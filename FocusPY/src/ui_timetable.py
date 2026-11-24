import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
from datetime import datetime, date, timedelta
import customtkinter as ctk

from FocusPY.src.constants import BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT, FG_GREEN
from FocusPY.src.config_manager import load_config, write_to_config
from FocusPY.src.friend_manager import export_friend_file, import_friend_file, load_friends, delete_friend
from FocusPY.src.course_names import unique_short_names
from FocusPY.src.settings import SETTINGS, ACTIONS, SECTION_ORDER

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
ACCENT_HOVER = "#74a0f0"
BUTTON_HOVER = "#585b70"
CELL_PADDING = 26


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


def plan_markers(now_idxs, target_idx):
    """Where the "Now" and "Target" labels go under the grade ladder.

    Returns [(text, kind, column, span)], all meant for the same row. When the
    target sits inside the highlighted range, "Now" is centred over the widest
    run of highlighted grades beside it so the two labels never overlap.
    """
    now_idxs = sorted(now_idxs)

    if not now_idxs:
        return [("Target", "target", target_idx, 1)] if target_idx is not None else []

    if target_idx is None:
        return [("Now", "now", now_idxs[0], now_idxs[-1] - now_idxs[0] + 1)]

    if target_idx not in now_idxs:
        return [
            ("Now", "now", now_idxs[0], now_idxs[-1] - now_idxs[0] + 1),
            ("Target", "target", target_idx, 1),
        ]

    rest = [i for i in now_idxs if i != target_idx]
    if not rest:
        return [("Now • Target", "target", target_idx, 1)]

    runs = []
    for index in rest:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    widest = max(runs, key=len)

    return [
        ("Now", "now", widest[0], len(widest)),
        ("Target", "target", target_idx, 1),
    ]


def normalise_commit(value):
    value = (value or "").strip()
    return "★" if value in ("1*", "*", "★") else value


def fit_text(font, text, max_pixels):
    """Shorten text with an ellipsis so it fits in max_pixels."""
    if max_pixels <= 0 or font.measure(text) <= max_pixels:
        return text

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(text[:middle].rstrip() + "…") <= max_pixels:
            low = middle
        else:
            high = middle - 1

    return text[:low].rstrip() + "…" if low else "…"


