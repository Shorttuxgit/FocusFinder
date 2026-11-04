import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import customtkinter as ctk
except ImportError:
    import pip
    pip.main(['install', 'customtkinter'])
    import customtkinter as ctk
from FocusPY.src.ui_loading import FocusFinderApp


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk(className='focusfinder')
    app = FocusFinderApp(root)
    root.mainloop()
    #Run me!