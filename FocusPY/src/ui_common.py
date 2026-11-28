# --------------------------------------------------
# Standard buttons and dropdowns, so every screen looks the same
# --------------------------------------------------

import customtkinter as ctk

from FocusPY.src.constants import (
    BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, BUTTON_HOVER, FG_TEXT, FG_ACCENT,
    ACCENT_HOVER, DANGER, DANGER_HOVER,
)

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


def round_rect(canvas, x1, y1, x2, y2, radius, **options):
    """Draw a rounded rectangle on a canvas (options are passed to create_polygon)."""
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **options)