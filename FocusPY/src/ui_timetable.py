# --------------------------------------------------
# The main window: daily timetable, grades panel, options and dialogs
# --------------------------------------------------

import tkinter as tk
import tkinter.font as tkfont
from bisect import bisect_left
from datetime import datetime, date, timedelta
from tkinter import ttk, filedialog
import customtkinter as ctk

from FocusPY.src.constants import (
    BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, BUTTON_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT,
    ACCENT_HOVER, FG_GREEN, DANGER, DANGER_HOVER, ZEBRA_ROW, OVERLAY_BG, GRID_LINE,
)
from FocusPY.src.config_manager import load_config, write_to_config, get_config_error
from FocusPY.src.friend_manager import export_friend_file, import_friend_file, load_friends, delete_friend
from FocusPY.src.course_names import unique_short_names
from FocusPY.src.settings import SETTINGS, ACTIONS, SECTION_ORDER

# --------------------------------------------------
# Look and feel
# --------------------------------------------------

# Grade ladders used by Focus. The right scale is chosen by checking which one
# contains the course's target grade.
GRADE_SCALES = [
    ["U", "E", "D", "C", "B", "A", "A*"],
    ["U", "PP", "MP", "MM", "DM", "DD", "D*D", "D*D*"],
]
COMMIT_SCALE = ["3", "2", "1", "★"]

# Extra room around table text, in pixels
CELL_PADDING = 26

# Button colours: (background, hover, text)
BUTTON_STYLES = {
    "primary": (FG_ACCENT, ACCENT_HOVER, BG_DARK),
    "danger": (DANGER, DANGER_HOVER, BG_DARK),
    "secondary": (BG_HOVER, BUTTON_HOVER, FG_TEXT),
}


def make_button(parent, text, command, kind="secondary", **options):
    """A standard rounded button. Extra keyword arguments (width, height...) override the defaults."""
    background, hover, text_color = BUTTON_STYLES[kind]
    settings = dict(
        font=("Arial", 12, "bold"), fg_color=background, hover_color=hover,
        text_color=text_color, corner_radius=12, height=36,
    )
    settings.update(options)
    return ctk.CTkButton(parent, text=text, command=command, **settings)


def make_dropdown(parent, values, **options):
    """A standard dropdown. Extra keyword arguments (width, command, variable...) override the defaults."""
    settings = dict(
        fg_color=BG_HOVER, button_color=BG_DARK, button_hover_color=BG_SURFACE, height=34,
        text_color=FG_TEXT, dropdown_fg_color=BG_CARD, dropdown_text_color=FG_TEXT,
        dropdown_hover_color=BG_HOVER,
    )
    settings.update(options)
    return ctk.CTkOptionMenu(parent, values=values, **settings)


# --------------------------------------------------
# Grade ladder helpers
# --------------------------------------------------

def scale_hint(title):
    # Course titles usually say which grading ladder applies (None = no clue)
    text = (title or "").lower()
    if any(word in text for word in ("btec", "diploma", "extended certificate", "cambridge technical")):
        return 1
    if any(word in text for word in ("a level", "a-level", "as level")):
        return 0
    return None


def resolve_grade_index(scale, grade):
    """Position of the grade on the ladder, or None if it isn't on it.

    A grade given as a single letter stands for the doubled grade, because
    Focus drops the second letter: "D" -> "DD", "M" -> "MM", "P" -> "PP".
    An exact match always wins, so A Level "D" stays a plain D.
    """
    grade = (grade or "").strip()
    if not grade:
        return None
    if grade in scale:
        return scale.index(grade)
    if grade + grade in scale:
        return scale.index(grade + grade)
    return None


def resolve_grade_indices(scale, grade):
    # Same as resolve_grade_index, as a list (empty when there is no match)
    index = resolve_grade_index(scale, grade)
    return [] if index is None else [index]


