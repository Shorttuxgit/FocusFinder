import sys
import subprocess
import os
import platform
import json
from datetime import datetime, date

# --- OS & DEPENDENCY DETECTION ---
CURRENT_OS = platform.system()
print(f"[*] Detected Operating System: {CURRENT_OS} ({platform.release()})")

def ensure_dependencies():
    """Checks for OS-specific system requirements, Python packages, and browser binaries."""
    restarted_flag = "--restarted" in sys.argv
    installed_new = False

    # 1. Check Tkinter availability
    try:
        import tkinter
    except ImportError:
        print("\n[!] Error: 'tkinter' is missing.")
        if CURRENT_OS == "Linux":
            print("[*] It looks like you are on Linux. You can install it using your package manager:")
            print("    - Fedora/RHEL: sudo dnf install python3-tkinter")
            print("    - Debian/Ubuntu: sudo apt install python3-tk")
        else:
            print("[*] Please reinstall Python and ensure the 'tcl/tk and IDLE' option is checked.")
        sys.exit(1)

    # 2. Check and install missing Python packages
    try:
        import playwright
    except ImportError:
        print("[*] Package 'playwright' not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        installed_new = True

    # 3. Ensure Playwright browser binaries are installed safely based on distro
    print("[*] Checking Playwright Chromium binaries...")
    try:
        if CURRENT_OS == "Linux":
            if os.path.exists("/usr/bin/apt-get") or os.path.exists("/bin/apt-get"):
                print("[*] Debian/Ubuntu detected: Checking system-level browser dependencies...")
                subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], check=False)
            else:
                print("[*] Non-Debian Linux (Fedora/Arch/etc.) detected: Skipping apt dependency check.")

        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("[*] Chromium binary check complete.\n")
    except Exception as e:
        print(f"[!] Warning: Could not verify Playwright Chromium binaries: {e}")

    if installed_new and not restarted_flag:
        print("[*] Restarting script process to initialize dependencies cleanly...\n")
        sys.argv.append("--restarted")
        os.execv(sys.executable, [sys.executable] + sys.argv)

ensure_dependencies()

import tkinter as tk
from tkinter import messagebox, ttk
from playwright.sync_api import sync_playwright

SESSION_FILE = "session.json"
BASE_URL = "https://focus.barton.ac.uk"
TIMETABLE_URL = "https://focus.barton.ac.uk/student-focus/107025/timetable"


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


def perform_login(p):
    """Launches interactive browser for authentication."""
    print("\n" + "=" * 60)
    print("  ACTION REQUIRED: Complete login in the browser window.")
    print("  (Window will close automatically as soon as login succeeds)")
    print("=" * 60)

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
        input("\n>>> Press [ENTER] in this terminal once you have logged in... ")

    context.storage_state(path=SESSION_FILE)
    print("\n[+] Login detected! Session saved to session.json.")
    print("[+] Closing interactive browser window...\n")
    browser.close()


def fetch_timetable():
    """Loads saved session in headless mode and fetches timetable data."""
    print(f"Fetching timetable in headless mode on {CURRENT_OS}...")
    with sync_playwright() as p:
        if not os.path.exists(SESSION_FILE):
            perform_login(p)

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
        page.goto(TIMETABLE_URL)

        if "login" in page.url.lower() or "google.com" in page.url.lower():
            print("[!] Saved session has expired. Re-authenticating...")
            browser.close()
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            perform_login(p)
            return fetch_timetable()

        try:
            page.wait_for_selector("#powerCalendar", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        events = extract_events(livewire_responses)

        if not events:
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
        return events


class TimetableApp:
    def __init__(self, root, events):
        self.root = root
        self.root.title(f"FocusFinder ({CURRENT_OS})")
        self.root.geometry("650x450")
        
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

        self.create_widgets()
        self.update_display()

    def process_events(self, events):
        grouped = {}
        for idx, ev in enumerate(events):
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

    def create_widgets(self):
        nav_frame = tk.Frame(self.root, pady=10)
        nav_frame.pack(side=tk.TOP, fill=tk.X)

        self.prev_btn = tk.Button(nav_frame, text="<< Previous Day", command=self.prev_day, font=("Arial", 10, "bold"))
        self.prev_btn.pack(side=tk.LEFT, padx=20)

        self.date_label = tk.Label(nav_frame, text="", font=("Arial", 12, "bold"))
        self.date_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(nav_frame, text="Next Day >>", command=self.next_day, font=("Arial", 10, "bold"))
        self.next_btn.pack(side=tk.RIGHT, padx=20)

        table_frame = tk.Frame(self.root, padx=10, pady=10)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("Time", "Event Title", "Room", "Staff")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        
        self.tree.heading("Time", text="Time")
        self.tree.heading("Event Title", text="Event Title")
        self.tree.heading("Room", text="Room")
        self.tree.heading("Staff", text="Staff")

        self.tree.column("Time", width=130, anchor=tk.W)
        self.tree.column("Event Title", width=240, anchor=tk.W)
        self.tree.column("Room", width=80, anchor=tk.W)
        self.tree.column("Staff", width=120, anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        bottom_frame = tk.Frame(self.root, pady=10)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Fixed tk.BOTTOM instead of tk.bottom
        today_btn = tk.Button(bottom_frame, text="Jump to Today", command=self.jump_to_today)
        today_btn.pack(side=tk.BOTTOM)

    def update_display(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.available_dates:
            self.date_label.config(text="No Timetable Data Available")
            return

        current_key = self.available_dates[self.current_index]
        day_data = self.grouped_days[current_key]

        self.date_label.config(text=day_data["header"])

        for e in day_data["events"]:
            self.tree.insert("", tk.END, values=(e["time"], e["title"], e["room"], e["staff"]))

        self.prev_btn.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.current_index < len(self.available_dates) - 1 else tk.DISABLED)

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


def run():
    events = fetch_timetable()
    if not events:
        print("[!] No events could be retrieved.")
        return

    root = tk.Tk()
    app = TimetableApp(root, events)
    root.mainloop()


if __name__ == "__main__":
    run()