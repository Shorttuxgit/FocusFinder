# --------------------------------------------------
# The Progress view: a course's grade history as a chart
# --------------------------------------------------
#
# Nothing in this file runs at start-up. ui_timetable.py creates a ProgressView
# the first time the Progress button is pressed, and each course is only drawn
# when it is selected.

import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk

from FocusPY.src.constants import (
    BG_SURFACE, BG_CARD, FG_TEXT, FG_SUBTEXT, FG_ACCENT, FG_GREEN, DANGER, ZEBRA_ROW, GRID_LINE,
)
from FocusPY.src.course_names import unique_short_names
from FocusPY.src.grades import (
    pick_scale, resolve_grade_index, course_history, history_grades,
    summarise_history, normalise_commit,
)
from FocusPY.src.ui_common import make_dropdown


class ProgressView:
    def __init__(self, root, parent, courses):
        """`parent` is the main window area the page is shown in; `courses` is
        the list of grade records saved by the scraper."""
        self.root = root
        self.courses = courses

        self.index = 0              # which course is selected
        self.visible = False        # only draw while the page is on screen
        self._redraw_job = None

        # Font used for the grade names and for measuring text
        self.axis_font = tkfont.Font(root=root, family="Arial", size=10, weight="bold")

        # The page itself. It is not packed here: show() and hide() do that.
        self.page = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)

        self.build_header()
        self.build_summary()
        self.build_chart_card()
        self.update_summary()

    # ------------------------------------------------------------------
    # Showing and hiding
    # ------------------------------------------------------------------

    def show(self):
        self.page.pack(fill=tk.BOTH, expand=True)
        self.visible = True

        # Draw once the page has a size (the chart also redraws whenever it is resized)
        self.root.after_idle(self.draw)

    def hide(self):
        self.page.pack_forget()
        self.visible = False

    # ------------------------------------------------------------------
    # Building the page
    # ------------------------------------------------------------------

    def build_header(self):
        # Header card: title on the left, course picker on the right
        header = ctk.CTkFrame(self.page, fg_color=BG_CARD, corner_radius=16)
        header.pack(fill=tk.X, pady=(0, 10), ipady=2)

        ctk.CTkLabel(
            header, text="Progress", font=("Arial", 18, "bold"), text_color=FG_ACCENT
        ).pack(side=tk.LEFT, padx=(18, 12), pady=8)

        self.names = unique_short_names([course.get("title") for course in self.courses])
        make_dropdown(
            header, self.names, command=self.on_course_selected, width=280
        ).pack(side=tk.RIGHT, padx=(0, 14), pady=8)

    def build_summary(self):
        # Four summary boxes: current grade, change, target, commitment
        summary = ctk.CTkFrame(self.page, fg_color="transparent")
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

    def build_chart_card(self):
        # Chart card: course title and legend on top, the chart underneath
        card = ctk.CTkFrame(self.page, fg_color=BG_SURFACE, corner_radius=16)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill=tk.X, padx=16, pady=(12, 0))

        ctk.CTkLabel(top, text="◆ Target", font=("Arial", 11, "bold"), text_color=FG_GREEN).pack(side=tk.RIGHT)
        ctk.CTkLabel(top, text="● Grade    ", font=("Arial", 11, "bold"), text_color=FG_ACCENT).pack(side=tk.RIGHT)

        self.title_label = ctk.CTkLabel(
            top, text="", font=("Arial", 13, "bold"), text_color=FG_TEXT, anchor="w"
        )
        self.title_label.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(card, bg=BG_SURFACE, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 10))
        self.canvas.bind("<Configure>", self.on_resize)

    # ------------------------------------------------------------------
    # Reacting to the person
    # ------------------------------------------------------------------

    def on_course_selected(self, name):
        # A different course was picked in the header
        self.index = self.names.index(name)
        self.update_summary()
        self.draw()

    def on_resize(self, _event):
        # Redraw once a resize settles
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(60, self.draw)

    # ------------------------------------------------------------------
    # Summary boxes
    # ------------------------------------------------------------------

    def set_chip(self, key, value, sub, value_color, sub_color=FG_SUBTEXT):
        value_label, sub_label = self.chips[key]
        value_label.configure(text=value, text_color=value_color)
        sub_label.configure(text=sub, text_color=sub_color)

    def update_summary(self):
        # Fill the four boxes and the chart title for the selected course
        course = self.courses[self.index]
        points = course_history(course)
        scale = pick_scale(course.get("title"), history_grades(points))

        self.title_label.configure(text=course.get("title", "Course"))

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

    # ------------------------------------------------------------------
    # The chart
    # ------------------------------------------------------------------

    def draw(self):
        # Line chart of the selected course: one point per recorded grade (blue
        # line) with the target set at each point (green diamonds), labelled
        # with the Focus code (e.g. SAS1) and period underneath.
        self._redraw_job = None
        if not self.visible:
            return

        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 150 or height < 150:
            return      # not laid out yet; the resize event will draw it

        course = self.courses[self.index]
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
        line_h = self.axis_font.metrics("linespace")
        label_font = ("Arial", 10, "bold")
        small_font = ("Arial", 9)

        # Plot area: grade names on the left, three lines of labels underneath
        rows = len(scale)
        left = max(self.axis_font.measure(name) for name in scale) + 24 * px
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
            canvas.create_line(left, y, width - right, y, fill=GRID_LINE)
            canvas.create_text(left - 12 * px, y, text=name, anchor="e", fill=FG_SUBTEXT, font=label_font)

        # A faint guide line down from every point to its label
        for i in range(count):
            canvas.create_line(x_of(i), top_row - 14 * px, x_of(i), axis_y, fill=GRID_LINE, dash=(2, 4))

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