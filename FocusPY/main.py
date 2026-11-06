import sys
import ctypes
from pathlib import Path

# --------------------------------------------------
# Windows taskbar identity
# --------------------------------------------------

if sys.platform == "win32":
    APP_USER_MODEL_ID = "uk.shortclaws.focusfinder"

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        APP_USER_MODEL_ID
    )

# --------------------------------------------------
# Project setup
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import customtkinter as ctk
except ImportError:
    import pip
    pip.main(['install', 'customtkinter'])
    import customtkinter as ctk

from FocusPY.src.ui_loading import FocusFinderApp


# --------------------------------------------------
# Application entry point
# --------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk(className="focusfinder")

    app = FocusFinderApp(root)

    root.mainloop()