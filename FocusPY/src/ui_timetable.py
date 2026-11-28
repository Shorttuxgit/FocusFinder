# --------------------------------------------------
# The main window: daily timetable, grades panel, options and dialogs
# --------------------------------------------------

import random
import tkinter as tk
import tkinter.font as tkfont
from bisect import bisect_left
from datetime import datetime, date, timedelta
from tkinter import ttk, filedialog
import customtkinter as ctk

from FocusPY.src.constants import (
    BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, BUTTON_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT,
    ACCENT_HOVER, FG_GREEN, DANGER, ZEBRA_ROW, OVERLAY_BG,
)
from FocusPY.src.config_manager import load_config, write_to_config, get_config_error
from FocusPY.src.friend_manager import export_friend_file, import_friend_file, load_friends, delete_friend
from FocusPY.src.settings import SETTINGS, ACTIONS, SECTION_ORDER
from FocusPY.src.ui_common import make_button, make_dropdown, fit_text
from FocusPY.src.ui_grades import GradesPanel
from FocusPY.src.ui_progress import ProgressView

# --------------------------------------------------
# Table layout
# --------------------------------------------------

# Extra room around table text, in pixels
CELL_PADDING = 26

# Greetings for the small hours. One is picked at random each time the app starts.
LATE_NIGHT_GREETINGS = (          # 11pm to 2am
    "Burning the midnight oil,",
    "Night owl mode activated,",
    "Checking timetables at this hour,",
    "The night is still young,",
)
VERY_EARLY_GREETINGS = (          # 2am to 6am
    "Even the sun isn't up yet,",
    "Sleep is for the weak,",
    "The birds aren't even awake yet,",
    "Time for bed or time for breakfast,",
)


def pick_greeting(hour, choose=random.choice):
    """The greeting for an hour of the day (0-23). It is followed by the student's name."""
    if hour >= 23 or hour < 2:
        return choose(LATE_NIGHT_GREETINGS)
    if hour < 6:
        return choose(VERY_EARLY_GREETINGS)
    if hour < 12:
        return "Good Morning,"
    if hour < 18:
        return "Good Afternoon,"
    return "Good Evening,"


# --------------------------------------------------
# Table helpers
# --------------------------------------------------

def parse_event_time(raw):
    # "2026-11-24T09:00:00.000Z" -> datetime (raises ValueError if it is not a date)
    return datetime.strptime(raw.split(".")[0].replace("T", " "), "%Y-%m-%d %H:%M:%S")


def event_field(event, key):
    # Room / staff can sit at the top level or inside "extendedProps"
    value = event.get(key) or (event.get("extendedProps") or {}).get(key)
    return str(value or "").strip() or "—"


def week_start(day_key):
    # Monday of the week a "YYYY-MM-DD" key belongs to (None for non-dates like "9999-99-99")
    try:
        day = date.fromisoformat(day_key)
    except ValueError:
        return None
    return day - timedelta(days=day.weekday())


def first_day_index(dates, today):
    """Which day to open on: today, else the day before the next lesson day."""
    position = bisect_left(dates, today)

    if position >= len(dates):
        return 0
    if dates[position] == today:
        return position
    return max(0, position - 1)