def pick_scale(title, grades):
    """The grade ladder that fits the most of the given grades.

    The title hint is tried first, so it decides any tie (for example a lone
    "D", which exists on both ladders).
    """
    order = list(range(len(GRADE_SCALES)))
    hint = scale_hint(title)
    if hint is not None:
        order.remove(hint)
        order.insert(0, hint)

    best, best_score = None, 0
    for index in order:
        scale = GRADE_SCALES[index]
        score = sum(resolve_grade_index(scale, grade) is not None for grade in grades)
        if score > best_score:
            best, best_score = scale, score
    return best


def course_history(course):
    """Every recorded grade for a course, oldest first.

    Older saved data has no history, so the latest values are used as one point.
    """
    history = course.get("history")
    if history:
        return history
    return [{key: course.get(key, "") for key in ("period", "label", "grade", "ttg", "commit")}]


def history_grades(points):
    # Every grade and target mentioned in the history (used to pick the ladder)
    return [value for point in points for value in (point["grade"], point["ttg"])]


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def summarise_history(scale, points):
    """Text for the Progress view's summary boxes.

    Returns a dict. The *_kind values are "good", "bad" or "plain" and decide
    the colour of each box.
    """
    last = points[-1]
    now = resolve_grade_index(scale, last["grade"])
    target = resolve_grade_index(scale, last["ttg"])

    info = {
        "current": scale[now] if now is not None else "—",
        "current_sub": " · ".join(part for part in (last["label"], last["period"]) if part),
        "change": "—", "change_sub": "", "change_kind": "plain",
        "target": scale[target] if target is not None else "—",
        "target_sub": "", "target_kind": "plain",
        "commit": normalise_commit(last["commit"]) or "—",
    }

    # Change since the last earlier point that had a readable grade
    if now is not None:
        before = next((p for p in reversed(points[:-1])
                       if resolve_grade_index(scale, p["grade"]) is not None), None)

        if before is None:
            info["change"], info["change_sub"] = "First grade", "nothing to compare yet"
        else:
            diff = now - resolve_grade_index(scale, before["grade"])
            since = f"since {before['label'] or before['period']}".strip()
            if diff > 0:
                info.update(change=f"▲ {plural(diff, 'grade')}", change_sub=since, change_kind="good")
            elif diff < 0:
                info.update(change=f"▼ {plural(-diff, 'grade')}", change_sub=since, change_kind="bad")
            else:
                info.update(change="No change", change_sub=since)

    # Distance to the target
    if now is not None and target is not None:
        gap = target - now
        if gap > 0:
            info["target_sub"] = f"{plural(gap, 'grade')} to go"
        elif gap == 0:
            info.update(target_sub="On target", target_kind="good")
        else:
            info.update(target_sub=f"{plural(-gap, 'grade')} above target", target_kind="good")

    return info


def plan_markers(now_idxs, target_idx):
    """Where the "Now" and "Target" labels go under the grade ladder.

    Returns [(text, kind, column, span)], all meant for the same row. When the
    target sits inside the highlighted range, "Now" is centred over the widest
    run of highlighted grades beside it so the two labels never overlap.
    """
    now_idxs = sorted(now_idxs)

    # Only a target, or only a current grade
    if not now_idxs:
        return [("Target", "target", target_idx, 1)] if target_idx is not None else []

    now_span = (now_idxs[0], now_idxs[-1] - now_idxs[0] + 1)

    if target_idx is None:
        return [("Now", "now", *now_span)]

    # Target is outside the highlighted range: two separate labels
    if target_idx not in now_idxs:
        return [("Now", "now", *now_span), ("Target", "target", target_idx, 1)]

    # Target is the only highlighted grade: one combined label
    rest = [i for i in now_idxs if i != target_idx]
    if not rest:
        return [("Now • Target", "target", target_idx, 1)]

    # Target is inside the range: put "Now" over the widest unbroken run beside it
    runs = []
    for index in rest:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    widest = max(runs, key=len)

    return [("Now", "now", widest[0], len(widest)), ("Target", "target", target_idx, 1)]


def normalise_commit(value):
    # Focus writes the top commitment level as "1*" or "*"; show it as a star
    value = (value or "").strip()
    return "★" if value in ("1*", "*", "★") else value


# --------------------------------------------------
# Table helpers
# --------------------------------------------------

