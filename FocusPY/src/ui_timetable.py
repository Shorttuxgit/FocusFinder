import math
import re
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime, date, timedelta
import customtkinter as ctk

from FocusPY.src.constants import BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT, FG_GREEN
from FocusPY.src.config_manager import load_config, write_to_config
from FocusPY.src.friend_manager import export_friend_file, import_friend_file, load_friends, delete_friend

# Grade ladders used by Focus. The right scale is chosen by checking which one
# contains the course's target grade.
GRADE_SCALES = [
    ["U", "E", "D", "C", "B", "A", "A*"],
    ["U", "PP", "MP", "MM", "DM", "DD", "D*D", "D*D*"],
]
COMMIT_SCALE = ["3", "2", "1", "★"]
ZEBRA_ROW = "#1d1d2c"
OVERLAY_BG = "#11111b"
DANGER = "#f38ba8"
DANGER_HOVER = "#eba0ac"


def pick_grade_scale(target, current):
    for grade in (target, current):
        for scale in GRADE_SCALES:
            if grade and grade in scale:
                return scale
    return None


def resolve_grade_indices(scale, grade):
    """Positions on the ladder that match the grade. An exact grade matches one
    position; a bare letter such as "D" or "M" matches every grade starting with
    that letter (D -> DM, DD, D*D, D*D*)."""
    if not grade:
        return []
    if grade in scale:
        return [scale.index(grade)]
    if len(grade) == 1:
        return [i for i, entry in enumerate(scale) if entry.startswith(grade)]
    return []


def short_course_name(title):
    """Short button label: 'Art Photography - A Level' -> 'Art Photography',
    'Media: Production - ...' -> 'Media'."""
    title = (title or "Course").strip()
    name = re.split(r"\s*[:(]|\s+-\s+", title, maxsplit=1)[0].strip() or title
    return name if len(name) <= 18 else name[:17].rstrip() + "…"


def normalise_commit(value):
    value = (value or "").strip()
    return "★" if value in ("1*", "*", "★") else value


