import customtkinter as ctk
from src.ui_loading import FocusFinderApp

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk(className='focusfinder')
    app = FocusFinderApp(root)
    root.mainloop()