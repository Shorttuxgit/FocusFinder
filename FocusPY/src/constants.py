# --------------------------------------------------
# Shared constants: paths, web address and colours
# --------------------------------------------------

import platform
from pathlib import Path

# Name of the operating system ("Windows", "Linux", ...)
CURRENT_OS = platform.system()

# Website the timetable is read from
BASE_URL = "https://focus.barton.ac.uk"

# PACKAGE_DIR is the FocusPY folder (where main.py lives).
# PROJECT_ROOT is the folder above it.
PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parent

# Saved data. Every file lives in PACKAGE_DIR no matter where the app is
# launched from, so the installer's backup / wipe logic always finds them.
SESSION_FILE = PACKAGE_DIR / "session.json"
CACHE_FILE = PACKAGE_DIR / "timetable_cache.json"
FRIENDS_FILE = PACKAGE_DIR / "friends_cache.json"
CONFIG_FILE = PACKAGE_DIR / "config.json"

# Older versions kept config.json in the folder above FocusPY.
# It is still read if the new file does not exist yet.
LEGACY_CONFIG_FILE = PROJECT_ROOT / "config.json"

# Window icon (.ico on Windows, .png elsewhere)
ICON_FILE = PACKAGE_DIR / ("icon.ico" if CURRENT_OS == "Windows" else "icon.png")

# --------------------------------------------------
# Colour themes
# --------------------------------------------------
#
# Each theme is a complete palette. apply_theme() copies the chosen one into
# this module, so the rest of the app just does:
#       from FocusPY.src.constants import BG_DARK, FG_TEXT, ...
#
# IMPORTANT: those imports take their value at the moment they run, so main.py
# calls apply_theme() BEFORE importing any user-interface module. Changing the
# theme later in the program has no effect until the app is restarted.
#
# Naming: BG_DARK is the main window background and BG_SURFACE the inset
# areas (table, grade panels), even in the light theme where they are pale.

DARK_THEME = {
    "BG_DARK": "#1e1e2e",         # window background
    "BG_SURFACE": "#181825",      # table card, grade panels, chart
    "BG_CARD": "#313244",         # cards and panels
    "BG_HOVER": "#45475a",        # buttons and borders
    "BUTTON_HOVER": "#585b70",    # button while the mouse is over it
    "FG_TEXT": "#cdd6f4",         # main text
    "FG_SUBTEXT": "#a6adc8",      # quieter text
    "FG_ACCENT": "#89b4fa",       # blue highlights
    "ACCENT_HOVER": "#74a0f0",    # blue button while the mouse is over it
    "FG_GREEN": "#a6e3a1",        # targets and good news
    "DANGER": "#f38ba8",          # errors, removals and falling grades
    "DANGER_HOVER": "#eba0ac",
    "ZEBRA_ROW": "#1d1d2c",       # every other table row
    "OVERLAY_BG": "#11111b",      # backdrop behind Options and dialogs
    "GRID_LINE": "#2a2b3c",       # chart grid lines
}

LIGHT_THEME = {
    "BG_DARK": "#eff1f5",
    "BG_SURFACE": "#ffffff",
    "BG_CARD": "#e4e7ee",
    "BG_HOVER": "#c9cdd9",
    "BUTTON_HOVER": "#b9bdcb",
    "FG_TEXT": "#3f4259",
    "FG_SUBTEXT": "#585b72",
    "FG_ACCENT": "#1a56d6",
    "ACCENT_HOVER": "#1448b8",
    "FG_GREEN": "#1f7316",
    "DANGER": "#c40e35",
    "DANGER_HOVER": "#a80c2d",
    "ZEBRA_ROW": "#f3f5f9",
    "OVERLAY_BG": "#ced2dc",
    "GRID_LINE": "#d5d9e3",
}


def apply_theme(light=False):
    """Make the light (True) or dark (False) palette the active one."""
    globals().update(LIGHT_THEME if light else DARK_THEME)


# Dark until main.py picks the theme from config.json
apply_theme(False)