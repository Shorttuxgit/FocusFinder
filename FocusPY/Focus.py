#!/bin/python3
import sys
import subprocess
import os
import platform
import json
import threading
import queue
from datetime import datetime, date

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
ICON_FILE = "icon.png"
BASE_URL = "https://focus.barton.ac.uk"
TIMETABLE_URL = "https://focus.barton.ac.uk/student-focus/107025/timetable"

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
        self.root.title(f"FocusFinder ({CURRENT_OS})")
        self.root.geometry("780x550")
        self.root.minsize(680, 480)
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

        title_label = ctk.CTkLabel(
            header_card,
            text="FocusFinder",
            font=("Arial", 22, "bold"),
            text_color=FG_TEXT
        )
        title_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.status_var = tk.StringVar(value="Initializing background engine...")
        self.status_label = ctk.CTkLabel(
            header_card,
            textvariable=self.status_var,
            font=("Arial", 12, "italic"),
            text_color=FG_SUBTEXT
        )
        self.status_label.pack(anchor="w", padx=15, pady=(2, 10))

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

    def gui_log(self, text, status_update=None):
        """Thread-safe log dispatcher that prints live output to terminal AND the GUI."""
        print(text, flush=True)  # Terminal output
        self.msg_queue.put(("LOG", text))
        if status_update:
            self.msg_queue.put(("STATUS", status_update))

    def run_cmd_with_logging(self, cmd_list, description):
        """Executes a command and streams its output live to both terminal and GUI."""
        self.gui_log(f"[*] {description}...")
        try:
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
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
        """Processes pending log messages and UI updates on the main thread."""
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "LOG":
                    self.log_box.insert(tk.END, content + "\n")
                    self.log_box.see(tk.END)
                elif msg_type == "STATUS":
                    self.status_var.set(content)
                elif msg_type == "DONE":
                    self.transition_to_timetable(content)
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
        """Background pipeline for environment checks, login, and data fetch."""
        try:
            self.gui_log(f"[*] Detected Operating System: {CURRENT_OS} ({platform.release()})")
            
            # 1. Dependency Verification with Live Terminal Streams
            try:
                import playwright
            except ImportError:
                self.run_cmd_with_logging(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    "Installing 'playwright' via pip"
                )

            from playwright.sync_api import sync_playwright

            if CURRENT_OS == "Linux":
                if os.path.exists("/usr/bin/apt-get") or os.path.exists("/bin/apt-get"):
                    self.run_cmd_with_logging(
                        [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                        "Checking Debian/Ubuntu browser system dependencies"
                    )

            self.run_cmd_with_logging(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                "Ensuring Playwright Chromium binaries"
            )
            self.gui_log("[*] Environment checks complete.\n", "Environment verified.")

            # 2. Timetable Fetching
            events = self.fetch_timetable_data(sync_playwright)

            if not events:
                self.msg_queue.put(("ERROR", "No timetable events could be retrieved."))
            else:
                self.msg_queue.put(("DONE", events))

        except Exception as e:
            self.msg_queue.put(("ERROR", f"An error occurred: {str(e)}"))

    def perform_login(self, p):
        """Launches interactive browser for authentication."""
        self.gui_log("\n" + "=" * 50, "Authentication Required")
        self.gui_log("ACTION REQUIRED: Complete login in the browser window.")
        self.gui_log("=" * 50 + "\n")

        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL)

        try:
            page.wait_for_url(
                lambda url: "focus.barton.ac.uk" in url.lower() and "login" not in url.lower() and "google.com" not in url.lower(),
                timeout=120000
            )
            page.wait_for_timeout(1500)
        except Exception:
            self.gui_log("[!] Waiting for user to complete login in browser...")

        context.storage_state(path=SESSION_FILE)
        self.gui_log("[+] Login detected! Session saved.")
        self.gui_log("[+] Closing interactive browser...\n")
        browser.close()

    def fetch_timetable_data(self, sync_playwright_fn):
        """Runs headless Playwright automation to intercept calendar responses."""
        self.gui_log("[*] Launching browser engine...", "Connecting to Focus portal...")

        with sync_playwright_fn() as p:
            if not os.path.exists(SESSION_FILE):
                self.perform_login(p)

            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=SESSION_FILE)
            page = context.new_page()

            livewire_responses = []

            def handle_response(response):
                if "livewire" in response.url or "message" in response.url:
                    try:
                        data = response.json()
                        if data:
                            livewire_responses.append(data)
                    except Exception:
                        pass

            page.on("response", handle_response)
            self.gui_log(f"[*] Navigating to timetable URL: {TIMETABLE_URL}", "Fetching timetable data...")
            page.goto(TIMETABLE_URL)

            if "login" in page.url.lower() or "google.com" in page.url.lower():
                self.gui_log("[!] Session expired. Re-authenticating...")
                browser.close()
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                return self.fetch_timetable_data(sync_playwright_fn)

            try:
                page.wait_for_selector("#powerCalendar", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            self.gui_log("[*] Parsing Livewire schedule payload...", "Processing schedule...")
            events = extract_events(livewire_responses)

            if not events:
                self.gui_log("[*] Secondary fallback extraction via JS context...")
                events = page.evaluate("""() => {
                    try {
                        if (window.calendar) {
                            return window.calendar.getEvents().map(e => e.toPlainObject());
                        }
                        const comp = window.Livewire?.components?.getComponentsByName('full-calendar.full-calendar')[0];
                        if (comp) {
                            return comp.ephemeral?.events || comp.canonical?.events || comp.snapshot?.memo?.data?.events || [];
                        }
                    } catch (err) {
                        return [];
                    }
                    return [];
                }""") or []

            browser.close()
            self.gui_log(f"[+] Success! Extracted {len(events)} schedule items.", "Data ready!")
            return events

    def transition_to_timetable(self, events):
        """Destroys the loading UI and renders the interactive Timetable widget."""
        self.progress.stop()
        self.loading_frame.destroy()

        # Render Main Timetable View
        self.timetable_ui = TimetableWidget(self.root, events)


class TimetableWidget:
    """Fully Rounded Dark Themed Timetable View Widget."""
    def __init__(self, root, events):
        self.root = root
        self.events = events
        self.grouped_days = self.process_events(events)
        self.available_dates = sorted(list(self.grouped_days.keys()))

        self.current_index = 0
        today_str = date.today().strftime("%Y-%m-%d")

        for idx, d_str in enumerate(self.available_dates):
            if d_str == today_str:
                self.current_index = idx
                break
            elif d_str > today_str:
                self.current_index = max(0, idx - 1)
                break

        self.configure_styles()
        self.create_widgets()
        self.update_display()

    def configure_styles(self):
        """Configures TTK treeview colors inside the rounded container."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=BG_SURFACE,
            foreground=FG_TEXT,
            fieldbackground=BG_SURFACE,
            bordercolor=BG_DARK,
            rowheight=34,
            font=("Arial", 10)
        )
        style.map(
            "Treeview",
            background=[("selected", BG_HOVER)],
            foreground=[("selected", FG_TEXT)]
        )

        style.configure(
            "Treeview.Heading",
            background=BG_CARD,
            foreground=FG_ACCENT,
            bordercolor=BG_DARK,
            font=("Arial", 10, "bold")
        )

        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=BG_CARD,
            darkcolor=BG_DARK,
            lightcolor=BG_DARK,
            troughcolor=BG_SURFACE,
            bordercolor=BG_DARK,
            arrowcolor=FG_TEXT
        )

    def create_widgets(self):
        self.main_container = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # --- TOP NAVIGATION BAR (Rounded Card) ---
        nav_card = ctk.CTkFrame(
            self.main_container,
            fg_color=BG_CARD,
            corner_radius=16
        )
        nav_card.pack(fill=tk.X, pady=(0, 15), ipadx=12, ipady=10)

        self.prev_btn = ctk.CTkButton(
            nav_card,
            text="<< Previous Day",
            command=self.prev_day,
            font=("Arial", 12, "bold"),
            fg_color=BG_HOVER,
            hover_color="#585b70",
            text_color=FG_TEXT,
            corner_radius=12,
            height=36,
            width=140
        )
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.date_label = ctk.CTkLabel(
            nav_card,
            text="",
            font=("Arial", 14, "bold"),
            text_color=FG_TEXT
        )
        self.date_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = ctk.CTkButton(
            nav_card,
            text="Next Day >>",
            command=self.next_day,
            font=("Arial", 12, "bold"),
            fg_color=BG_HOVER,
            hover_color="#585b70",
            text_color=FG_TEXT,
            corner_radius=12,
            height=36,
            width=140
        )
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # --- TABLE CONTAINER (Rounded Outer Box) ---
        table_card = ctk.CTkFrame(
            self.main_container,
            fg_color=BG_SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=BG_HOVER
        )
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        columns = ("Time", "Event Title", "Room", "Staff")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")

        self.tree.heading("Time", text="Time")
        self.tree.heading("Event Title", text="Event Title")
        self.tree.heading("Room", text="Room")
        self.tree.heading("Staff", text="Staff")

        self.tree.column("Time", width=120, anchor=tk.W)
        self.tree.column("Event Title", width=260, anchor=tk.W)
        self.tree.column("Room", width=80, anchor=tk.W)
        self.tree.column("Staff", width=140, anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 12), pady=12)

        # --- BOTTOM ACTION BAR ---
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color=BG_DARK)
        bottom_frame.pack(fill=tk.X)

        today_btn = ctk.CTkButton(
            bottom_frame,
            text="Jump to Today",
            command=self.jump_to_today,
            font=("Arial", 12, "bold"),
            fg_color=FG_ACCENT,
            hover_color="#b4befe",
            text_color=BG_DARK,
            corner_radius=20,
            height=40,
            width=160
        )
        today_btn.pack(side=tk.BOTTOM)

    def process_events(self, events):
        grouped = {}
        for ev in events:
            start_raw = str(ev.get("start", ""))
            end_raw = str(ev.get("end", ""))

            try:
                clean_start = start_raw.split(".")[0].replace("T", " ")
                clean_end = end_raw.split(".")[0].replace("T", " ")

                dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
                dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

                day_key = dt_start.strftime("%Y-%m-%d")
                day_header = dt_start.strftime("%A, %d %B %Y")
                time_str = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
            except ValueError:
                dt_start = datetime.min
                day_key = "9999-99-99"
                day_header = "Unscheduled / Other"
                time_str = f"{start_raw} - {end_raw}"

            title = ev.get("title") or "N/A"
            room = ev.get("room") or ev.get("extendedProps", {}).get("room") or "—"
            staff = ev.get("staff") or ev.get("extendedProps", {}).get("staff") or "—"

            room = str(room).strip() if str(room).strip() else "—"
            staff = str(staff).strip() if str(staff).strip() else "—"

            if day_key not in grouped:
                grouped[day_key] = {"header": day_header, "events": []}

            grouped[day_key]["events"].append({
                "dt_start": dt_start,
                "time": time_str,
                "title": title,
                "room": room,
                "staff": staff
            })

        for day_key in grouped:
            grouped[day_key]["events"].sort(key=lambda x: x["dt_start"])

        return grouped

    def update_display(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.available_dates:
            self.date_label.configure(text="No Timetable Data Available")
            return

        current_key = self.available_dates[self.current_index]
        day_data = self.grouped_days[current_key]

        self.date_label.configure(text=day_data["header"])

        for e in day_data["events"]:
            self.tree.insert("", tk.END, values=(e["time"], e["title"], e["room"], e["staff"]))

        has_prev = self.current_index > 0
        has_next = self.current_index < len(self.available_dates) - 1

        self.prev_btn.configure(
            state="normal" if has_prev else "disabled",
            fg_color=BG_HOVER if has_prev else BG_SURFACE,
            text_color=FG_TEXT if has_prev else FG_SUBTEXT
        )
        self.next_btn.configure(
            state="normal" if has_next else "disabled",
            fg_color=BG_HOVER if has_next else BG_SURFACE,
            text_color=FG_TEXT if has_next else FG_SUBTEXT
        )

    def prev_day(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def next_day(self):
        if self.current_index < len(self.available_dates) - 1:
            self.current_index += 1
            self.update_display()

    def jump_to_today(self):
        today_str = date.today().strftime("%Y-%m-%d")
        found = False
        for idx, d_str in enumerate(self.available_dates):
            if d_str == today_str:
                self.current_index = idx
                found = True
                break

        if found:
            self.update_display()
        else:
            messagebox.showinfo("Info", "Time to Relax! No Lessons Today!!")


if __name__ == "__main__":
    root = ctk.CTk()
    app = FocusFinderApp(root)
    root.mainloop()
