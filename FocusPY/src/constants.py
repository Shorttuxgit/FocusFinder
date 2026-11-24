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

# User interface colour palette
BG_DARK = "#1e1e2e"
BG_SURFACE = "#181825"
BG_CARD = "#313244"
BG_HOVER = "#45475a"
FG_TEXT = "#cdd6f4"
FG_SUBTEXT = "#a6adc8"
FG_ACCENT = "#89b4fa"
FG_GREEN = "#a6e3a1"