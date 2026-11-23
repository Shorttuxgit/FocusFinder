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

    # System-level DPI awareness: the window is scaled once for the main display
    # and never re-laid-out when dragged between monitors. Per-monitor awareness
    # (CustomTkinter's default) rebuilds every widget during the drag, which is
    # what makes the window stutter.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

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

def configure_dpi_scaling():
    """Scale the interface once, at the system DPI, and stop CustomTkinter
    from re-scaling whenever the window crosses between displays."""

    if sys.platform != "win32":
        return

    ctk.deactivate_automatic_dpi_awareness()

    try:
        scale = ctypes.windll.user32.GetDpiForSystem() / 96
    except (AttributeError, OSError):
        scale = 1.0

    ctk.set_widget_scaling(scale)
    ctk.set_window_scaling(scale)


if __name__ == "__main__":
    configure_dpi_scaling()
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk(className="focusfinder")

    app = FocusFinderApp(root)

    root.mainloop()