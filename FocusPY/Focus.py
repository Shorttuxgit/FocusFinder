#!/bin/python3
import datetime
import sys
import subprocess
import os
import platform
import json
import threading
import queue
from datetime import datetime, date, timedelta

sett_enabled = False
weather_enabled = False
autoupdate = False
version_number = 0
profile_enabled = False
time_format = False # False for 24 hour True for 12 hour


if time_format == True:
    formats = "%I"
    isPOM = "%p"  
    isPOMenable = "Enabled" 
else:
    formats = "%H"
    isPOM = ""
    isPOMenable = "Disabled" 


current_hour = datetime.now().hour
greeting = ""

if current_hour < 12:
    greeting = "Good Morning,"
else:
    greeting = "Good Afternoon,"


# --- OS DETECTION ---
CURRENT_OS = platform.system()

# --- INITIAL TKINTER CHECK ---
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    print("\n[!] Error: 'tkinter' is missing from your Python installation.")
    sys.exit(1)

# Auto-ensure CustomTkinter for rounded UI components
try:
    import customtkinter as ctk
except ImportError:
    print("[*] Installing 'customtkinter' for rounded UI elements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

# Configure CustomTkinter Dark Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

SESSION_FILE = "session.json"
CACHE_FILE = "timetable_cache.json"
ICON_FILE = "icon.png"
BASE_URL = "https://barton.ac.uk"

# --- COLOR PALETTE ---
BG_DARK = "#1e1e2e"
BG_SURFACE = "#181825"
BG_CARD = "#313244"
BG_HOVER = "#45475a"
FG_TEXT = "#cdd6f4"
FG_SUBTEXT = "#a6adc8"
FG_ACCENT = "#89b4fa"
FG_GREEN = "#a6e3a1"


def apply_app_icon(root):
    """Loads icon.png onto the window if available."""
    if os.path.exists(ICON_FILE):
        try:
            app_icon = tk.PhotoImage(file=ICON_FILE)
            root.iconphoto(True, app_icon)
        except Exception:
            pass


def get_current_week_sunday():
    """Calculates the date of the Sunday commencing the current week."""
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    return sunday.strftime("%Y-%m-%d")


def load_cached_timetable():
    """Loads cached timetable if it belongs to the current week commencing Sunday."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if data.get("week_commencing") == get_current_week_sunday():
                return data.get("events", []), data.get("student_name", "Student")
    except Exception:
        pass
    return None


def save_cached_timetable(events, student_name):
    """Saves fetched timetable events and student name along with the current week commencing Sunday."""
    try:
        data = {
            "week_commencing": get_current_week_sunday(),
            "student_name": student_name,
            "events": events
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Could not save timetable cache: {e}")


def extract_events(livewire_responses):
    """Parses Livewire response payloads and extracts dispatched timetable events."""
    events = []
    for resp in livewire_responses:
        components = resp if isinstance(resp, list) else resp.get("components", [])
        for comp in components:
            if not isinstance(comp, dict):
                continue
            dispatches = comp.get("effects", {}).get("dispatches", [])
            for dispatch in dispatches:
                if dispatch.get("name") == "event-changed":
                    evt_list = dispatch.get("params", {}).get("events", [])
                    events.extend(evt_list)
    return events


class FocusFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"FocusFinder {CURRENT_OS}")
        self.root.geometry("780x580")
        self.root.minsize(680, 680)
        self.root.configure(fg_color=BG_DARK)

        apply_app_icon(self.root)

        # Queue for thread-safe UI updates
        self.msg_queue = queue.Queue()

        # Build initial Loading & Logging Screen
        self.setup_loading_screen()
        
        # Start monitoring the queue for log messages
        self.root.after(100, self.process_queue)

        # Launch background fetching worker thread
        self.worker_thread = threading.Thread(target=self.bg_fetch_pipeline, daemon=True)
        self.worker_thread.start()

    def setup_loading_screen(self):
        """Creates the initial status, animation, and logging GUI with rounded cards."""
        self.loading_frame = ctk.CTkFrame(
            self.root,
            fg_color=BG_DARK,
            corner_radius=0
        )
        self.loading_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title Card (Rounded Container)
        header_card = ctk.CTkFrame(
            self.loading_frame,
            fg_color=BG_CARD,
            corner_radius=16
        )
        header_card.pack(fill=tk.X, pady=(0, 15), ipadx=15, ipady=12)

        # Inner container splitting headers left/right
        text_frame = ctk.CTkFrame(header_card, fg_color="transparent")
        text_frame.pack(side=tk.LEFT, fill=tk.Y)

        title_label = ctk.CTkLabel(
            text_frame,
            text="FocusFinder",
            font=("Arial", 22, "bold"),
            text_color=FG_TEXT
        )
        title_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.status_var = tk.StringVar(value="Initializing background engine...")
        self.status_label = ctk.CTkLabel(
            text_frame,
            textvariable=self.status_var,
            font=("Arial", 12, "italic"),
            text_color=FG_SUBTEXT
        )
        self.status_label.pack(anchor="w", padx=15, pady=(2, 10))

        # POM Interactive Toggle Button placed cleanly on the right
        self.pom_button = ctk.CTkButton(
            header_card,
            text="Time Format: 24H" if not time_format else "Time Format: 12H (POM)",
            command=self.toggle_time_format,
            fg_color=BG_SURFACE,
            hover_color=BG_HOVER,
            border_width=1,
            border_color=FG_ACCENT,
            text_color=FG_TEXT,
            corner_radius=8,
            width=160
        )
        self.pom_button.pack(side=tk.RIGHT, anchor="c", padx=15, pady=10)

        # Animated Progress Bar (Rounded)
        self.progress = ctk.CTkProgressBar(
            self.loading_frame,
            mode="indeterminate",
            progress_color=FG_ACCENT,
            fg_color=BG_SURFACE,
            corner_radius=8,
            height=12
        )
        self.progress.pack(fill=tk.X, pady=(0, 15))
        self.progress.start()

        # Log Card Container (Rounded)
        log_card = ctk.CTkFrame(
            self.loading_frame,
            fg_color=BG_CARD,
            corner_radius=16
        )
        log_card.pack(fill=tk.BOTH, expand=True, ipadx=15, ipady=15)

        log_heading = ctk.CTkLabel(
            log_card,
            text="Activity Log:",
            font=("Arial", 11, "bold"),
            text_color=FG_ACCENT
        )
        log_heading.pack(anchor="w", padx=15, pady=(10, 6))

        # Console Text Output Box (Rounded Corners)
        self.log_box = ctk.CTkTextbox(
            log_card,
            fg_color=BG_SURFACE,
            text_color=FG_GREEN,
            font=("Consolas", 11),
            corner_radius=12,
            border_width=1,
            border_color=BG_HOVER
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    def toggle_time_format(self):
        """Toggles state engine runtime parameters for 12/24 hour display options."""
        global time_format, formats, isPOM, isPOMenable
        time_format = not time_format
        
        if time_format:
            formats = "%I"
            isPOM = "%p"
            isPOMenable = "Enabled"
            self.pom_button.configure(text="Time Format: 12H (POM)")
        else:
            formats = "%H"
            isPOM = ""
            isPOMenable = "Disabled"
            self.pom_button.configure(text="Time Format: 24H")
            
        self.gui_log(f"[*] Time format updated. POM mode is now {isPOMenable}.")

    def gui_log(self, text, status_update=None):
        """Thread-safe log dispatcher that prints live output to terminal AND the GUI."""
        print(text, flush=True)  # Terminal output
        self.msg_queue.put(("LOG", text))
        if status_update:
            self.msg_queue.put(("STATUS", status_update))

    def process_queue(self):
        """Processes messages arriving inside the thread queue to modify the GUI layout dynamically."""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "LOG":
                    self.log_box.insert(tk.END, f"{data}\n")
                    self.log_box.see(tk.END)
                elif msg_type == "STATUS":
                    self.status_var.set(data)
                self.msg_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def run_cmd_with_logging(cmd_list, description):
        """Executes a command and streams its output live to both terminal and GUI."""
        # Unused stub method context based on input snippet closure sequence
        pass

    def bg_fetch_pipeline(self):
        """Background initialization worker thread placeholder logic."""
        self.gui_log("[*] Background fetch pipeline operational.")


if __name__ == "__main__":
    root = ctk.CTk()
    app = FocusFinderApp(root)
    root.mainloop()