class TimetableWidget:
    def __init__(self, root, events, student_name, progress=None, show=True):
        self.root = root

        # In-app overlay panels (options, dialogs) and toast state
        self._overlays = []
        self.options_entry = None
        self._option_vars = []
        self.toast = None

        # The logged-in student's own data
        self.my_events = events
        self.my_name = student_name

        # Track active view data separately for friend timetable switching
        self.events = events
        self.student_name = student_name
        self.view_key = "me"

        # Settings (see settings.py). Read values anywhere with self.cfg["key"].
        self.cfg = load_config()
        self.sett_enabled = self.cfg["sett_enabled"]
        self.friends_system_enabled = self.cfg["friends_system"]
        self.progress_enabled = self.cfg["progress_system"]
        self.time_format = bool(self.cfg["time_format"])
        self.update_time_format_variables()

        # Grades are ignored completely when the progress system is off
        self.my_progress = (progress or []) if self.progress_enabled else []

        # Caches that keep screen changes cheap
        self._friends = None
        self._group_cache = {}
        self._nav_state = None
        self._date_text = None
        self._col_widths = None         # column widths currently applied to the table
        self._need = None               # widest Time / Room / Staff text in the whole view
        self._shown_cache = {}          # day -> rows ready to insert, until widths change
        self._row_full = {}             # table row -> full (unshortened) text
        self._display_job = None        # pending redraw (see request_display)
        self._tree_width = 0
        self._refit_job = None

        # Greeting depends on the time of day
        self.greeting = pick_greeting(datetime.now().hour)

        # Group timetable events by date and start on today (or the nearest day)
        self.load_days()
        self.current_index = first_day_index(self.available_dates, date.today().isoformat())

        # Fonts used to measure text for the table
        self.body_font = tkfont.Font(root=self.root, family="Arial", size=13)
        self.head_font = tkfont.Font(root=self.root, family="Arial", size=10, weight="bold")

        self.configure_styles()
        self.create_widgets()
        self.update_display()
        self.root.bind("<Escape>", lambda _e: self.on_escape())

        # With show=False everything is built but kept off screen, so the caller
        # can reveal a finished window (see show / finalize_layout)
        if show:
            self.show()

    def update_time_format_variables(self):
        # Configure time format strings based on user preference
        if self.time_format:
            self.formats = "%I"
            self.isPOM = "%p"
        else:
            self.formats = "%H"
            self.isPOM = ""

    # ------------------------------------------------------------------
    # Cached data
    # ------------------------------------------------------------------

    def get_friends(self, force=False):
        # Friends are read from disk once and then kept in memory
        if force or self._friends is None:
            self._friends = load_friends()
        return self._friends

    def get_grouped_days(self, view_key, events):
        # Parsing every event is wasted work when the same view is shown again
        key = (view_key, self.time_format)
        if key not in self._group_cache:
            self._group_cache[key] = self.process_events(events)
        return self._group_cache[key]

    def load_days(self):
        # Group the active view's events by date
        self.grouped_days = self.get_grouped_days(self.view_key, self.events)
        self.available_dates = sorted(self.grouped_days)

        # Everything measured from the old view or time format is out of date
        self._need = None
        self._shown_cache = {}

    def reload_days(self):
        # Rebuild the day list for the active view, staying on the same day if possible
        current_key = None
        if self.current_index < len(self.available_dates):
            current_key = self.available_dates[self.current_index]

        self.load_days()

        if current_key in self.available_dates:
            self.current_index = self.available_dates.index(current_key)
        else:
            self.current_index = min(self.current_index, max(0, len(self.available_dates) - 1))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def configure_styles(self):
        # Flat, borderless table styling. The "clam" theme draws light and dark
        # 3D edges around widgets, so every edge colour is set to the surface colour.
        style = ttk.Style()
        style.theme_use("clam")

        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        style.configure(
            "Treeview",
            background=BG_SURFACE, foreground=FG_TEXT, fieldbackground=BG_SURFACE,
            borderwidth=0, relief="flat",
            bordercolor=BG_SURFACE, lightcolor=BG_SURFACE, darkcolor=BG_SURFACE,
            rowheight=34, font=("Arial", 13)
        )
        style.map(
            "Treeview",
            background=[("selected", BG_HOVER)],
            foreground=[("selected", FG_TEXT)]
        )
        style.configure(
            "Treeview.Heading",
            background=BG_CARD, foreground=FG_ACCENT,
            borderwidth=0, relief="flat",
            bordercolor=BG_CARD, lightcolor=BG_CARD, darkcolor=BG_CARD,
            padding=(12, 9), font=("Arial", 10, "bold")
        )
        style.map(
            "Treeview.Heading",
            background=[("active", BG_HOVER)],
            relief=[("active", "flat"), ("pressed", "flat")]
        )

    def create_widgets(self):
        # Main application layout container
        self.main_container = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)

        # The timetable screen (greeting, day navigation, table, grades panel) lives
        # in its own page so the Progress view can take its place
        self.timetable_page = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)

        # Greeting box in its own separate centered card at the top
        greeting_card = ctk.CTkFrame(self.timetable_page, fg_color=BG_CARD, corner_radius=16)
        greeting_card.pack(fill=tk.X, pady=(0, 10), ipady=2)

        self.welcome_label = ctk.CTkLabel(
            greeting_card,
            text=f"{self.greeting} {self.student_name}",
            font=("Arial", 18, "bold"),
            text_color=FG_ACCENT
        )
        self.welcome_label.pack(anchor="center", pady=6)

        # Day navigation card: previous button, clickable date, next button
        nav_card = ctk.CTkFrame(self.timetable_page, fg_color=BG_CARD, corner_radius=16)
        nav_card.pack(fill=tk.X, pady=(0, 10), ipadx=12, ipady=6)

        self.prev_btn = make_button(nav_card, "<< Previous Day", self.prev_day, width=140)
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.date_label = ctk.CTkLabel(
            nav_card, text="", font=("Arial", 14, "bold"), text_color=FG_TEXT, cursor="hand2"
        )
        self.date_label.pack(side=tk.LEFT, expand=True)
        self.date_label.bind("<Button-1>", self.go_to_today)

        self.next_btn = make_button(nav_card, "Next Day >>", self.next_day, width=140)
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Bottom toolbar: view switcher dropdown and options button side by side
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        self.bottom_frame = bottom_frame

        bottom_inner = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_inner.pack(expand=True, anchor="center")

        # The view dropdown only exists when the friends system is on
        if self.friends_system_enabled:
            view_options = ["My Timetable"] + [f"Friend: {name}" for name in self.get_friends()]

            self.view_var = tk.StringVar(value=view_options[0])
            self.view_dropdown = make_dropdown(
                bottom_inner, view_options, command=self.on_view_selected,
                variable=self.view_var, width=190, height=36
            )
            self.view_dropdown.pack(side=tk.LEFT, padx=6)

        # Progress view button: sits between the dropdown and Options. It only
        # exists when the progress system is on and grades were found.
        self.progress_view = None
        self.progress_view_open = False
        self.view_btn = None
        if self.progress_enabled and self.my_progress:
            self.view_btn = make_button(bottom_inner, "Progress", self.toggle_progress_view, width=110)
            self.view_btn.pack(side=tk.LEFT, padx=6)

        # The Options button only exists when there is something to show in it
        if self.has_options():
            make_button(bottom_inner, "Options", self.open_options_menu, width=110).pack(side=tk.LEFT, padx=6)

        # The toolbar is packed first so it stays at the bottom; the page fills the rest
        self.timetable_page.pack(fill=tk.BOTH, expand=True)

        # Timetable events table card
        table_card = ctk.CTkFrame(self.timetable_page, fg_color=BG_SURFACE, corner_radius=16, border_width=0)
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.table_card = table_card

        columns = ("Time", "Event Title", "Room", "Staff")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse", height=4)
        self.tree.tag_configure("even", background=BG_SURFACE)
        self.tree.tag_configure("odd", background=ZEBRA_ROW)

        for name in columns:
            self.tree.heading(name, text=name, anchor=tk.W)
            self.tree.column(name, width=100, anchor=tk.W, stretch=(name == "Event Title"))

        scrollbar = ctk.CTkScrollbar(
            table_card, orientation="vertical", command=self.tree.yview,
            fg_color=BG_SURFACE, button_color=BG_HOVER, button_hover_color=BUTTON_HOVER
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=10)

        self.tree.bind("<Configure>", self.on_tree_configure)
        self.tree.bind("<Double-1>", self.on_row_double_click)

        # Grades panel sits beneath the timetable (skipped when the progress system is off
        # or no grades were found)
        self.grades_panel = None
        if self.my_progress:
            self.grades_panel = GradesPanel(
                self.root, self.timetable_page, self.my_progress, before=self.table_card
            )

    def show(self):
        # Put the finished interface on screen
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

    def finalize_layout(self):
        """Settle size-dependent layout once the window is at its final size.

        Column widths and the course buttons depend on real widget sizes, which
        are unknown until the window is on screen. Calling this before the
        window becomes visible means nothing shifts after the user sees it.
        """
        # Cancel any resize work that was queued while the window was being built
        if self._refit_job is not None:
            self.root.after_cancel(self._refit_job)
            self._refit_job = None

        self._tree_width = self.tree.winfo_width()
        self._col_widths = None
        self.render_rows()

        if self.grades_panel is not None:
            self.grades_panel.finalize()

        # If config.json could not be read, say so instead of silently using defaults
        problem = get_config_error()
        if problem:
            self.root.after(500, lambda: self.show_toast(f"Config problem: {problem}", is_error=True))

    # ------------------------------------------------------------------
    # Timetable table
    # ------------------------------------------------------------------

    def content_widths(self):
        """Widest Time, Room and Staff text found anywhere in the active view.

        Measuring the whole view once means the columns keep the same size while
        moving between days, so a click never has to re-measure or re-layout the table.
        """
        if self._need is None:
            time_w = self.head_font.measure("Time") + CELL_PADDING + 8
            room_w = self.head_font.measure("Room") + CELL_PADDING + 8
            staff_w = self.head_font.measure("Staff") + CELL_PADDING + 8

            measure = self.body_font.measure
            for day in self.grouped_days.values():
                for event in day["events"]:
                    time_w = max(time_w, measure(event["time"]) + CELL_PADDING)
                    room_w = max(room_w, measure(event["room"]) + CELL_PADDING)
                    staff_w = max(staff_w, measure(event["staff"]) + CELL_PADDING)

            self._need = (time_w, room_w, staff_w)

        return self._need

    def fit_columns(self):
        """Column widths: Time, Room and Staff take what they need; the lesson
        title gets everything left over. If space is still short, Staff gives
        way first and long text is cut with an ellipsis instead of running off the edge.
        """
        time_w, room_w, staff_w = self.content_widths()

        available = self.tree.winfo_width()
        if available <= 1:
            available = 640

        title_min = 150
        title_w = available - time_w - room_w - staff_w

        # Not enough room for the title: take the difference from the Staff column
        if title_w < title_min:
            staff_floor = self.head_font.measure("Staff") + CELL_PADDING + 8
            give = min(title_min - title_w, max(0, staff_w - staff_floor))
            staff_w -= give
            title_w += give

        return time_w, max(title_w, 60), room_w, staff_w

    def day_rows(self, day_key):
        """Rows for one day as [(shown text, full text)], worked out once and
        reused until the column widths change."""
        rows = self._shown_cache.get(day_key)

        if rows is None:
            _, title_w, _, staff_w = self._col_widths
            rows = []
            for event in self.grouped_days[day_key]["events"]:
                full = (event["time"], event["title"], event["room"], event["staff"])
                shown = (
                    full[0],
                    fit_text(self.body_font, full[1], title_w - CELL_PADDING),
                    full[2],
                    fit_text(self.body_font, full[3], staff_w - CELL_PADDING),
                )
                rows.append((shown, full))
            self._shown_cache[day_key] = rows

        return rows

    def render_rows(self):
        # Fill the table with the current day's lessons
        widths = self.fit_columns()

        # Only touch the column settings when a width really changed
        if widths != self._col_widths:
            self._col_widths = widths
            self._shown_cache = {}
            time_w, title_w, room_w, staff_w = widths
            self.tree.column("Time", width=time_w, minwidth=time_w, stretch=False)
            self.tree.column("Event Title", width=title_w, minwidth=60, stretch=True)
            self.tree.column("Room", width=room_w, minwidth=room_w, stretch=False)
            self.tree.column("Staff", width=staff_w, minwidth=staff_w, stretch=False)

        self.tree.delete(*self.tree.get_children())
        self._row_full = {}

        if not self.available_dates:
            return

        rows = self.day_rows(self.available_dates[self.current_index])
        for idx, (shown, full) in enumerate(rows):
            item = self.tree.insert("", tk.END, values=shown, tags=("odd" if idx % 2 else "even",))
            # Remember the full (unshortened) text for the double-click details
            self._row_full[item] = full

    def on_tree_configure(self, event):
        # Re-fit when the window is resized, waiting until the resize settles
        if event.width == self._tree_width:
            return
        self._tree_width = event.width

        if self._refit_job is not None:
            self.root.after_cancel(self._refit_job)
        self._refit_job = self.root.after(80, self.refit_after_resize)

    def refit_after_resize(self):
        self._refit_job = None
        self._col_widths = None
        self.render_rows()

    def on_row_double_click(self, event):
        # Full details for a lesson, in case any text was shortened to fit
        item = self.tree.identify_row(event.y)
        if item not in self._row_full:
            return

        time_text, title, room, staff = self._row_full[item]
        self.show_message("Lesson details", f"{title}\n{time_text}\nRoom: {room}\nStaff: {staff}")

    def update_display(self):
        # Refresh the date, the table rows and the arrow buttons for the active day
        if not self.available_dates:
            self.render_rows()
            self.set_date_text("No Timetable Data Available")
            self.update_nav_buttons(False, False)
            return

        self.set_date_text(self.grouped_days[self.available_dates[self.current_index]]["header"])
        self.render_rows()

        self.update_nav_buttons(
            self.current_index > 0,
            self.current_index < len(self.available_dates) - 1
        )

    def request_display(self):
        # Used by the day buttons. Quick repeated clicks only redraw once, for the
        # day they end on, which keeps slow computers responsive.
        if self._display_job is None:
            self._display_job = self.root.after_idle(self.run_display)

    def run_display(self):
        self._display_job = None
        self.update_display()

    def set_date_text(self, text):
        # Only redraw the label when the text changed
        if text != self._date_text:
            self._date_text = text
            self.date_label.configure(text=text)

    def update_nav_buttons(self, has_prev, has_next):
        # Reconfiguring a CustomTkinter button redraws it, so only do it on a change
        state = (has_prev, has_next)
        if state == self._nav_state:
            return
        previous = self._nav_state or (None, None)
        self._nav_state = state

        for button, enabled, old in ((self.prev_btn, has_prev, previous[0]), (self.next_btn, has_next, previous[1])):
            if enabled != old:
                button.configure(
                    state="normal" if enabled else "disabled",
                    fg_color=BG_HOVER if enabled else BG_SURFACE,
                    text_color=FG_TEXT if enabled else FG_SUBTEXT
                )

    def set_progress_visible(self, visible):
        # Grades belong to the logged-in student, so hide them on friends' timetables
        if self.grades_panel is not None:
            self.grades_panel.set_visible(visible)

    # ------------------------------------------------------------------
    # Switching between the timetable and the Progress view.
    # The Progress view itself lives in ui_progress.py and is only created
    # the first time the Progress button is pressed, so it costs nothing at start-up.
    # ------------------------------------------------------------------

    def on_view_selected(self, choice):
        # Picking a timetable from the dropdown always returns to the timetable screen
        self.show_timetable_page()
        self.switch_timetable_view(choice)

    def toggle_progress_view(self):
        # The Progress button switches between the two screens
        if self.progress_view_open:
            self.show_timetable_page()
        else:
            self.show_progress_page()

    def show_progress_page(self):
        if self.progress_view is None:
            self.progress_view = ProgressView(self.root, self.main_container, self.my_progress)

        self.timetable_page.pack_forget()
        self.progress_view.show()
        self.view_btn.configure(text="Timetable")
        self.progress_view_open = True

    def show_timetable_page(self):
        if not self.progress_view_open:
            return

        self.progress_view.hide()
        self.timetable_page.pack(fill=tk.BOTH, expand=True)
        self.view_btn.configure(text="Progress")
        self.progress_view_open = False

    # ------------------------------------------------------------------
    # Timetable data
    # ------------------------------------------------------------------

    def process_events(self, events):
        # Parse and group events by calendar date, excluding Saturdays
        grouped = {}
        time_format = f"{self.formats}:%M{self.isPOM}"

        for event in events:
            start_raw = str(event.get("start", ""))
            end_raw = str(event.get("end", ""))

            try:
                dt_start = parse_event_time(start_raw)
                dt_end = parse_event_time(end_raw)
            except ValueError:
                # Dates that cannot be read go into one "Unscheduled" group
                dt_start = datetime.min
                day_key = "9999-99-99"
                day_header = "Unscheduled / Other"
                time_str = f"{start_raw} - {end_raw}"
            else:
                if dt_start.weekday() == 5:
                    continue

                day_key = dt_start.strftime("%Y-%m-%d")
                day_header = dt_start.strftime("%A, %d %B %Y")
                time_str = f"{dt_start.strftime(time_format)} - {dt_end.strftime(time_format)}"

            day = grouped.setdefault(day_key, {"header": day_header, "events": []})
            day["events"].append({
                "dt_start": dt_start,
                "time": time_str,
                "title": event.get("title") or "N/A",
                "room": event_field(event, "room"),
                "staff": event_field(event, "staff"),
            })

        # Lessons in time order within each day
        for day in grouped.values():
            day["events"].sort(key=lambda item: item["dt_start"])

        return grouped

    def prev_day(self):
        # Move to the previous day in the timetable view
        if self.current_index > 0:
            self.current_index -= 1
            self.request_display()

    def next_day(self):
        # Move to the next day in the timetable view
        if self.current_index < len(self.available_dates) - 1:
            self.current_index += 1
            self.request_display()

    def go_to_today(self, _event=None):
        # Jump to today's date when it belongs to the displayed timetable week
        today = date.today()
        today_key = today.isoformat()

        # No lessons at weekends
        if today.weekday() >= 5:
            return

        if today_key not in self.grouped_days:
            # Today has no lessons: only jump if the timetable covers today's week
            this_week = today - timedelta(days=today.weekday())
            if not any(week_start(key) == this_week for key in self.available_dates):
                return

            self.grouped_days[today_key] = {"header": today.strftime("%A, %d %B %Y"), "events": []}
            self.available_dates = sorted(self.grouped_days)

        self.current_index = self.available_dates.index(today_key)
        self.request_display()

    def switch_timetable_view(self, choice):
        # Switch active timetable between user schedule and selected friend schedule
        if choice == "My Timetable":
            self.student_name = self.my_name
            self.events = self.my_events
            self.view_key = "me"
        else:
            friend_name = choice.replace("Friend: ", "").strip()
            friend_data = self.get_friends()
            if friend_name in friend_data:
                self.student_name = friend_name
                self.events = friend_data[friend_name]
                self.view_key = f"friend:{friend_name}"

        self.load_days()
        self.current_index = 0

        self.welcome_label.configure(text=f"{self.greeting} {self.student_name}")
        self.set_progress_visible(choice == "My Timetable")
        self.update_display()

    # ------------------------------------------------------------------
    # In-app overlays: panels and dialogs are drawn inside the main window
    # ------------------------------------------------------------------

    def push_overlay(self, width, close_on_click=False, on_close=None):
        # Dim the whole window and draw a card in the middle
        overlay = ctk.CTkFrame(self.root, fg_color=OVERLAY_BG, corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(
            overlay, fg_color=BG_CARD, corner_radius=18,
            border_width=1, border_color=BG_HOVER
        )

        # The card is as tall as its content. To give it a fixed width, a thin spacer
        # goes inside it. Where it sits matters:
        #  - Tk never makes a widget less than 1 pixel tall, so a spacer on the very
        #    top row paints a line across the rounded corners and border. (That was the
        #    "line sticking out" bug.) It is therefore placed BELOW the corner curve,
        #    where the card edge is straight, and inset from the side borders, so it
        #    only ever paints the card's own colour onto itself.
        #  - It adds that space at the top, so the first widget in each card has no
        #    top padding of its own.
        # `width` is in CustomTkinter units; convert it to pixels for this screen.
        # (CustomTkinter does not allow a width in .place(), so it can't be set there.)
        try:
            scale = card._get_widget_scaling()
        except Exception:
            scale = max(1.0, self.root.winfo_fpixels("1i") / 96)

        corner = int(18 * scale) + 1                # card corner radius, in pixels
        inset = max(2, int(round(scale)) + 1)       # keep clear of the 1-unit border
        spacer = tk.Frame(
            card, width=int(width * scale) - 2 * inset, height=1,
            bd=0, highlightthickness=0, bg=BG_CARD
        )
        spacer.pack(padx=inset, pady=(corner, 0))
        card.place(relx=0.5, rely=0.5, anchor="center")

        entry = {"overlay": overlay, "on_close": on_close}
        self._overlays.append(entry)

        if close_on_click:
            overlay.bind("<Button-1>", lambda _e: self.close_overlay(entry))

        overlay.lift()
        return entry, card

    def close_overlay(self, entry):
        if entry not in self._overlays:
            return
        self._overlays.remove(entry)

        try:
            entry["overlay"].destroy()
        except tk.TclError:
            pass

        if entry["on_close"]:
            entry["on_close"]()

    def on_escape(self):
        # Escape closes the top-most overlay, or else leaves the Progress view
        if self._overlays:
            self.close_overlay(self._overlays[-1])
        elif self.progress_view_open:
            self.show_timetable_page()

    def show_toast(self, message, is_error=False):
        # Small auto-dismissing banner for quick confirmations
        if self.toast is not None:
            try:
                self.toast.destroy()
            except tk.TclError:
                pass

        color = DANGER if is_error else FG_GREEN
        toast = ctk.CTkFrame(
            self.root, fg_color=BG_SURFACE, corner_radius=14,
            border_width=1, border_color=color
        )
        ctk.CTkLabel(
            toast, text=message, font=("Arial", 12, "bold"), text_color=color, wraplength=460
        ).pack(padx=18, pady=10)
        toast.place(relx=0.5, rely=1.0, y=-24, anchor="s")
        toast.lift()
        self.toast = toast

        def dismiss():
            try:
                toast.destroy()
            except tk.TclError:
                pass
            if self.toast is toast:
                self.toast = None

        # Errors stay a little longer than confirmations
        self.root.after(6000 if is_error else 3200, dismiss)

    def show_dialog(self, title, message, buttons, is_error=False):
        # buttons: list of (text, kind, callback) where kind is primary, danger or secondary
        entry, card = self.push_overlay(360)

        ctk.CTkLabel(
            card, text=title, font=("Arial", 15, "bold"),
            text_color=DANGER if is_error else FG_ACCENT
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            card, text=message, font=("Arial", 12), text_color=FG_TEXT,
            wraplength=310, justify="center"
        ).pack(padx=24, pady=(6, 14))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=(0, 18))

        for text, kind, callback in buttons:
            # Every button closes the dialog first, then runs its own action
            def run(cb=callback):
                self.close_overlay(entry)
                if cb:
                    cb()

            make_button(row, text, run, kind, height=34, width=100).pack(side=tk.LEFT, padx=6)

    def show_message(self, title, message, is_error=False):
        self.show_dialog(title, message, [("OK", "primary", None)], is_error=is_error)

    def show_confirm(self, title, message, on_yes, yes_text="Yes"):
        self.show_dialog(
            title, message,
            [("Cancel", "secondary", None), (yes_text, "danger", on_yes)]
        )

    # ------------------------------------------------------------------
    # Options panel (built from settings.py)
    # ------------------------------------------------------------------

    def option_visible(self, requires):
        # An item with requires="some_key" is only shown while that config value is on
        return not requires or bool(self.cfg.get(requires))

    def has_options(self):
        # True when the Options panel would have at least one setting or button
        return (
            any(not s.hidden and self.option_visible(s.requires) for s in SETTINGS)
            or any(self.option_visible(a.requires) for a in ACTIONS)
        )

    def collect_option_sections(self):
        # Group visible settings and actions by section, in display order
        sections = {}

        def section(name):
            return sections.setdefault(name, {"settings": [], "actions": []})

        for setting in SETTINGS:
            if not setting.hidden and self.option_visible(setting.requires):
                section(setting.section)["settings"].append(setting)

        for action in ACTIONS:
            if self.option_visible(action.requires):
                section(action.section)["actions"].append(action)

        # Sections that draw their own content (options_extra_<name>)
        for name in SECTION_ORDER:
            if hasattr(self, self.extra_method_name(name)):
                section(name)

        ordered = [name for name in SECTION_ORDER if name in sections]
        ordered += [name for name in sections if name not in SECTION_ORDER]
        return [(name, sections[name]) for name in ordered]

    @staticmethod
    def extra_method_name(section):
        return "options_extra_" + section.lower().replace(" ", "_")

    def open_options_menu(self):
        self.close_options_menu()
        self._option_vars = []

        entry, card = self.push_overlay(
            600, close_on_click=True,
            on_close=lambda: setattr(self, "options_entry", None)
        )
        self.options_entry = entry

        ctk.CTkLabel(
            card, text="Options", font=("Arial", 17, "bold"), text_color=FG_ACCENT
        ).pack(anchor="w", padx=24, pady=(0, 4))

        # Pack the Done button first so it can never be pushed out of view
        make_button(card, "Done", self.close_options_menu, "primary").pack(
            side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 18)
        )

        for name, content in self.collect_option_sections():
            heading = ctk.CTkLabel(
                card, text=name.upper(), font=("Arial", 10, "bold"), text_color=FG_SUBTEXT
            )
            heading.pack(anchor="w", padx=24, pady=(10, 4))

            drew = bool(content["settings"] or content["actions"])

            # Toggles / choices for this section
            for setting in content["settings"]:
                self.add_setting_row(card, setting)

            # Buttons for this section
            for action in content["actions"]:
                handler = getattr(self, action.handler, None)
                if handler is None:
                    print(f"[!] Options action '{action.id}' has no method '{action.handler}'")
                    continue
                make_button(card, action.label, handler).pack(fill=tk.X, padx=20, pady=(0, 8))

            # Custom content for this section
            extra = getattr(self, self.extra_method_name(name), None)
            if extra is not None and extra(card):
                drew = True

            # Don't leave a heading with nothing under it
            if not drew:
                heading.destroy()

    def add_setting_row(self, card, setting):
        # One row: label on the left, switch or choice buttons on the right
        row = ctk.CTkFrame(card, fg_color=BG_SURFACE, corner_radius=12, height=44)
        row.pack(fill=tk.X, padx=20, pady=(0, 6))
        row.pack_propagate(False)

        ctk.CTkLabel(
            row, text=setting.label, font=("Arial", 12), text_color=FG_TEXT
        ).pack(side=tk.LEFT, padx=14)

        value = self.cfg.get(setting.key, setting.default)

        if setting.kind == "toggle":
            variable = ctk.IntVar(value=1 if value else 0)
            self._option_vars.append(variable)
            ctk.CTkSwitch(
                row, text="", width=46, variable=variable, onvalue=1, offvalue=0,
                progress_color=FG_ACCENT,
                command=lambda key=setting.key, var=variable: self.set_setting(key, bool(var.get()))
            ).pack(side=tk.RIGHT, padx=(0, 10))

        elif setting.kind == "choice":
            choices = ctk.CTkSegmentedButton(
                row, values=list(setting.choices), height=28,
                fg_color=BG_CARD, selected_color=FG_ACCENT, selected_hover_color=ACCENT_HOVER,
                unselected_color=BG_HOVER, unselected_hover_color=BUTTON_HOVER,
                text_color=FG_TEXT,
                command=lambda choice, key=setting.key: self.set_setting(key, choice)
            )
            choices.set(value)
            choices.pack(side=tk.RIGHT, padx=(0, 10))

    def set_setting(self, key, value):
        # Save a changed setting, then run its apply_setting_<key> method if there is one
        self.cfg[key] = value

        try:
            write_to_config(key, value)
        except OSError:
            self.show_toast("Could not save that setting", is_error=True)

        handler = getattr(self, f"apply_setting_{key}", None)
        if handler is not None:
            handler(value)

    def apply_setting_time_format(self, value):
        # Switch between 24-hour and 12-hour times straight away
        self.time_format = bool(value)
        self.update_time_format_variables()
        self.reload_days()
        self.update_display()

    def apply_setting_light_theme(self, value):
        # Colours are chosen once when the app starts, so this needs a restart
        self.show_toast("Restart FocusFinder to switch to the " + ("light" if value else "dark") + " theme")

    def options_extra_friends(self, parent):
        # Remove-friend row; drawn under the Friends actions
        if not self.friends_system_enabled:
            return False

        friend_data = self.get_friends()
        if not friend_data:
            return False

        remove_row = ctk.CTkFrame(parent, fg_color="transparent")
        remove_row.pack(fill=tk.X, padx=20, pady=(0, 4))

        friend_names = list(friend_data)
        del_var = tk.StringVar(value=friend_names[0])
        self._option_vars.append(del_var)
        make_dropdown(
            remove_row, friend_names, variable=del_var
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        def remove_friend():
            name = del_var.get()

            def do_remove():
                delete_friend(name)
                self.refresh_dropdown_options()
                self.show_toast(f"Removed {name}")
                self.open_options_menu()

            self.show_confirm(
                "Remove friend", f"Remove {name} from your friends?",
                do_remove, yes_text="Remove"
            )

        make_button(remove_row, "Remove", remove_friend, "danger", height=34, width=90).pack(side=tk.LEFT)
        return True

    def close_options_menu(self):
        if self.options_entry is not None:
            self.close_overlay(self.options_entry)

    # ------------------------------------------------------------------
    # Friends actions
    # ------------------------------------------------------------------

    def export_my_timetable_file(self):
        # Export the current user's timetable as an Android-compatible file
        try:
            output_file = export_friend_file(self.my_name, self.my_events)
        except Exception as error:
            self.show_message("Export failed", f"Could not save your timetable:\n{error}", is_error=True)
            return
        self.show_message("Timetable exported", f"Your timetable was saved to:\n{output_file}")

    def open_add_friend_dialog(self):
        # Native file picker to import an Android-compatible friend timetable
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Import Friend Timetable",
            filetypes=[
                ("FocusFinder timetable files", "*.fff"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            name, _events = import_friend_file(file_path)
        except Exception as error:
            self.show_message("Import failed", f"Could not import this timetable file:\n{error}", is_error=True)
            return

        self.refresh_dropdown_options()
        self.show_toast(f"Imported {name}'s timetable")
        self.open_options_menu()

    def refresh_dropdown_options(self):
        # Refresh view dropdown values when friends are added or removed
        if not self.friends_system_enabled:
            return

        friend_data = self.get_friends(force=True)

        # Forget any parsed friend timetables, since they may have changed
        self._group_cache = {key: value for key, value in self._group_cache.items() if key[0] == "me"}

        view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data]
        self.view_dropdown.configure(values=view_options)

        current = self.view_var.get()
        if current not in view_options:
            self.view_var.set("My Timetable")
            self.switch_timetable_view("My Timetable")
        elif current != "My Timetable":
            # The friend on screen may have just been re-imported
            self.switch_timetable_view(current)