class TimetableWidget:
    def __init__(self, root, events, student_name, progress=None):
        self.root = root
        self.my_progress = progress or []

        # In-app overlay panels (options, dialogs) and toast state
        self._overlays = []
        self.options_entry = None
        self.toast = None
        self.my_events = events
        self.my_name = student_name

        # Track active view data separately for friend timetable switching
        self.events = events
        self.student_name = student_name
        
        # Load user configuration settings
        config = load_config()
        self.sett_enabled = config.get("sett_enabled", True)
        self.friends_system_enabled = config.get("friends_system", True)
        self.time_format = config.get("time_format", False)
        self.update_time_format_variables()
        # Determine greeting based on current time of day
        current_Date = datetime.now()
        current_time = current_Date.strftime("%p")
        self.greeting = "Good Morning," if current_time == "AM" else "Good Afternoon,"

        # Group timetable events by date
        self.grouped_days = self.process_events(events)
        self.available_dates = sorted(list(self.grouped_days.keys()))

        # Set calendar index to today's date
        self.current_index = 0
        today_str = date.today().strftime("%Y-%m-%d")

        for idx, d_str in enumerate(self.available_dates):
            if d_str == today_str:
                self.current_index = idx
                break
            elif d_str > today_str:
                self.current_index = max(0, idx - 1)
                break

        self.configure_styles()
        self.create_widgets()
        self.update_display()
        self.root.bind("<Escape>", lambda _e: self.on_escape())

    def update_time_format_variables(self):
        # Configure time format strings based on user preference
        if self.time_format:
            self.formats = "%I"
            self.isPOM = "%p"
            self.isPOMenable = "Enabled" 
        else:
            self.formats = "%H"
            self.isPOM = ""
            self.isPOMenable = "Disabled" 

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
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        # Greeting box in its own separate centered card at the top
        greeting_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        greeting_card.pack(fill=tk.X, pady=(0, 10), ipady=2)

        self.welcome_label = ctk.CTkLabel(
            greeting_card, 
            text=f"{self.greeting} {self.student_name}", 
            font=("Arial", 18, "bold"), 
            text_color=FG_ACCENT
        )
        self.welcome_label.pack(anchor="center", pady=6)

        # Day navigation card
        nav_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        nav_card.pack(fill=tk.X, pady=(0, 10), ipadx=12, ipady=6)

        self.prev_btn = ctk.CTkButton(nav_card, text="<< Previous Day", command=self.prev_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.date_label = ctk.CTkLabel(
            nav_card,
            text="",
            font=("Arial", 14, "bold"),
            text_color=FG_TEXT,
            cursor="hand2"
        )
        self.date_label.pack(side=tk.LEFT, expand=True)
        self.date_label.bind("<Button-1>", self.go_to_today)

        self.next_btn = ctk.CTkButton(nav_card, text="Next Day >>", command=self.next_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Bottom toolbar frame holding view switcher dropdown and options button side-by-side
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        self.bottom_frame = bottom_frame

        bottom_inner = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_inner.pack(expand=True, anchor="center")

        if self.friends_system_enabled:
            friend_data = load_friends()
            view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data.keys()]
            
            self.view_var = tk.StringVar(value=view_options[0])
            self.view_dropdown = ctk.CTkOptionMenu(
                bottom_inner, values=view_options, command=self.switch_timetable_view,
                variable=self.view_var, width=190, height=36, fg_color=BG_HOVER, button_color=BG_DARK
            )
            self.view_dropdown.pack(side=tk.LEFT, padx=6)

        if self.sett_enabled or self.friends_system_enabled:
            options_btn = ctk.CTkButton(
                bottom_inner, text="Options", font=("Arial", 12, "bold"),
                fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                command=self.open_options_menu, corner_radius=12, height=36, width=110
            )
            options_btn.pack(side=tk.LEFT, padx=6)

        # Timetable events table card
        table_card = ctk.CTkFrame(self.main_container, fg_color=BG_SURFACE, corner_radius=16, border_width=0)
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.table_card = table_card

        columns = ("Time", "Event Title", "Room", "Staff")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse", height=4)
        self.tree.tag_configure("even", background=BG_SURFACE)
        self.tree.tag_configure("odd", background=ZEBRA_ROW)
        self.tree.heading("Time", text="Time")
        self.tree.heading("Event Title", text="Event Title")
        self.tree.heading("Room", text="Room")
        self.tree.heading("Staff", text="Staff")

        self.tree.column("Time", width=180, anchor=tk.W)
        self.tree.column("Event Title", width=260, anchor=tk.W)
        self.tree.column("Room", width=80, anchor=tk.W)
        self.tree.column("Staff", width=140, anchor=tk.W)

        scrollbar = ctk.CTkScrollbar(
            table_card, orientation="vertical", command=self.tree.yview,
            fg_color=BG_SURFACE, button_color=BG_HOVER, button_hover_color="#585b70"
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=10)

        # Grades panel sits beneath the timetable
        self.progress_card = None
        self.build_progress_card()

    def build_progress_card(self):
        # Grades panel: one course at a time, chosen with a button per course
        if not self.my_progress:
            return

        card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.table_card)
        self.progress_card = card

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=14, pady=(8, 0))

        ctk.CTkLabel(
            header, text="Current Grades", font=("Arial", 12, "bold"), text_color=FG_ACCENT
        ).pack(side=tk.LEFT, padx=(2, 10))

        self.course_buttons = []
        for index, course in enumerate(self.my_progress):
            button = ctk.CTkButton(
                header, text=short_course_name(course.get("title")),
                font=("Arial", 11, "bold"), height=24, corner_radius=12,
                width=10, border_spacing=6,
                command=lambda i=index: self.show_course(i)
            )
            button.pack(side=tk.LEFT, padx=3)
            self.course_buttons.append(button)

        self.course_area = ctk.CTkFrame(card, fg_color="transparent")
        self.course_area.pack(fill=tk.X, padx=4, pady=(0, 6))

        self.show_course(0)

    def show_course(self, index):
        # Show the selected course's grade ladder and highlight its button
        for child in self.course_area.winfo_children():
            child.destroy()

        for i, button in enumerate(self.course_buttons):
            active = i == index
            button.configure(
                fg_color=FG_ACCENT if active else BG_HOVER,
                hover_color=FG_ACCENT if active else "#585b70",
                text_color=BG_DARK if active else FG_TEXT
            )

        self.build_course_block(self.course_area, self.my_progress[index])

    def build_course_block(self, parent, course):
        grade = course.get("grade", "")
        target = course.get("ttg", "")
        commit = normalise_commit(course.get("commit", ""))
        scale = pick_grade_scale(target, grade)

        block = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=10)
        block.pack(fill=tk.X, padx=4, pady=3)

        top = ctk.CTkFrame(block, fg_color="transparent")
        top.pack(fill=tk.X, padx=12, pady=(7, 4))

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

        # Commitment circles
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

        if not scale:
            ctk.CTkFrame(block, fg_color="transparent", height=2).pack()
            return

        # Grade ladder
        bar = ctk.CTkFrame(block, fg_color="transparent")
        bar.pack(fill=tk.X, padx=10, pady=(0, 7))

        now_idxs = resolve_grade_indices(scale, grade)
        target_idxs = resolve_grade_indices(scale, target)
        target_idx = target_idxs[0] if target_idxs else None
        now_start = min(now_idxs) if now_idxs else None
        now_end = max(now_idxs) if now_idxs else None

        for i, label in enumerate(scale):
            bar.grid_columnconfigure(i, weight=1, uniform="grade")

            if i in now_idxs:
                fill, text_color = FG_ACCENT, BG_DARK
            elif now_start is not None and i < now_start:
                fill, text_color = BG_HOVER, FG_TEXT
            else:
                fill, text_color = BG_CARD, FG_SUBTEXT

            segment = ctk.CTkFrame(
                bar, fg_color=fill, corner_radius=6, height=22,
                border_width=2 if i == target_idx else 0, border_color=FG_GREEN
            )
            segment.grid(row=0, column=i, sticky="ew", padx=1)
            segment.grid_propagate(False)
            ctk.CTkLabel(
                segment, text=label, font=("Arial", 10, "bold"), text_color=text_color
            ).place(relx=0.5, rely=0.5, anchor="center")

        def marker(text, color, row, column, span=1):
            ctk.CTkLabel(
                bar, text=text, font=("Arial", 9, "bold"), text_color=color, height=12
            ).grid(row=row, column=column, columnspan=span, pady=(2, 0))

        # "Now" is centred under every highlighted grade
        if now_idxs:
            span = now_end - now_start + 1
            if span == 1 and target_idx == now_start:
                marker("Now • Target", FG_GREEN, 1, now_start)
            else:
                marker("Now", FG_ACCENT, 1, now_start, span)
                if target_idx is not None:
                    inside = now_start <= target_idx <= now_end
                    marker("Target", FG_GREEN, 2 if inside else 1, target_idx)
        elif target_idx is not None:
            marker("Target", FG_GREEN, 1, target_idx)

    def set_progress_visible(self, visible):
        # Grades belong to the logged-in student, so hide them on friends' timetables
        if self.progress_card is None:
            return
        if visible:
            self.progress_card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.table_card)
        else:
            self.progress_card.pack_forget()

    def process_events(self, events):
        # Parse and group events by calendar date, excluding Saturdays
        grouped = {}
        for ev in events:
            start_raw = str(ev.get("start", ""))
            end_raw = str(ev.get("end", ""))

            try:
                clean_start = start_raw.split(".")[0].replace("T", " ")
                clean_end = end_raw.split(".")[0].replace("T", " ")

                dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
                dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

                if dt_start.weekday() == 5:
                    continue

                day_key = dt_start.strftime("%Y-%m-%d")
                day_header = dt_start.strftime("%A, %d %B %Y")
                time_str = f"{dt_start.strftime(f'{self.formats}:%M{self.isPOM}')} - {dt_end.strftime(f'{self.formats}:%M{self.isPOM}')}"
            except ValueError:
                dt_start = datetime.min
                day_key = "9999-99-99"
                day_header = "Unscheduled / Other"
                time_str = f"{start_raw} - {end_raw}"

            title = ev.get("title") or "N/A"
            room = str(ev.get("room") or ev.get("extendedProps", {}).get("room") or "—").strip()
            staff = str(ev.get("staff") or ev.get("extendedProps", {}).get("staff") or "—").strip()
            room = room if room else "—"
            staff = staff if staff else "—"

            if day_key not in grouped:
                grouped[day_key] = {"header": day_header, "events": []}

            grouped[day_key]["events"].append({
                "dt_start": dt_start,
                "time": time_str,
                "title": title,
                "room": room,
                "staff": staff
            })

        for day_key in grouped:
            grouped[day_key]["events"].sort(key=lambda x: x["dt_start"])

        return grouped

    def update_display(self):
        # Refresh treeview table rows for the active date
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.available_dates:
            self.date_label.configure(text="No Timetable Data Available")
            return

        current_key = self.available_dates[self.current_index]
        day_data = self.grouped_days[current_key]

        self.date_label.configure(text=day_data["header"])

        for idx, e in enumerate(day_data["events"]):
            self.tree.insert(
                "", tk.END,
                values=(e["time"], e["title"], e["room"], e["staff"]),
                tags=("odd" if idx % 2 else "even",)
            )

        has_prev = self.current_index > 0
        has_next = self.current_index < len(self.available_dates) - 1

        self.prev_btn.configure(state="normal" if has_prev else "disabled", fg_color=BG_HOVER if has_prev else BG_SURFACE, text_color=FG_TEXT if has_prev else FG_SUBTEXT)
        self.next_btn.configure(state="normal" if has_next else "disabled", fg_color=BG_HOVER if has_next else BG_SURFACE, text_color=FG_TEXT if has_next else FG_SUBTEXT)

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

        if today.weekday() >= 5:
            return

        if today_key not in self.grouped_days:
            if not self.available_dates:
                return

            today_week_start = today - timedelta(days=today.weekday())
            timetable_contains_today_week = any(
                date.fromisoformat(day_key)
                - timedelta(days=date.fromisoformat(day_key).weekday())
                == today_week_start
                for day_key in self.available_dates
            )

            if not timetable_contains_today_week:
                return

            self.grouped_days[today_key] = {
                "header": today.strftime("%A, %d %B %Y"),
                "events": []
            }
            self.available_dates = sorted(self.grouped_days.keys())

        self.current_index = self.available_dates.index(today_key)
        self.update_display()

    def switch_timetable_view(self, choice):
        # Switch active timetable between user schedule and selected friend schedule
        if choice == "My Timetable":
            self.student_name = self.my_name
            self.events = self.my_events
        else:
            friend_name = choice.replace("Friend: ", "").strip()
            friend_data = load_friends()
            if friend_name in friend_data:
                self.student_name = friend_name
                self.events = friend_data[friend_name]
        
        self.grouped_days = self.process_events(self.events)
        self.available_dates = sorted(list(self.grouped_days.keys()))
        self.current_index = 0
        
        self.welcome_label.configure(text=f"{self.greeting} {self.student_name}")
        self.set_progress_visible(choice == "My Timetable")
        self.update_display()

    # ------------------------------------------------------------------
    # In-app overlays: panels and dialogs are drawn inside the main window
    # ------------------------------------------------------------------

    def push_overlay(self, width, height, close_on_click=False, on_close=None):
        overlay = ctk.CTkFrame(self.root, fg_color=OVERLAY_BG, corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(
            overlay, fg_color=BG_CARD, corner_radius=18,
            border_width=1, border_color=BG_HOVER, width=width, height=height
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

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
        if self._overlays:
            self.close_overlay(self._overlays[-1])

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
            toast, text=message, font=("Arial", 12, "bold"), text_color=color
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

        self.root.after(3200, dismiss)

    def show_dialog(self, title, message, buttons, is_error=False):
        # buttons: list of (text, kind, callback) where kind is primary, danger or secondary
        lines = sum(max(1, math.ceil(len(line) / 42)) for line in message.split("\n"))
        height = max(170, 125 + lines * 18)
        entry, card = self.push_overlay(360, height)

        ctk.CTkLabel(
            card, text=title, font=("Arial", 15, "bold"),
            text_color=DANGER if is_error else FG_ACCENT
        ).pack(pady=(18, 2))
        ctk.CTkLabel(
            card, text=message, font=("Arial", 12), text_color=FG_TEXT,
            wraplength=310, justify="center"
        ).pack(padx=24, pady=(6, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(side=tk.BOTTOM, pady=(0, 18))

        styles = {
            "primary": (FG_ACCENT, "#74a0f0", BG_DARK),
            "danger": (DANGER, DANGER_HOVER, BG_DARK),
            "secondary": (BG_HOVER, "#585b70", FG_TEXT),
        }

        for text, kind, callback in buttons:
            fg, hover, text_color = styles[kind]

            def run(cb=callback):
                self.close_overlay(entry)
                if cb:
                    cb()

            ctk.CTkButton(
                row, text=text, command=run, fg_color=fg, hover_color=hover,
                text_color=text_color, font=("Arial", 12, "bold"),
                corner_radius=12, height=34, width=100
            ).pack(side=tk.LEFT, padx=6)

    def show_message(self, title, message, is_error=False):
        self.show_dialog(title, message, [("OK", "primary", None)], is_error=is_error)

    def show_confirm(self, title, message, on_yes, yes_text="Yes"):
        self.show_dialog(
            title, message,
            [("Cancel", "secondary", None), (yes_text, "danger", on_yes)]
        )

    # ------------------------------------------------------------------
    # Options panel
    # ------------------------------------------------------------------

    def open_options_menu(self):
        self.close_options_menu()

        friend_data = load_friends() if self.friends_system_enabled else {}

        height = 140
        if self.sett_enabled:
            height += 88
        if self.friends_system_enabled:
            height += 30 + 92 + (52 if friend_data else 0)

        entry, card = self.push_overlay(
            400, height, close_on_click=True,
            on_close=lambda: setattr(self, "options_entry", None)
        )
        self.options_entry = entry

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(16, 4))
        ctk.CTkLabel(
            header, text="Options", font=("Arial", 17, "bold"), text_color=FG_ACCENT
        ).pack(side=tk.LEFT)
        ctk.CTkButton(
            header, text="✕", width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=BG_HOVER, text_color=FG_SUBTEXT,
            font=("Arial", 13, "bold"), command=self.close_options_menu
        ).pack(side=tk.RIGHT)

        # Pack the Done button first so it can never be pushed out of view
        ctk.CTkButton(
            card, text="Done", command=self.close_options_menu,
            fg_color=FG_ACCENT, hover_color="#74a0f0", text_color=BG_DARK,
            font=("Arial", 12, "bold"), corner_radius=12, height=36
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 18))

        def section(title):
            ctk.CTkLabel(
                card, text=title, font=("Arial", 10, "bold"), text_color=FG_SUBTEXT
            ).pack(anchor="w", padx=24, pady=(10, 4))

        if self.sett_enabled:
            section("DISPLAY")
            row = ctk.CTkFrame(card, fg_color=BG_SURFACE, corner_radius=12, height=44)
            row.pack(fill=tk.X, padx=20)
            row.pack_propagate(False)

            self.time_var = ctk.IntVar(value=1 if self.time_format else 0)
            ctk.CTkLabel(
                row, text="12-hour time", font=("Arial", 12), text_color=FG_TEXT
            ).pack(side=tk.LEFT, padx=14)
            ctk.CTkSwitch(
                row, text="", width=46, command=self.toggle_time,
                variable=self.time_var, onvalue=1, offvalue=0,
                progress_color=FG_ACCENT
            ).pack(side=tk.RIGHT, padx=(0, 10))

        if self.friends_system_enabled:
            section("FRIENDS")

            for text, command in (
                ("Export my timetable", self.export_my_timetable_file),
                ("Import friend timetable", self.open_add_friend_dialog),
            ):
                ctk.CTkButton(
                    card, text=text, command=command, font=("Arial", 12, "bold"),
                    fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                    corner_radius=12, height=36
                ).pack(fill=tk.X, padx=20, pady=(0, 8))

            if friend_data:
                remove_row = ctk.CTkFrame(card, fg_color="transparent")
                remove_row.pack(fill=tk.X, padx=20, pady=(0, 4))

                friend_names = list(friend_data.keys())
                del_var = tk.StringVar(value=friend_names[0])
                ctk.CTkOptionMenu(
                    remove_row, values=friend_names, variable=del_var, height=34,
                    fg_color=BG_HOVER, button_color=BG_DARK, button_hover_color=BG_SURFACE
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

                ctk.CTkButton(
                    remove_row, text="Remove", command=remove_friend,
                    fg_color=DANGER, hover_color=DANGER_HOVER, text_color=BG_DARK,
                    font=("Arial", 12, "bold"), corner_radius=12, height=34, width=90
                ).pack(side=tk.LEFT)

    def close_options_menu(self):
        if self.options_entry is not None:
            self.close_overlay(self.options_entry)

    def toggle_time(self):
        # Toggle 12-hour or 24-hour time format preference and refresh display
        self.time_format = bool(self.time_var.get())  
        self.update_time_format_variables()
        write_to_config("time_format", self.time_format)        
        self.grouped_days = self.process_events(self.events)
        self.update_display()

    def export_my_timetable_file(self):
        # Export the current user's timetable as an Android-compatible file
        try:
            output_file = export_friend_file(self.my_name, self.my_events)
        except Exception as e:
            self.show_message("Export failed", f"Could not save your timetable:\n{e}", is_error=True)
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
        except Exception as e:
            self.show_message("Import failed", f"Could not import this timetable file:\n{e}", is_error=True)
            return

        self.refresh_dropdown_options()
        self.show_toast(f"Imported {name}'s timetable")
        self.open_options_menu()

    def refresh_dropdown_options(self):
        # Refresh view dropdown values when friends are added or removed
        if not self.friends_system_enabled:
            return
        friend_data = load_friends()
        view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data.keys()]
        self.view_dropdown.configure(values=view_options)
        if self.view_var.get() not in view_options:
            self.view_var.set("My Timetable")
            self.switch_timetable_view("My Timetable")