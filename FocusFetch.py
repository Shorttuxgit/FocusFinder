import sys
import subprocess
import os

def ensure_dependencies():
    """Checks for required packages and Playwright browser binaries, installing them if missing."""
    # 1. Install missing Python packages
    required_packages = ["playwright"]
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            print(f"[*] Package '{pkg}' not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

    # 2. Ensure Playwright Chromium browser binary is installed
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[!] Warning: Could not verify Playwright Chromium binaries: {e}")

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


def run():
    with sync_playwright() as p:
        has_session = os.path.exists(SESSION_FILE)
        browser = p.chromium.launch(headless=has_session)

        if has_session:
            print("Loading saved session...")
            context = browser.new_context(storage_state=SESSION_FILE)
        else:
            context = browser.new_context()

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

        page.goto(BASE_URL)
        page.wait_for_timeout(2000)

        if "login" in page.url.lower() or "google.com" in page.url.lower() or not has_session:
            print("\n" + "=" * 60)
            print("  ACTION REQUIRED: Complete the login in the browser window.")
            print("=" * 60)
            
            input("\n>>> Press [ENTER] in this terminal AFTER you have logged in... ")
            
            context.storage_state(path=SESSION_FILE)
            print("\nSession saved to session.json!\n")

        print("Fetching timetable page...")
        page.goto(TIMETABLE_URL)

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

        display_timetable(events)
        browser.close()


if __name__ == "__main__":
    run()
