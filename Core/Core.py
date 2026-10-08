import sys
import subprocess
import os

def ensure_dependencies():
    """Checks for required packages and Playwright browser binaries, installing them if missing."""
    restarted_flag = "--restarted" in sys.argv
    installed_new = False

    # 1. Check and install missing Python packages
    try:
        import playwright
    except ImportError:
        print("[*] Package 'playwright' not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        installed_new = True

    # 2. Ensure Playwright Chromium browser binary is installed
    print("[*] Checking Playwright Chromium browser binary...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("[*] Chromium binary check complete.\n")
    except Exception as e:
        print(f"[!] Warning: Could not verify Playwright Chromium binaries: {e}")

    # Automatically restart Python process if new dependencies were installed
    if installed_new and not restarted_flag:
        print("[*] Restarting script process to initialize dependencies cleanly...\n")
        sys.argv.append("--restarted")
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Run dependency check before importing Playwright
ensure_dependencies()

# Standard Library Imports
import json
from datetime import datetime

# Third-Party Imports
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


def display_timetable(events):
    """Deduplicates, sorts, and prints timetable events in formatted terminal tables."""
    if not events:
        print("No timetable events found.")
        return

    unique_events = {ev.get("id", idx): ev for idx, ev in enumerate(events)}
    sorted_events = sorted(unique_events.values(), key=lambda x: str(x.get("start", "")))

    grouped_days = {}
    for ev in sorted_events:
        start_raw = str(ev.get("start", ""))
        end_raw = str(ev.get("end", ""))

        try:
            clean_start = start_raw.split(".")[0].replace("T", " ")
            clean_end = end_raw.split(".")[0].replace("T", " ")

            dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

            day_header = dt_start.strftime("%A, %d %B %Y")
            time_str = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
        except ValueError:
            day_header = "Unscheduled / Other"
            time_str = f"{start_raw} - {end_raw}"

        title = ev.get("title") or "N/A"
        room = ev.get("room") or ev.get("extendedProps", {}).get("room") or "—"
        staff = ev.get("staff") or ev.get("extendedProps", {}).get("staff") or "—"

        room = str(room).strip() if str(room).strip() else "—"
        staff = str(staff).strip() if str(staff).strip() else "—"

        grouped_days.setdefault(day_header, []).append({
            "time": time_str,
            "title": title,
            "room": room,
            "staff": staff
        })

    print("\n" + "=" * 70)
    print("                     WEEKLY TIMETABLE                     ")
    print("=" * 70)

    for day, day_events in grouped_days.items():
        print(f"\n--- {day} " + "-" * max(0, (65 - len(day))))
        print(f"{'Time':<17} | {'Event Title':<28} | {'Room':<8} | {'Staff'}")
        print("-" * 70)
        for e in day_events:
            print(f"{e['time']:<17} | {e['title'][:28]:<28} | {e['room']:<8} | {e['staff']}")


def perform_login(p):
    """Launches interactive browser for authentication and closes window immediately upon login."""
    print("\n" + "=" * 60)
    print("  ACTION REQUIRED: Complete login in the browser window.")
    print("  (Window will close automatically as soon as login succeeds)")
    print("=" * 60)

    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(BASE_URL)

    # Detect when user completes Google/SSO login and redirects back to Barton portal
    try:
        page.wait_for_url(
            lambda url: "focus.barton.ac.uk" in url.lower() and "login" not in url.lower() and "google.com" not in url.lower(),
            timeout=120000
        )
        page.wait_for_timeout(1500) # Brief pause for auth cookies to settle
    except Exception:
        input("\n>>> Press [ENTER] in this terminal once you have logged in... ")

    context.storage_state(path=SESSION_FILE)
    print("\n[+] Login detected! Session saved to session.json.")
    print("[+] Closing interactive browser window...\n")
    browser.close()


def fetch_timetable(p):
    """Loads saved session in headless mode and fetches timetable data."""
    print("Fetching timetable in headless mode...")
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

    # Detect if saved session has expired
    if "login" in page.url.lower() or "google.com" in page.url.lower():
        print("[!] Saved session has expired.")
        browser.close()
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        return None

    try:
        page.wait_for_selector("#powerCalendar", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    events = extract_events(livewire_responses)

    if not events:
        print("Network capture missed payload. Reading directly from page memory...")
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


def run():
    with sync_playwright() as p:
        # Prompt for login if no saved session exists
        if not os.path.exists(SESSION_FILE):
            perform_login(p)

        events = fetch_timetable(p)

        # Re-authenticate if session was expired
        if events is None:
            perform_login(p)
            events = fetch_timetable(p)

        if events is not None:
            display_timetable(events)


if __name__ == "__main__":
    run()
