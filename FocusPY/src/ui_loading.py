import sys
import os
import platform
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from FocusPY.src.constants import CURRENT_OS, ICON_FILE, BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT, FG_GREEN
from FocusPY.src.scraper import load_cached_timetable, save_cached_timetable, fetch_timetable_data
from FocusPY.src.ui_timetable import TimetableWidget
from FocusPY.src.window_utils import get_monitor_bounds, centre_geometry

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
        self.root.resizable(False, False)
        self.center_window(400, 400)
        self.root.configure(fg_color=BG_DARK)

        apply_app_icon(self.root)
        self.msg_queue = queue.Queue()

        self.setup_loading_screen()
        self.root.after(100, self.process_queue)

        self.worker_thread = threading.Thread(target=self.bg_fetch_pipeline, daemon=True)
        self.worker_thread.start()

    def center_window(self, width, height, around=None):
        # Size the window and centre it on one monitor (DPI-aware).
        # `around` is a screen point; the monitor containing it is used, or the
        # one under the mouse pointer when not given.
        self.root.update_idletasks()
        self._target = None

        scale = 1.0
        try:
            scale = self.root._get_window_scaling()
        except Exception:
            pass

        bounds = get_monitor_bounds(self.root, around)

        if bounds is None:
            if around is None:
                # Monitors can't be detected: only size it and let the window manager place it
                self.root.geometry(f"{width}x{height}")
                return

            # Grow around the point instead, which keeps the window on the same screen
            x = max(0, int(around[0] - width * scale / 2))
            y = max(0, int(around[1] - height * scale / 2))
        else:
            width, height, x, y = centre_geometry(bounds, width, height, scale)

        geometry = f"{width}x{height}+{x}+{y}"
        self.root.geometry(geometry)
        self._target = (geometry, x, y)

    def correct_position(self):
        # Some window managers move a window after it resizes; if this one did,
        # put it back where center_window meant it to go
        if not getattr(self, "_target", None):
            return

        geometry, x, y = self._target
        if abs(self.root.winfo_rootx() - x) > 60 or abs(self.root.winfo_rooty() - y) > 80:
            self.root.geometry(geometry)
            self.root.update()

    def setup_loading_screen(self):
        # Compact square splash: name in the middle, status line and a thin bar at the bottom
        self.loading_frame = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)
        self.loading_frame.pack(fill=tk.BOTH, expand=True)

        self.progress = ctk.CTkProgressBar(
            self.loading_frame, mode="determinate", progress_color=FG_ACCENT,
            fg_color=BG_CARD, corner_radius=0, height=4
        )
        self.progress.pack(side=tk.BOTTOM, fill=tk.X)
        self.progress.set(0)

        self.status_var = tk.StringVar(value="Starting up...")
        self.status_label = ctk.CTkLabel(
            self.loading_frame, textvariable=self.status_var, font=("Arial", 11),
            text_color=FG_SUBTEXT, wraplength=340
        )
        self.status_label.pack(side=tk.BOTTOM, pady=(0, 16))

        center = ctk.CTkFrame(self.loading_frame, fg_color="transparent")
        center.place(relx=0.5, rely=0.42, anchor="center")

        ctk.CTkLabel(
            center, text="FocusFinder", font=("Arial", 28, "bold"), text_color=FG_ACCENT
        ).pack()
        ctk.CTkLabel(
            center, text=f"for {CURRENT_OS}", font=("Arial", 11), text_color=FG_SUBTEXT
        ).pack(pady=(2, 0))

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
                    pass  # log lines still print to the console; the splash only shows status
                elif msg_type == "STATUS":
                    self.status_var.set(content)
                elif msg_type == "PROGRESS":
                    self.progress.set(max(0.0, min(1.0, content)))
                elif msg_type == "DONE":
                    events, student_name, progress = content
                    self.transition_to_timetable(events, student_name, progress)
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
            self.gui_log("[*] Checking for weekly cached timetable...", "Checking saved timetable...")
            self.msg_queue.put(("PROGRESS", 0.02))
            cache_result = load_cached_timetable()
            
            if cache_result:
                cached_events, student_name, progress = cache_result
                self.gui_log(f"[+] Loaded {len(cached_events)} events from weekly cache!", "Cache loaded successfully!")
                self.msg_queue.put(("PROGRESS", 1.0))
                self.msg_queue.put(("DONE", (cached_events, student_name, progress)))
                return

            self.gui_log("[*] No valid cache for this week. Connecting to portal...", "Preparing browser engine...")
            self.msg_queue.put(("PROGRESS", 0.04))
            try:
                import playwright
            except ImportError:
                self.run_cmd_with_logging([sys.executable, "-m", "pip", "install", "playwright"], "Installing 'playwright'")

            from playwright.sync_api import sync_playwright

            if CURRENT_OS == "Linux" and (os.path.exists("/usr/bin/apt-get") or os.path.exists("/bin/apt-get")):
                self.run_cmd_with_logging([sys.executable, "-m", "playwright", "install-deps", "chromium"], "Checking Debian/Ubuntu browser dependencies")

            self.run_cmd_with_logging([sys.executable, "-m", "playwright", "install", "chromium"], "Ensuring Playwright Chromium binaries")
            self.gui_log("[*] Environment checks complete.\n", "Environment verified.")
            self.msg_queue.put(("PROGRESS", 0.08))

            result = fetch_timetable_data(
                sync_playwright,
                self.gui_log,
                lambda fraction: self.msg_queue.put(("PROGRESS", fraction))
            )
            if not result:
                self.msg_queue.put(("ERROR", "No timetable events could be retrieved."))
            else:
                events, student_name, progress = result
                save_cached_timetable(events, student_name, progress)
                self.msg_queue.put(("PROGRESS", 1.0))
                self.msg_queue.put(("DONE", (events, student_name, progress)))
        except Exception as e:
            self.msg_queue.put(("ERROR", f"An error occurred: {str(e)}"))

    def hide_window(self):
        # Make the window invisible without unmapping it, so Tk can still lay
        # everything out at its real size. Falls back to withdrawing it.
        try:
            self.root.attributes("-alpha", 0.0)
            return "alpha"
        except tk.TclError:
            self.root.withdraw()
            return "withdraw"

    def reveal_window(self, mode):
        if mode == "alpha":
            self.root.attributes("-alpha", 1.0)
        else:
            self.root.deiconify()

    def transition_to_timetable(self, events, student_name, progress=None):
        # 1. Build the whole main window while the splash is still showing.
        #    It stays off screen until it is finished.
        self.status_var.set("Preparing your timetable...")
        self.root.update_idletasks()

        try:
            timetable = TimetableWidget(self.root, events, student_name, progress, show=False)
        except Exception as error:
            self.progress.stop()
            self.status_var.set("Error encountered.")
            messagebox.showerror("Error", f"Could not build the timetable: {error}")
            return

        # 2. Swap splash for main window while the window is invisible, so the
        #    resize, move and layout all happen before anyone can see them.
        self.root.update_idletasks()
        splash_centre = (
            self.root.winfo_rootx() + self.root.winfo_width() // 2,
            self.root.winfo_rooty() + self.root.winfo_height() // 2,
        )

        mode = self.hide_window()
        try:
            self.progress.stop()
            self.loading_frame.destroy()
            self.root.resizable(True, True)
            self.root.minsize(700, 600)
            self.center_window(820, 680, around=splash_centre)

            timetable.show()
            self.root.update()              # let Tk apply the new size and layout
            self.correct_position()         # undo any move the window manager made
            timetable.finalize_layout()     # settle anything that depends on real sizes
            self.root.update_idletasks()
        finally:
            self.reveal_window(mode)

        self.timetable_ui = timetable