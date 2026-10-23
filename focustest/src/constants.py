import os
import platform

CURRENT_OS = platform.system()
BASE_URL = "https://focus.barton.ac.uk"

SESSION_FILE = "session.json"
CACHE_FILE = "timetable_cache.json"
ICON_FILE = "icon.ico" if CURRENT_OS == "Windows" else "icon.png"

# --- COLOR PALETTE ---
BG_DARK = "#1e1e2e"
BG_SURFACE = "#181825"
BG_CARD = "#313244"
BG_HOVER = "#45475a"
FG_TEXT = "#cdd6f4"
FG_SUBTEXT = "#a6adc8"
FG_ACCENT = "#89b4fa"
FG_GREEN = "#a6e3a1"