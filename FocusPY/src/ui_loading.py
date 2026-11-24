# --------------------------------------------------
# Start-up: optional splash screen, then the timetable window
# --------------------------------------------------

import sys
import os
import platform
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from FocusPY.src.constants import CURRENT_OS, ICON_FILE, BG_DARK, BG_CARD, FG_SUBTEXT, FG_ACCENT
from FocusPY.src.config_manager import load_config
from FocusPY.src.scraper import load_cached_timetable, save_cached_timetable, fetch_timetable_data
from FocusPY.src.ui_timetable import TimetableWidget
from FocusPY.src.window_utils import get_monitor_bounds, centre_geometry

# Size of the main window (CustomTkinter units)
MAIN_SIZE = (820, 680)
MAIN_MIN_SIZE = (700, 600)

# Text in a Playwright error that means "the browser is not installed yet"
BROWSER_MISSING_HINTS = ("Executable doesn't exist", "playwright install")


def apply_app_icon(root):
    # Put the app icon on the window (silently skipped if the file is missing)
    if not os.path.exists(ICON_FILE):
        return

    try:
        if CURRENT_OS == "Windows":
            root.iconbitmap(str(ICON_FILE))
        else:
            root.iconphoto(True, tk.PhotoImage(file=str(ICON_FILE)))
    except Exception:
        pass