class TimetableWidget:
    def __init__(self, root, events, student_name, progress=None, show=True):
        self.root = root
        self.my_progress = progress or []

        # In-app overlay panels (options, dialogs) and toast state
        self._overlays = []
        self.options_entry = None
        self._option_vars = []
        self.toast = None

        self.my_events = events
        self.my_name = student_name

        # Track active view data separately for friend timetable switching
        self.events = events
        self.student_name = student_name
        self.view_key = "me"

        # Settings (see settings.py). Read values anywhere with self.cfg["key"].
        self.cfg = load_config()
        self.sett_enabled = self.cfg.get("sett_enabled", True)
        self.friends_system_enabled = self.cfg.get("friends_system", True)
        self.time_format = bool(self.cfg.get("time_format", False))
        self.update_time_format_variables()

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

        # Determine greeting based on current time of day
        current_Date = datetime.now()
        current_time = current_Date.strftime("%p")
        self.greeting = "Good Morning," if current_time == "AM" else "Good Afternoon,"

        # Group timetable events by date
        self.grouped_days = self.get_grouped_days(self.view_key, events)
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
        if force or self._friends is None:
            self._friends = load_friends()
        return self._friends

    def get_grouped_days(self, view_key, events):
        # Parsing every event is wasted work when the same view is shown again
        key = (view_key, self.time_format)
        if key not in self._group_cache:
            self._group_cache[key] = self.process_events(events)
        return self._group_cache[key]

    def reload_days(self):
        # Rebuild the day list for the active view, staying on the same day if possible
        current_key = None
        if self.available_dates and self.current_index < len(self.available_dates):
            current_key = self.available_dates[self.current_index]

        self.grouped_days = self.get_grouped_days(self.view_key, self.events)
        self.available_dates = sorted(self.grouped_days.keys())

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

        self.prev_btn = ctk.CTkButton(nav_card, text="<< Previous Day", command=self.prev_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT, corner_radius=12, height=36, width=140)
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

        self.next_btn = ctk.CTkButton(nav_card, text="Next Day >>", command=self.next_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Bottom toolbar frame holding view switcher dropdown and options button side-by-side
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        self.bottom_frame = bottom_frame

        bottom_inner = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_inner.pack(expand=True, anchor="center")

        if self.friends_system_enabled:
            friend_data = self.get_friends()
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
                fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT,
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

        # Grades panel sits beneath the timetable
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

        if title_w < title_min:
            staff_floor = self.head_font.measure("Staff") + CELL_PADDING + 8
            give = min(title_min - title_w, max(0, staff_w - staff_floor))
            staff_w -= give
            title_w += give

        title_w = max(title_w, 60)
        return time_w, title_w, room_w, staff_w

    def render_rows(self):
        rows = self._current_rows
        widths = self.fit_columns(rows)
        time_w, title_w, room_w, staff_w = widths

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
        if not item or item not in self._row_full:
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

        current_key = self.available_dates[self.current_index]
        day_data = self.grouped_days[current_key]

        self.set_date_text(day_data["header"])

        self._current_rows = [
            (e["time"], e["title"], e["room"], e["staff"]) for e in day_data["events"]
        ]
        self.render_rows()

        self.update_nav_buttons(
            self.current_index > 0,
            self.current_index < len(self.available_dates) - 1
        )

    def set_date_text(self, text):
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
    # Grades panel
    # ------------------------------------------------------------------

    def build_progress_card(self):
        # Grades panel: one course at a time, chosen with a button per course
        self.course_blocks = {}
        self.course_buttons = []
        self.active_course = None
        self._bar_width = 0
        self._button_pos = {}
        self._bar_job = None

        if not self.my_progress:
            return

        card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.table_card)
        self.progress_card = card

        self.course_bar = ctk.CTkFrame(card, fg_color="transparent")
        self.course_bar.pack(fill=tk.X, padx=14, pady=(8, 0))

        self.course_title = ctk.CTkLabel(
            self.course_bar, text="Current Grades", font=("Arial", 12, "bold"), text_color=FG_ACCENT
        )
        self.course_title.grid(row=0, column=0, padx=(2, 10), pady=2, sticky="w")

        names = unique_short_names([course.get("title") for course in self.my_progress])
        for index, name in enumerate(names):
            button = ctk.CTkButton(
                self.course_bar, text=name,
                font=("Arial", 11, "bold"), height=24, corner_radius=12,
                width=10, border_spacing=6,
                fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT,
                command=lambda i=index: self.show_course(i)
            )
            self.course_buttons.append(button)

        self.course_area = ctk.CTkFrame(card, fg_color="transparent")
        self.course_area.pack(fill=tk.X, padx=4, pady=(0, 6))

        self.root.update_idletasks()
        self.layout_course_buttons()
        self.course_bar.bind("<Configure>", self.on_bar_configure)

        self.show_course(0)

        # Build every course now (this runs while the splash screen is up) so
        # switching courses later never has to draw anything
        for index in range(len(self.my_progress)):
            self.get_course_block(index)

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

            if in_row > 0 and used + needed > width:
                row, column, used, in_row = row + 1, 0, 0, 0

            position = (row, column)
            if self._button_pos.get(index) != position:
                button.grid(row=row, column=column, padx=3, pady=2, sticky="w")
                self._button_pos[index] = position

            used += needed
            column += 1
            in_row += 1

    def on_bar_configure(self, event):
        if event.width == self._bar_width:
            return
        if self._bar_job is not None:
            self.root.after_cancel(self._bar_job)
        self._bar_job = self.root.after(80, self.relayout_buttons)

    def relayout_buttons(self):
        self._bar_job = None
        self.layout_course_buttons()

    def get_course_block(self, index):
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
        scale = pick_grade_scale(target, grade)

        block = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=10)

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
    # Timetable data
    # ------------------------------------------------------------------

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
            self.view_key = "me"
        else:
            friend_name = choice.replace("Friend: ", "").strip()
            friend_data = self.get_friends()
            if friend_name in friend_data:
                self.student_name = friend_name
                self.events = friend_data[friend_name]
                self.view_key = f"friend:{friend_name}"

        self.grouped_days = self.get_grouped_days(self.view_key, self.events)
        self.available_dates = sorted(list(self.grouped_days.keys()))
        self.current_index = 0

        self.welcome_label.configure(text=f"{self.greeting} {self.student_name}")
        self.set_progress_visible(choice == "My Timetable")
        self.update_display()

    # ------------------------------------------------------------------
    # In-app overlays: panels and dialogs are drawn inside the main window
    # ------------------------------------------------------------------

    def push_overlay(self, width, close_on_click=False, on_close=None):
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

        styles = {
            "primary": (FG_ACCENT, ACCENT_HOVER, BG_DARK),
            "danger": (DANGER, DANGER_HOVER, BG_DARK),
            "secondary": (BG_HOVER, BUTTON_HOVER, FG_TEXT),
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
    # Options panel (built from settings.py)
    # ------------------------------------------------------------------

    def option_visible(self, requires):
        return not requires or bool(self.cfg.get(requires))

    def collect_option_sections(self):
        # Group visible settings and actions by section, in display order
        sections = {}

        for setting in SETTINGS:
            if setting.hidden or not self.option_visible(setting.requires):
                continue
            sections.setdefault(setting.section, {"settings": [], "actions": []})["settings"].append(setting)

        for action in ACTIONS:
            if not self.option_visible(action.requires):
                continue
            sections.setdefault(action.section, {"settings": [], "actions": []})["actions"].append(action)

        for name in SECTION_ORDER:
            if hasattr(self, self.extra_method_name(name)):
                sections.setdefault(name, {"settings": [], "actions": []})

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
        ctk.CTkButton(
            card, text="Done", command=self.close_options_menu,
            fg_color=FG_ACCENT, hover_color=ACCENT_HOVER, text_color=BG_DARK,
            font=("Arial", 12, "bold"), corner_radius=12, height=36
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 18))

        for name, content in self.collect_option_sections():
            heading = ctk.CTkLabel(
                card, text=name.upper(), font=("Arial", 10, "bold"), text_color=FG_SUBTEXT
            )
            heading.pack(anchor="w", padx=24, pady=(10, 4))

            drew = bool(content["settings"] or content["actions"])

            for setting in content["settings"]:
                self.add_setting_row(card, setting)

            for action in content["actions"]:
                handler = getattr(self, action.handler, None)
                if handler is None:
                    print(f"[!] Options action '{action.id}' has no method '{action.handler}'")
                    continue
                ctk.CTkButton(
                    card, text=action.label, command=handler, font=("Arial", 12, "bold"),
                    fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT,
                    corner_radius=12, height=36
                ).pack(fill=tk.X, padx=20, pady=(0, 8))

            extra = getattr(self, self.extra_method_name(name), None)
            if extra is not None and extra(card):
                drew = True

            if not drew:
                heading.destroy()

    def add_setting_row(self, card, setting):
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
        self.time_format = bool(value)
        self.update_time_format_variables()
        self.reload_days()
        self.update_display()

    def options_extra_friends(self, parent):
        # Remove-friend row; drawn under the Friends actions
        if not self.friends_system_enabled:
            return False

        friend_data = self.get_friends()
        if not friend_data:
            return False

        remove_row = ctk.CTkFrame(parent, fg_color="transparent")
        remove_row.pack(fill=tk.X, padx=20, pady=(0, 4))

        friend_names = list(friend_data.keys())
        del_var = tk.StringVar(value=friend_names[0])
        self._option_vars.append(del_var)
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

        friend_data = self.get_friends(force=True)
        self._group_cache = {key: value for key, value in self._group_cache.items() if key[0] == "me"}

        view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data.keys()]
        self.view_dropdown.configure(values=view_options)

        current = self.view_var.get()
        if current not in view_options:
            self.view_var.set("My Timetable")
            self.switch_timetable_view("My Timetable")
        elif current != "My Timetable":
            # The friend on screen may have just been re-imported
            self.switch_timetable_view(current)