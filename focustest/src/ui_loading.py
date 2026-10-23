import sys
import os
import platform
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from src.constants import CURRENT_OS, ICON_FILE, BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT, FG_GREEN
from src.scraper import load_cached_timetable, save_cached_timetable, fetch_timetable_data
from src.ui_timetable import TimetableWidget

def apply_app_icon(root):
    if os.path.exists(ICON_FILE):
        try:
            if CURRENT_OS == "Windows":
                root.iconbitmap(ICON_FILE)
            else:
                app_icon = tk.PhotoImage(file=ICON_FILE)
                root.iconphoto(True, app_icon)
        except Exception:
            pass

class FocusFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"FocusFinder {CURRENT_OS}")
        self.root.geometry("780x580")
        self.root.minsize(680, 680)
        self.root.configure(fg_color=BG_DARK)

        apply_app_icon(self.root)
        self.msg_queue = queue.Queue()

        self.setup_loading_screen()
        self.root.after(100, self.process_queue)

        self.worker_thread = threading.Thread(target=self.bg_fetch_pipeline, daemon=True)
        self.worker_thread.start()

    def setup_loading_screen(self):
        self.loading_frame = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)
        self.loading_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        header_card = ctk.CTkFrame(self.loading_frame, fg_color=BG_CARD, corner_radius=16)
        header_card.pack(fill=tk.X, pady=(0, 15), ipadx=15, ipady=12)

        title_label = ctk.CTkLabel(header_card, text="FocusFinder", font=("Arial", 22, "bold"), text_color=FG_TEXT)
        title_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.status_var = tk.StringVar(value="Initializing background engine...")
        self.status_label = ctk.CTkLabel(header_card, textvariable=self.status_var, font=("Arial", 12, "italic"), text_color=FG_SUBTEXT)
        self.status_label.pack(anchor="w", padx=15, pady=(2, 10))

        self.progress = ctk.CTkProgressBar(self.loading_frame, mode="indeterminate", progress_color=FG_ACCENT, fg_color=BG_SURFACE, corner_radius=8, height=12)
        self.progress.pack(fill=tk.X, pady=(0, 15))
        self.progress.start()

        log_card = ctk.CTkFrame(self.loading_frame, fg_color=BG_CARD, corner_radius=16)
        log_card.pack(fill=tk.BOTH, expand=True, ipadx=15, ipady=15)

        log_heading = ctk.CTkLabel(log_card, text="Activity Log:", font=("Arial", 11, "bold"), text_color=FG_ACCENT)
        log_heading.pack(anchor="w", padx=15, pady=(10, 6))

        self.log_box = ctk.CTkTextbox(log_card, fg_color=BG_SURFACE, text_color=FG_GREEN, font=("Consolas", 11), corner_radius=12, border_width=1, border_color=BG_HOVER)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    def gui_log(self, text, status_update=None):
        print(text, flush=True)
        self.msg_queue.put(("LOG", text))
        if status_update:
            self.msg_queue.put(("STATUS", status_update))

    def run_cmd_with_logging(self, cmd_list, description):
        self.gui_log(f"[*] {description}...")
        try:
            process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in iter(process.stdout.readline, ''):
                clean_line = line.rstrip()
                if clean_line:
                    self.gui_log(f"    {clean_line}")
            process.stdout.close()
            return_code = process.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, cmd_list)
        except Exception as e:
            self.gui_log(f"[!] Warning during '{description}': {e}")

    def process_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "LOG":
                    self.log_box.insert(tk.END, content + "\n")
                    self.log_box.see(tk.END)
                elif msg_type == "STATUS":
                    self.status_var.set(content)
                elif msg_type == "DONE":
                    events, student_name = content
                    self.transition_to_timetable(events, student_name)
                    return
                elif msg_type == "ERROR":
                    self.progress.stop()
                    self.status_var.set("Error encountered.")
                    messagebox.showerror("Error", content)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def bg_fetch_pipeline(self):
        try:
            self.gui_log(f"[*] Detected Operating System: {CURRENT_OS} ({platform.release()})")
            self.gui_log("[*] Checking for weekly cached timetable...")
            cache_result = load_cached_timetable()
            
            if cache_result:
                cached_events, student_name = cache_result
                self.gui_log(f"[+] Loaded {len(cached_events)} events from weekly cache!", "Cache loaded successfully!")
                self.msg_queue.put(("DONE", (cached_events, student_name)))
                return

            self.gui_log("[*] No valid cache for this week. Connecting to portal...")
            try:
                import playwright
            except ImportError:
                self.run_cmd_with_logging([sys.executable, "-m", "pip", "install", "playwright"], "Installing 'playwright'")

            from playwright.sync_api import sync_playwright

            if CURRENT_OS == "Linux" and (os.path.exists("/usr/bin/apt-get") or os.path.exists("/bin/apt-get")):
                self.run_cmd_with_logging([sys.executable, "-m", "playwright", "install-deps", "chromium"], "Checking Debian/Ubuntu browser dependencies")

            self.run_cmd_with_logging([sys.executable, "-m", "playwright", "install", "chromium"], "Ensuring Playwright Chromium binaries")
            self.gui_log("[*] Environment checks complete.\n", "Environment verified.")

            result = fetch_timetable_data(sync_playwright, self.gui_log)
            if not result:
                self.msg_queue.put(("ERROR", "No timetable events could be retrieved."))
            else:
                events, student_name = result
                save_cached_timetable(events, student_name)
                self.msg_queue.put(("DONE", (events, student_name)))
        except Exception as e:
            self.msg_queue.put(("ERROR", f"An error occurred: {str(e)}"))

    def transition_to_timetable(self, events, student_name):
        self.progress.stop()
        self.loading_frame.destroy()
        self.timetable_ui = TimetableWidget(self.root, events, student_name)