def fit_text(font, text, max_pixels):
    """Shorten text with an ellipsis so it fits in max_pixels."""
    if max_pixels <= 0 or font.measure(text) <= max_pixels:
        return text

    # Binary search for the longest piece of text that still fits
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(text[:middle].rstrip() + "…") <= max_pixels:
            low = middle
        else:
            high = middle - 1

    return text[:low].rstrip() + "…" if low else "…"


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
        self._col_widths = None
        self._tree_width = 0
        self._refit_job = None
        self._current_rows = []
        self._row_full = {}

        # Greeting depends on the time of day
        self.greeting = "Good Morning," if datetime.now().hour < 12 else "Good Afternoon,"

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
        self.progress_page = None
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

        # Grades panel sits beneath the timetable (skipped when the progress system is off)
        self.progress_card = None
        self.build_progress_card()

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
        for name in ("_refit_job", "_bar_job"):
            job = getattr(self, name, None)
            if job is not None:
                self.root.after_cancel(job)
                setattr(self, name, None)

        self._tree_width = self.tree.winfo_width()
        self._col_widths = None
        self.render_rows()

        if self.progress_card is not None:
            self.layout_course_buttons()

        # If config.json could not be read, say so instead of silently using defaults
        problem = get_config_error()
        if problem:
            self.root.after(500, lambda: self.show_toast(f"Config problem: {problem}", is_error=True))

    # ------------------------------------------------------------------
    # Timetable table
    # ------------------------------------------------------------------

    def fit_columns(self, rows):
        """Work out column widths from the text actually shown.

        Time, Room and Staff take only the room they need; the lesson title gets
        everything left over. If space is still short, Staff gives way first and
        long text is cut with an ellipsis rather than running off the edge.
        """

        def needed(index, heading):
            width = self.head_font.measure(heading) + CELL_PADDING + 8
            for row in rows:
                width = max(width, self.body_font.measure(row[index]) + CELL_PADDING)
            return width

        time_w = needed(0, "Time")
        room_w = needed(2, "Room")
        staff_w = needed(3, "Staff")

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

    def render_rows(self):
        # Fill the table with the current day's lessons
        rows = self._current_rows
        widths = self.fit_columns(rows)
        time_w, title_w, room_w, staff_w = widths

        # Only touch the column settings when a width really changed
        if widths != self._col_widths:
            self._col_widths = widths
            self.tree.column("Time", width=time_w, minwidth=time_w, stretch=False)
            self.tree.column("Event Title", width=title_w, minwidth=60, stretch=True)
            self.tree.column("Room", width=room_w, minwidth=room_w, stretch=False)
            self.tree.column("Staff", width=staff_w, minwidth=staff_w, stretch=False)

        self.tree.delete(*self.tree.get_children())
        self._row_full = {}

        for idx, (time_text, title, room, staff) in enumerate(rows):
            item = self.tree.insert(
                "", tk.END,
                values=(
                    time_text,
                    fit_text(self.body_font, title, title_w - CELL_PADDING),
                    room,
                    fit_text(self.body_font, staff, staff_w - CELL_PADDING),
                ),
                tags=("odd" if idx % 2 else "even",)
            )
            # Remember the full (unshortened) text for the double-click details
            self._row_full[item] = (time_text, title, room, staff)

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
        # Refresh the table rows for the active date
        if not self.available_dates:
            self._current_rows = []
            self.render_rows()
            self.set_date_text("No Timetable Data Available")
            self.update_nav_buttons(False, False)
            return

        day = self.grouped_days[self.available_dates[self.current_index]]

        self.set_date_text(day["header"])
        self._current_rows = [(e["time"], e["title"], e["room"], e["staff"]) for e in day["events"]]
        self.render_rows()

        self.update_nav_buttons(
            self.current_index > 0,
            self.current_index < len(self.available_dates) - 1
        )

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

    # ------------------------------------------------------------------
    # Grades panel (only built when "progress_system" is on)
    # ------------------------------------------------------------------

    def build_progress_card(self):
        # Grades panel: one course at a time, chosen with a button per course
        self.course_blocks = {}
        self.course_buttons = []
        self.active_course = None
        self._bar_width = 0
        self._button_pos = {}
        self._bar_job = None

        # Nothing to show: progress system off, or no grades were found
        if not self.my_progress:
            return

        card = ctk.CTkFrame(self.timetable_page, fg_color=BG_CARD, corner_radius=16)
        card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.table_card)
        self.progress_card = card

        # Top row: title plus one button per course
        self.course_bar = ctk.CTkFrame(card, fg_color="transparent")
        self.course_bar.pack(fill=tk.X, padx=14, pady=(8, 0))

        self.course_title = ctk.CTkLabel(
            self.course_bar, text="Current Grades", font=("Arial", 12, "bold"), text_color=FG_ACCENT
        )
        self.course_title.grid(row=0, column=0, padx=(2, 10), pady=2, sticky="w")

        names = unique_short_names([course.get("title") for course in self.my_progress])
        for index, name in enumerate(names):
            self.course_buttons.append(ctk.CTkButton(
                self.course_bar, text=name,
                font=("Arial", 11, "bold"), height=24, corner_radius=12,
                width=10, border_spacing=6,
                fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT,
                command=lambda i=index: self.show_course(i)
            ))

        # Area where the selected course's details are shown
        self.course_area = ctk.CTkFrame(card, fg_color="transparent")
        self.course_area.pack(fill=tk.X, padx=4, pady=(0, 6))

        self.root.update_idletasks()
        self.layout_course_buttons()
        self.course_bar.bind("<Configure>", self.on_bar_configure)

        # Only the first course is built now; the rest are built a little at a
        # time once the window is open, so start-up stays quick
        self.show_course(0)
        self.root.after(100, self.prebuild_course_blocks, 1)

    def prebuild_course_blocks(self, index):
        # Build one course panel per tick so switching courses later is instant
        if index >= len(self.my_progress):
            return

        try:
            self.get_course_block(index)
        except tk.TclError:
            return      # window was closed in the meantime

        self.root.after(30, self.prebuild_course_blocks, index + 1)

    def layout_course_buttons(self):
        # Flow the course buttons onto extra rows when they don't fit on one line
        width = self.course_bar.winfo_width()
        if width <= 1:
            width = max(300, self.root.winfo_width() - 60)
        self._bar_width = width

        used = self.course_title.winfo_reqwidth() + 14
        row, column, in_row = 0, 1, 1

        for index, button in enumerate(self.course_buttons):
            needed = button.winfo_reqwidth() + 8

            # Start a new row when this button would go past the edge
            if in_row > 0 and used + needed > width:
                row, column, used, in_row = row + 1, 0, 0, 0

            # Only move a button if its position actually changed
            position = (row, column)
            if self._button_pos.get(index) != position:
                button.grid(row=row, column=column, padx=3, pady=2, sticky="w")
                self._button_pos[index] = position

            used += needed
            column += 1
            in_row += 1

    def on_bar_configure(self, event):
        # Re-flow the buttons after a resize settles
        if event.width == self._bar_width:
            return
        if self._bar_job is not None:
            self.root.after_cancel(self._bar_job)
        self._bar_job = self.root.after(80, self.relayout_buttons)

    def relayout_buttons(self):
        self._bar_job = None
        self.layout_course_buttons()

    def get_course_block(self, index):
        # Build a course panel the first time it is needed, then reuse it
        block = self.course_blocks.get(index)
        if block is None:
            block = self.build_course_block(self.course_area, self.my_progress[index])
            self.course_blocks[index] = block
        return block

    def set_course_button_style(self, index, active):
        self.course_buttons[index].configure(
            fg_color=FG_ACCENT if active else BG_HOVER,
            hover_color=ACCENT_HOVER if active else BUTTON_HOVER,
            text_color=BG_DARK if active else FG_TEXT
        )

    def show_course(self, index):
        # Swap in the selected course. Blocks are built once and reused, so
        # switching only hides one frame and shows another.
        if index == self.active_course:
            return

        previous = self.active_course
        if previous is not None:
            self.course_blocks[previous].pack_forget()
            self.set_course_button_style(previous, False)

        self.get_course_block(index).pack(fill=tk.X, padx=4, pady=3)
        self.set_course_button_style(index, True)
        self.active_course = index

    def build_course_block(self, parent, course):
        # Returns an unpacked frame; show_course decides when to display it
        grade = course.get("grade", "")
        target = course.get("ttg", "")
        commit = normalise_commit(course.get("commit", ""))
        scale = pick_scale(course.get("title"), history_grades(course_history(course)))

        block = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=10)

        top = ctk.CTkFrame(block, fg_color="transparent")
        top.pack(fill=tk.X, padx=12, pady=(7, 4))

        # Left: course title and "Current / Target" summary
        text_col = ctk.CTkFrame(top, fg_color="transparent")
        text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkLabel(
            text_col, text=course.get("title", "Course"), font=("Arial", 11, "bold"),
            text_color=FG_TEXT, anchor="w", justify="left", wraplength=430
        ).pack(anchor="w")

        summary = f"Current: {grade or '—'}   •   Target: {target or '—'}"
        ctk.CTkLabel(
            text_col, text=summary, font=("Arial", 10), text_color=FG_SUBTEXT, anchor="w"
        ).pack(anchor="w")

        # Right: commitment circles
        commit_col = ctk.CTkFrame(top, fg_color="transparent")
        commit_col.pack(side=tk.RIGHT, padx=(10, 0))

        circles = ctk.CTkFrame(commit_col, fg_color="transparent")
        circles.pack()
        for value in COMMIT_SCALE:
            active = value == commit
            ctk.CTkLabel(
                circles, text=value, width=20, height=20, corner_radius=10,
                font=("Arial", 10, "bold"),
                fg_color=FG_ACCENT if active else BG_CARD,
                text_color=BG_DARK if active else FG_SUBTEXT
            ).pack(side=tk.LEFT, padx=1)
        ctk.CTkLabel(
            commit_col, text="Commitment", font=("Arial", 9), text_color=FG_SUBTEXT
        ).pack(pady=(1, 0))

        # No recognised grade scale: nothing more to draw
        if not scale:
            ctk.CTkFrame(block, fg_color="transparent", height=2).pack()
            return block

        # Grade ladder
        bar = ctk.CTkFrame(block, fg_color="transparent")
        bar.pack(fill=tk.X, padx=10, pady=(0, 7))

        now_idxs = resolve_grade_indices(scale, grade)
        target_idxs = resolve_grade_indices(scale, target)
        target_idx = target_idxs[0] if target_idxs else None
        now_start = min(now_idxs) if now_idxs else None

        for i, label in enumerate(scale):
            bar.grid_columnconfigure(i, weight=1, uniform="grade")

            # Current grade is blue, grades below it are grey, grades above are dim
            if i in now_idxs:
                fill, text_color = FG_ACCENT, BG_DARK
            elif now_start is not None and i < now_start:
                fill, text_color = BG_HOVER, FG_TEXT
            else:
                fill, text_color = BG_CARD, FG_SUBTEXT

            # One label per grade (a label can draw its own rounded background).
            # Only the target grade needs a second widget for its green outline.
            if i == target_idx:
                outline = ctk.CTkFrame(bar, fg_color=FG_GREEN, corner_radius=7)
                outline.grid(row=0, column=i, sticky="ew", padx=1)
                ctk.CTkLabel(
                    outline, text=label, font=("Arial", 10, "bold"), text_color=text_color,
                    fg_color=fill, corner_radius=5, height=20
                ).pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            else:
                ctk.CTkLabel(
                    bar, text=label, font=("Arial", 10, "bold"), text_color=text_color,
                    fg_color=fill, corner_radius=6, height=24
                ).grid(row=0, column=i, sticky="ew", padx=1)

        # "Now" and "Target" labels share one line under the ladder
        colours = {"now": FG_ACCENT, "target": FG_GREEN}
        for text, kind, column, span in plan_markers(now_idxs, target_idx):
            ctk.CTkLabel(
                bar, text=text, font=("Arial", 9, "bold"), text_color=colours[kind], height=12
            ).grid(row=1, column=column, columnspan=span, pady=(2, 0))

        return block

    def set_progress_visible(self, visible):
        # Grades belong to the logged-in student, so hide them on friends' timetables
        if self.progress_card is None:
            return
        if visible:
            self.progress_card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.table_card)
        else:
            self.progress_card.pack_forget()

    # ------------------------------------------------------------------
    # Progress view: grade history as a chart.
    # Nothing here is built at start-up; the page is created the first time
    # the Progress button is pressed.
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
        # Build the page on first use only, so it costs nothing at start-up
        if self.progress_page is None:
            self.build_progress_page()

        self.timetable_page.pack_forget()
        self.progress_page.pack(fill=tk.BOTH, expand=True)
        self.view_btn.configure(text="Timetable")
        self.progress_view_open = True

        # Draw once the page has a size (the chart also redraws whenever it is resized)
        self.root.after_idle(self.draw_progress_chart)

    def show_timetable_page(self):
        if not self.progress_view_open:
            return

        self.progress_page.pack_forget()
        self.timetable_page.pack(fill=tk.BOTH, expand=True)
        self.view_btn.configure(text="Progress")
        self.progress_view_open = False

    def build_progress_page(self):
        # Not packed here; show_progress_page decides when it appears
        page = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
        self.progress_page = page
        self.chart_index = 0
        self._chart_job = None

        # Header card: title on the left, course picker on the right
        header = ctk.CTkFrame(page, fg_color=BG_CARD, corner_radius=16)
        header.pack(fill=tk.X, pady=(0, 10), ipady=2)

        ctk.CTkLabel(
            header, text="Progress", font=("Arial", 18, "bold"), text_color=FG_ACCENT
        ).pack(side=tk.LEFT, padx=(18, 12), pady=8)

        self.chart_names = unique_short_names([course.get("title") for course in self.my_progress])
        make_dropdown(
            header, self.chart_names, command=self.on_chart_course, width=280
        ).pack(side=tk.RIGHT, padx=(0, 14), pady=8)

        # Four summary boxes: current grade, change, target, commitment
        summary = ctk.CTkFrame(page, fg_color="transparent")
        summary.pack(fill=tk.X, pady=(0, 10))

        self.chips = {}
        captions = (("current", "Current grade"), ("change", "Change"), ("target", "Target"), ("commit", "Commitment"))
        for column, (key, caption) in enumerate(captions):
            summary.grid_columnconfigure(column, weight=1, uniform="chip")

            box = ctk.CTkFrame(summary, fg_color=BG_CARD, corner_radius=14)
            box.grid(row=0, column=column, sticky="nsew",
                     padx=(0 if column == 0 else 5, 0 if column == len(captions) - 1 else 5))

            ctk.CTkLabel(
                box, text=caption.upper(), font=("Arial", 9, "bold"), text_color=FG_SUBTEXT
            ).pack(pady=(9, 0))
            value = ctk.CTkLabel(box, text="", font=("Arial", 22, "bold"), text_color=FG_TEXT)
            value.pack()
            sub = ctk.CTkLabel(box, text="", font=("Arial", 10), text_color=FG_SUBTEXT)
            sub.pack(pady=(0, 9))
            self.chips[key] = (value, sub)

        # Chart card: course title and legend on top, the chart underneath
        card = ctk.CTkFrame(page, fg_color=BG_SURFACE, corner_radius=16)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill=tk.X, padx=16, pady=(12, 0))

        ctk.CTkLabel(top, text="◆ Target", font=("Arial", 11, "bold"), text_color=FG_GREEN).pack(side=tk.RIGHT)
        ctk.CTkLabel(top, text="● Grade    ", font=("Arial", 11, "bold"), text_color=FG_ACCENT).pack(side=tk.RIGHT)
        self.chart_title = ctk.CTkLabel(
            top, text="", font=("Arial", 13, "bold"), text_color=FG_TEXT, anchor="w"
        )
        self.chart_title.pack(side=tk.LEFT)

        self.chart_canvas = tk.Canvas(card, bg=BG_SURFACE, highlightthickness=0, bd=0)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 10))
        self.chart_canvas.bind("<Configure>", self.on_chart_configure)

        self.update_chart_summary()

    def on_chart_course(self, name):
        # A different course was picked in the header
        self.chart_index = self.chart_names.index(name)
        self.update_chart_summary()
        self.draw_progress_chart()

    def on_chart_configure(self, _event):
        # Redraw once a resize settles
        if self._chart_job is not None:
            self.root.after_cancel(self._chart_job)
        self._chart_job = self.root.after(60, self.draw_progress_chart)

    def set_chip(self, key, value, sub, value_color, sub_color=FG_SUBTEXT):
        value_label, sub_label = self.chips[key]
        value_label.configure(text=value, text_color=value_color)
        sub_label.configure(text=sub, text_color=sub_color)

    def update_chart_summary(self):
        # Fill the four boxes and the chart title for the selected course
        course = self.my_progress[self.chart_index]
        points = course_history(course)
        scale = pick_scale(course.get("title"), history_grades(points))

        self.chart_title.configure(text=course.get("title", "Course"))

        # Grades that aren't on a known ladder can't be summarised
        if scale is None:
            for key in self.chips:
                self.set_chip(key, "—", "", FG_TEXT)
            return

        info = summarise_history(scale, points)
        change_colour = {"good": FG_GREEN, "bad": DANGER, "plain": FG_TEXT}[info["change_kind"]]
        target_sub_colour = FG_GREEN if info["target_kind"] == "good" else FG_SUBTEXT

        self.set_chip("current", info["current"], info["current_sub"], FG_ACCENT)
        self.set_chip("change", info["change"], info["change_sub"], change_colour)
        self.set_chip("target", info["target"], info["target_sub"], FG_GREEN, target_sub_colour)
        self.set_chip("commit", info["commit"], "", FG_TEXT)

    def draw_progress_chart(self):
        # Line chart of the selected course: one point per recorded grade (blue
        # line) with the target set at each point (green diamonds), labelled
        # with the Focus code (e.g. SAS1) and period underneath.
        self._chart_job = None
        if self.progress_page is None or not self.progress_view_open:
            return

        canvas = self.chart_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 150 or height < 150:
            return      # not laid out yet; the resize event will draw it

        course = self.my_progress[self.chart_index]
        points = course_history(course)
        scale = pick_scale(course.get("title"), history_grades(points))

        if scale is None:
            canvas.create_text(
                width / 2, height / 2, text="These grades can't be shown on a chart",
                fill=FG_SUBTEXT, font=("Arial", 12)
            )
            return

        # Sizes below are multiplied by px so the chart is the right size on high-DPI screens
        px = max(1.0, self.root.winfo_fpixels("1i") / 96)
        line_h = self.head_font.metrics("linespace")
        label_font = ("Arial", 10, "bold")
        small_font = ("Arial", 9)
        grid_colour = GRID_LINE

        # Plot area: grade names on the left, three lines of labels underneath
        rows = len(scale)
        left = max(self.head_font.measure(name) for name in scale) + 24 * px
        right = 26 * px
        axis_y = height - (3 * line_h + 18 * px)
        top_row = 32 * px
        bottom_row = axis_y - 14 * px
        step = (bottom_row - top_row) / (rows - 1)

        def y_of(index):
            return bottom_row - index * step

        count = len(points)
        pad = 40 * px
        span = max(1.0, width - left - right - 2 * pad)
        spacing = span / (count - 1) if count > 1 else span

        def x_of(i):
            return left + pad + (span * i / (count - 1) if count > 1 else span / 2)

        # Background: striped rows with a grade name on each
        for i, name in enumerate(scale):
            y = y_of(i)
            canvas.create_rectangle(
                left, max(0, y - step / 2), width - right, min(axis_y, y + step / 2),
                fill=ZEBRA_ROW if i % 2 == 0 else BG_SURFACE, outline=""
            )
            canvas.create_line(left, y, width - right, y, fill=grid_colour)
            canvas.create_text(left - 12 * px, y, text=name, anchor="e", fill=FG_SUBTEXT, font=label_font)

        # A faint guide line down from every point to its label
        for i in range(count):
            canvas.create_line(x_of(i), top_row - 14 * px, x_of(i), axis_y, fill=grid_colour, dash=(2, 4))

        grade_idx = [resolve_grade_index(scale, point["grade"]) for point in points]
        target_idx = [resolve_grade_index(scale, point["ttg"]) for point in points]

        # Target: dashed green line with a diamond at each point.
        # With only one point, the line runs the full width so the goal is easy to see.
        targets = [(x_of(i), y_of(t)) for i, t in enumerate(target_idx) if t is not None]
        dash_width = max(1, int(1.5 * px))
        if len(targets) == 1:
            canvas.create_line(left, targets[0][1], width - right, targets[0][1],
                               fill=FG_GREEN, width=dash_width, dash=(6, 4))
        elif len(targets) > 1:
            canvas.create_line(*[value for point in targets for value in point],
                               fill=FG_GREEN, width=dash_width, dash=(6, 4))
        for x, y in targets:
            r = 7 * px
            canvas.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y,
                                  fill=FG_GREEN, outline=BG_SURFACE, width=2)

        # Grades: blue line and dots, the newest one larger with a ring around it
        actual = [(x_of(i), y_of(g), i) for i, g in enumerate(grade_idx) if g is not None]
        if len(actual) > 1:
            canvas.create_line(*[value for x, y, _ in actual for value in (x, y)],
                               fill=FG_ACCENT, width=3 * px, capstyle="round", joinstyle="round")

        for n, (x, y, i) in enumerate(actual):
            newest = n == len(actual) - 1
            r = (7 if newest else 5.5) * px
            if newest:
                ring = r + 5 * px
                canvas.create_oval(x - ring, y - ring, x + ring, y + ring, outline=FG_ACCENT, width=2)
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=FG_ACCENT, outline=BG_SURFACE, width=2)

            # Grade name above the dot, or below it when the target diamond is just above
            offset = (20 + (5 if newest else 0)) * px
            t = target_idx[i]
            target_above = t is not None and 0 < y - y_of(t) < 34 * px
            below = target_above and y + offset < axis_y + 4 * px
            canvas.create_text(
                x, y + offset if below else y - offset,
                text=scale[grade_idx[i]], fill=FG_TEXT, font=label_font
            )

        # Under the chart: Focus code, period and commitment for every point
        show_period = count == 1 or spacing > 50 * px
        show_commit = count == 1 or spacing > 84 * px
        for i, point in enumerate(points):
            x = x_of(i)
            y = axis_y + 12 * px

            canvas.create_text(
                x, y, text=point["label"] or "—", anchor="n", font=label_font,
                fill=FG_ACCENT if i == count - 1 else FG_TEXT
            )

            if show_period and point["period"]:
                canvas.create_text(x, y + line_h, text=point["period"], anchor="n",
                                   fill=FG_SUBTEXT, font=small_font)

            commit = normalise_commit(point["commit"])
            if show_commit and commit:
                canvas.create_text(x, y + 2 * line_h, text=f"Commit {commit}", anchor="n",
                                   fill=FG_SUBTEXT, font=small_font)

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
            self.update_display()

    def next_day(self):
        # Move to the next day in the timetable view
        if self.current_index < len(self.available_dates) - 1:
            self.current_index += 1
            self.update_display()

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
        self.update_display()

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
        card.place(relx=0.5, rely=0.5, anchor="center")

        # The card is as tall as its content. A thin spacer sets the width in
        # CustomTkinter units so it scales correctly on high-DPI screens.
        ctk.CTkFrame(card, fg_color="transparent", width=width, height=1, corner_radius=0).pack()

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
        ).pack(pady=(18, 2))
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
            400, close_on_click=True,
            on_close=lambda: setattr(self, "options_entry", None)
        )
        self.options_entry = entry

        ctk.CTkLabel(
            card, text="Options", font=("Arial", 17, "bold"), text_color=FG_ACCENT
        ).pack(anchor="w", padx=24, pady=(18, 4))

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