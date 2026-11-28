# --------------------------------------------------
# The grades panel on the home page: one course at a time, chosen with a button
# per course. The details are drawn on a single canvas, which is much lighter
# than building widgets for every course, so switching course is quick even
# on a slow computer.
# --------------------------------------------------

import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk

from FocusPY.src.constants import (
    BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, BUTTON_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT,
    ACCENT_HOVER, FG_GREEN,
)
from FocusPY.src.course_names import unique_short_names
from FocusPY.src.grades import (
    COMMIT_SCALE, pick_scale, course_history, history_grades,
    resolve_grade_indices, plan_markers, normalise_commit,
)
from FocusPY.src.ui_common import fit_text, round_rect


class GradesPanel:
    def __init__(self, root, parent, courses, before):
        """`parent` holds the panel; the panel is packed just above `before`
        (the timetable table). `courses` is the list saved by the scraper."""
        self.root = root
        self.courses = courses
        self.before = before

        self.active = None          # which course is showing
        self._bar_width = 0
        self._button_pos = {}
        self._bar_job = None
        self._draw_job = None
        self._drawn_width = 0

        # Sizes below are multiplied by px so the panel is the right size on high-DPI screens
        self.px = max(1.0, root.winfo_fpixels("1i") / 96)

        self.title_font = tkfont.Font(root=root, family="Arial", size=11, weight="bold")
        self.text_font = tkfont.Font(root=root, family="Arial", size=10)
        self.small_font = tkfont.Font(root=root, family="Arial", size=9)

        self.card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=16)
        self.card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=before)

        self.build_buttons()
        self.build_canvas()

        self.root.update_idletasks()
        self.layout_buttons()
        self.select(0)

    # ------------------------------------------------------------------
    # Building the panel
    # ------------------------------------------------------------------

    def build_buttons(self):
        # Top row: title plus one button per course
        self.bar = ctk.CTkFrame(self.card, fg_color="transparent")
        self.bar.pack(fill=tk.X, padx=14, pady=(8, 0))

        self.heading = ctk.CTkLabel(
            self.bar, text="Current Grades", font=("Arial", 12, "bold"), text_color=FG_ACCENT
        )
        self.heading.grid(row=0, column=0, padx=(2, 10), pady=2, sticky="w")

        self.buttons = []
        names = unique_short_names([course.get("title") for course in self.courses])
        for index, name in enumerate(names):
            self.buttons.append(ctk.CTkButton(
                self.bar, text=name,
                font=("Arial", 11, "bold"), height=24, corner_radius=12,
                width=10, border_spacing=6,
                fg_color=BG_HOVER, hover_color=BUTTON_HOVER, text_color=FG_TEXT,
                command=lambda i=index: self.select(i)
            ))

        self.bar.bind("<Configure>", self.on_bar_configure)

    def build_canvas(self):
        # Heights are worked out from the fonts so text is never cut off
        px = self.px
        self.title_h = self.title_font.metrics("linespace")
        self.text_h = self.text_font.metrics("linespace")
        self.small_h = self.small_font.metrics("linespace")

        self.circle = 20 * px
        top_block = max(self.title_h + self.text_h + px, self.circle + 2 * px + self.small_h)
        self.ladder_top = 8 * px + top_block + 6 * px
        self.cell_h = 24 * px
        height = self.ladder_top + self.cell_h + 3 * px + self.small_h + 8 * px

        self.canvas = tk.Canvas(
            self.card, bg=BG_CARD, highlightthickness=0, bd=0, height=int(height)
        )
        self.canvas.pack(fill=tk.X, padx=14, pady=(4, 10))
        self.canvas.bind("<Configure>", self.on_canvas_configure)

    # ------------------------------------------------------------------
    # Showing, hiding and layout
    # ------------------------------------------------------------------

    def set_visible(self, visible):
        # Grades belong to the logged-in student, so hide them on friends' timetables
        if visible:
            self.card.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), before=self.before)
        else:
            self.card.pack_forget()

    def finalize(self):
        # Called once the window is at its final size, before it is shown
        if self._bar_job is not None:
            self.root.after_cancel(self._bar_job)
            self._bar_job = None

        self.layout_buttons()
        self.draw()

    def layout_buttons(self):
        # Flow the course buttons onto extra rows when they don't fit on one line
        width = self.bar.winfo_width()
        if width <= 1:
            width = max(300, self.root.winfo_width() - 60)
        self._bar_width = width

        used = self.heading.winfo_reqwidth() + 14
        row, column, in_row = 0, 1, 1

        for index, button in enumerate(self.buttons):
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
        self.layout_buttons()

    def on_canvas_configure(self, event):
        # Redraw once a width change settles
        if event.width == self._drawn_width:
            return
        if self._draw_job is not None:
            self.root.after_cancel(self._draw_job)
        self._draw_job = self.root.after(60, self.draw)

    # ------------------------------------------------------------------
    # Choosing a course
    # ------------------------------------------------------------------

    def style_button(self, index, active):
        self.buttons[index].configure(
            fg_color=FG_ACCENT if active else BG_HOVER,
            hover_color=ACCENT_HOVER if active else BUTTON_HOVER,
            text_color=BG_DARK if active else FG_TEXT
        )

    def select(self, index):
        if index == self.active:
            return

        if self.active is not None:
            self.style_button(self.active, False)
        self.style_button(index, True)

        self.active = index
        self.draw()

    # ------------------------------------------------------------------
    # Drawing the selected course
    # ------------------------------------------------------------------

    def draw(self):
        self._draw_job = None
        canvas = self.canvas
        width = canvas.winfo_width()
        if width < 120 or self.active is None:
            return      # not laid out yet; the resize event will draw it

        self._drawn_width = width
        canvas.delete("all")
        px = self.px

        course = self.courses[self.active]
        grade = course.get("grade", "")
        target = course.get("ttg", "")
        commit = normalise_commit(course.get("commit", ""))
        scale = pick_scale(course.get("title"), history_grades(course_history(course)))

        height = canvas.winfo_height()
        round_rect(canvas, 0, 0, width - 1, height - 1, 10 * px, fill=BG_SURFACE, outline="")

        # Right: commitment circles with a caption underneath
        gap = 2 * px
        circles_w = len(COMMIT_SCALE) * self.circle + (len(COMMIT_SCALE) - 1) * gap
        left_of_circles = width - 12 * px - circles_w
        for n, value in enumerate(COMMIT_SCALE):
            x = left_of_circles + n * (self.circle + gap)
            active = value == commit
            canvas.create_oval(
                x, 8 * px, x + self.circle, 8 * px + self.circle,
                fill=FG_ACCENT if active else BG_CARD, outline=""
            )
            canvas.create_text(
                x + self.circle / 2, 8 * px + self.circle / 2, text=value,
                fill=BG_DARK if active else FG_SUBTEXT, font=("Arial", 10, "bold")
            )
        canvas.create_text(
            left_of_circles + circles_w / 2, 8 * px + self.circle + 2 * px, text="Commitment",
            anchor="n", fill=FG_SUBTEXT, font=("Arial", 9)
        )

        # Left: course title and "Current / Target" summary
        text_width = left_of_circles - 24 * px
        canvas.create_text(
            12 * px, 8 * px, anchor="nw", fill=FG_TEXT, font=("Arial", 11, "bold"),
            text=fit_text(self.title_font, course.get("title", "Course"), text_width)
        )
        canvas.create_text(
            12 * px, 8 * px + self.title_h + px, anchor="nw", fill=FG_SUBTEXT, font=("Arial", 10),
            text=fit_text(self.text_font, f"Current: {grade or '—'}   •   Target: {target or '—'}", text_width)
        )

        # No recognised grade scale: nothing more to draw
        if not scale:
            return

        self.draw_ladder(scale, grade, target, width)

    def draw_ladder(self, scale, grade, target, width):
        canvas = self.canvas
        px = self.px

        now_idxs = resolve_grade_indices(scale, grade)
        target_idxs = resolve_grade_indices(scale, target)
        target_idx = target_idxs[0] if target_idxs else None
        now_start = min(now_idxs) if now_idxs else None

        # One box per grade, side by side across the panel
        left, right, gap = 10 * px, width - 10 * px, 2 * px
        cell_w = (right - left - gap * (len(scale) - 1)) / len(scale)
        top, bottom = self.ladder_top, self.ladder_top + self.cell_h

        def cell_x(i):
            return left + i * (cell_w + gap)

        for i, label in enumerate(scale):
            x1, x2 = cell_x(i), cell_x(i) + cell_w

            # Current grade is blue, grades below it are grey, grades above are dim
            if i in now_idxs:
                fill, text_color = FG_ACCENT, BG_DARK
            elif now_start is not None and i < now_start:
                fill, text_color = BG_HOVER, FG_TEXT
            else:
                fill, text_color = BG_CARD, FG_SUBTEXT

            # The target grade gets a green outline
            if i == target_idx:
                round_rect(canvas, x1, top, x2, bottom, 7 * px, fill=FG_GREEN, outline="")
                round_rect(canvas, x1 + 2 * px, top + 2 * px, x2 - 2 * px, bottom - 2 * px, 5 * px,
                           fill=fill, outline="")
            else:
                round_rect(canvas, x1, top, x2, bottom, 6 * px, fill=fill, outline="")

            canvas.create_text((x1 + x2) / 2, (top + bottom) / 2, text=label,
                               fill=text_color, font=("Arial", 10, "bold"))

        # "Now" and "Target" labels share one line under the ladder
        colours = {"now": FG_ACCENT, "target": FG_GREEN}
        for text, kind, column, span in plan_markers(now_idxs, target_idx):
            middle = (cell_x(column) + cell_x(column + span - 1) + cell_w) / 2
            canvas.create_text(middle, bottom + 3 * px, text=text, anchor="n",
                               fill=colours[kind], font=("Arial", 9, "bold"))