class FocusFinderApp:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.msg_queue = queue.Queue()

        self.loading_frame = None
        self.timetable_ui = None
        self._target = None

        self.root.title(f"FocusFinder {CURRENT_OS}")
        self.root.configure(fg_color=BG_DARK)
        apply_app_icon(self.root)

        # This week's saved timetable, if there is one. Reading it is a quick
        # file read, so it is done here rather than in the background.
        cached = load_cached_timetable(need_progress=self.cfg["progress_system"])

        # Splash screen off + saved timetable: open straight to the timetable.
        # (With no saved timetable the splash is always shown, because a
        # download follows and the person needs to see what is happening.)
        if cached and not self.cfg["splash_screen"]:
            if self.open_without_splash(cached):
                return
            cached = None   # building failed, so download fresh data behind the splash

        self.start_splash(cached)

    # ------------------------------------------------------------------
    # Window placement
    # ------------------------------------------------------------------

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
        if not self._target:
            return

        geometry, x, y = self._target
        if abs(self.root.winfo_rootx() - x) > 60 or abs(self.root.winfo_rooty() - y) > 80:
            self.root.geometry(geometry)
            self.root.update()

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

    # ------------------------------------------------------------------
    # Splash screen
    # ------------------------------------------------------------------

    def start_splash(self, cached):
        # Show the splash and start the background work (cache hand-over or download)
        self.root.resizable(False, False)
        self.center_window(400, 400)
        self.setup_loading_screen()
        self.root.after(100, self.process_queue)

        threading.Thread(target=self.bg_fetch_pipeline, args=(cached,), daemon=True).start()

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
        ctk.CTkLabel(
            self.loading_frame, textvariable=self.status_var, font=("Arial", 11),
            text_color=FG_SUBTEXT, wraplength=340
        ).pack(side=tk.BOTTOM, pady=(0, 16))

        center = ctk.CTkFrame(self.loading_frame, fg_color="transparent")
        center.place(relx=0.5, rely=0.42, anchor="center")

        ctk.CTkLabel(
            center, text="FocusFinder", font=("Arial", 28, "bold"), text_color=FG_ACCENT
        ).pack()
        ctk.CTkLabel(
            center, text=f"for {CURRENT_OS}", font=("Arial", 11), text_color=FG_SUBTEXT
        ).pack(pady=(2, 0))

    # ------------------------------------------------------------------
    # Background work (runs on a second thread; talks to the window via msg_queue)
    # ------------------------------------------------------------------

    def gui_log(self, text, status_update=None):
        # Console log line, plus an optional status message for the splash
        print(text, flush=True)
        if status_update:
            self.msg_queue.put(("STATUS", status_update))

    def run_cmd_with_logging(self, cmd_list, description):
        # Run a command and echo its output to the console
        self.gui_log(f"[*] {description}...")
        try:
            process = subprocess.Popen(
                cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in process.stdout:
                if line.strip():
                    self.gui_log(f"    {line.rstrip()}")
            process.stdout.close()

            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd_list)
        except Exception as error:
            self.gui_log(f"[!] Warning during '{description}': {error}")

    def install_browser(self):
        # Download the Chromium browser Playwright drives (only done when it is missing)
        on_debian = os.path.exists("/usr/bin/apt-get") or os.path.exists("/bin/apt-get")
        if CURRENT_OS == "Linux" and on_debian:
            self.run_cmd_with_logging(
                [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                "Checking Debian/Ubuntu browser dependencies"
            )

        self.run_cmd_with_logging(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            "Installing Playwright Chromium"
        )

    def download_timetable(self, sync_playwright):
        # Download everything; if the browser turns out to be missing, install it and retry once
        def fetch():
            return fetch_timetable_data(
                sync_playwright,
                self.gui_log,
                lambda fraction: self.msg_queue.put(("PROGRESS", fraction)),
                fetch_grades=self.cfg["progress_system"],
            )

        try:
            return fetch()
        except Exception as error:
            if not any(hint in str(error) for hint in BROWSER_MISSING_HINTS):
                raise

        self.msg_queue.put(("STATUS", "Installing browser engine..."))
        self.install_browser()
        return fetch()

    def bg_fetch_pipeline(self, cached):
        try:
            # A saved timetable was already loaded: just hand it over
            if cached:
                events, student_name, progress = cached
                self.gui_log(
                    f"[+] Loaded {len(events)} events from weekly cache!",
                    "Cache loaded successfully!"
                )
                self.msg_queue.put(("PROGRESS", 1.0))
                self.msg_queue.put(("DONE", cached))
                return

            # Otherwise download a new timetable
            self.gui_log(f"[*] Detected Operating System: {CURRENT_OS} ({platform.release()})")
            self.gui_log(
                "[*] No valid cache for this week. Connecting to portal...",
                "Preparing browser engine..."
            )
            self.msg_queue.put(("PROGRESS", 0.04))

            # Playwright is installed automatically the first time it is needed
            try:
                import playwright  # noqa: F401
            except ImportError:
                self.run_cmd_with_logging(
                    [sys.executable, "-m", "pip", "install", "playwright"], "Installing 'playwright'"
                )

            from playwright.sync_api import sync_playwright

            self.msg_queue.put(("PROGRESS", 0.08))
            result = self.download_timetable(sync_playwright)

            if not result:
                self.msg_queue.put(("ERROR", "No timetable events could be retrieved."))
                return

            events, student_name, progress = result
            save_cached_timetable(
                events, student_name, progress, has_progress=self.cfg["progress_system"]
            )
            self.msg_queue.put(("PROGRESS", 1.0))
            self.msg_queue.put(("DONE", result))

        except Exception as error:
            self.msg_queue.put(("ERROR", f"An error occurred: {error}"))

    def process_queue(self):
        # Runs every 100 ms on the main thread and applies messages from the worker
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()

                if msg_type == "STATUS":
                    self.status_var.set(content)

                elif msg_type == "PROGRESS":
                    self.progress.set(max(0.0, min(1.0, content)))

                elif msg_type == "DONE":
                    self.finish_splash(*content)
                    return

                elif msg_type == "ERROR":
                    self.progress.stop()
                    self.status_var.set("Error encountered.")
                    messagebox.showerror("Error", content)
                    return

        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    # ------------------------------------------------------------------
    # Showing the timetable
    # ------------------------------------------------------------------

    def show_timetable(self, events, student_name, progress, around=None):
        """Build the main window and swap it in. Raises if it cannot be built."""
        # 1. Build everything while it is still hidden (or behind the splash)
        timetable = TimetableWidget(self.root, events, student_name, progress, show=False)

        # 2. Swap splash for main window while the window is invisible, so the
        #    resize, move and layout all happen before anyone can see them
        mode = self.hide_window()
        try:
            if self.loading_frame is not None:
                self.progress.stop()
                self.loading_frame.destroy()
                self.loading_frame = None

            self.root.resizable(True, True)
            self.root.minsize(*MAIN_MIN_SIZE)
            self.center_window(*MAIN_SIZE, around=around)

            timetable.show()
            self.root.update()              # let Tk apply the new size and layout
            self.correct_position()         # undo any move the window manager made
            timetable.finalize_layout()     # settle anything that depends on real sizes
            self.root.update_idletasks()
        finally:
            self.reveal_window(mode)

        self.timetable_ui = timetable

    def finish_splash(self, events, student_name, progress):
        # Called when the splash has its data: replace the splash with the timetable
        self.status_var.set("Preparing your timetable...")
        self.root.update_idletasks()

        # Open the main window on the same screen the splash was on
        splash_centre = (
            self.root.winfo_rootx() + self.root.winfo_width() // 2,
            self.root.winfo_rooty() + self.root.winfo_height() // 2,
        )

        try:
            self.show_timetable(events, student_name, progress, around=splash_centre)
        except Exception as error:
            self.progress.stop()
            self.status_var.set("Error encountered.")
            messagebox.showerror("Error", f"Could not build the timetable: {error}")

    def open_without_splash(self, cached):
        # Splash is switched off: build the window invisibly and show it finished.
        # Returns False if the timetable could not be built.
        mode = self.hide_window()
        try:
            self.show_timetable(*cached)
            return True
        except Exception as error:
            print(f"[!] Could not open the saved timetable: {error}")
            self.reveal_window(mode)
            return False