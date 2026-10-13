#!/bin/python3
import sys
import subprocess
import os

def log_debug(category, message, details=None):
    """Helper function to print detailed diagnostic logs for every part of the program."""
    print(f"[DEBUG][{category.upper()}] {message}")
    if details is not None:
        print(f"         ↳ Details: {details}")

def ensure_dependencies():
    """Checks for required packages and Playwright browser binaries, installing them if missing."""
    log_debug("deps", "Starting dependency verification check.")
    restarted_flag = "--restarted" in sys.argv
    installed_new = False
    log_debug("deps", f"sys.argv: {sys.argv}, restarted_flag: {restarted_flag}")

    # 1. Check and install missing Python packages
    try:
        import playwright
        log_debug("deps", "Package 'playwright' is already installed.")
    except ImportError:
        log_debug("deps", "Package 'playwright' NOT found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        installed_new = True

    # 2. Ensure Playwright Chromium browser binary is installed
    log_debug("deps", "Checking Playwright Chromium browser binary...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        log_debug("deps", "Chromium binary check complete.")
    except Exception as e:
        log_debug("deps", f"Warning during Chromium binary check: {e}")

    # Automatically restart Python process if new dependencies were installed
    if installed_new and not restarted_flag:
        log_debug("deps", "New dependencies installed. Restarting process...")
        sys.argv.append("--restarted")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    log_debug("deps", "Dependency verification complete.")

# Run dependency check before importing Playwright
ensure_dependencies()

# Standard Library Imports
import json
from datetime import datetime, date, timedelta

# Third-Party Imports
from playwright.sync_api import sync_playwright

SESSION_FILE = "session.json"
CACHE_FILE = "timetable_cache.json"
BASE_URL = "https://focus.barton.ac.uk"

log_debug("config", f"Configuration loaded. SESSION_FILE={SESSION_FILE}, CACHE_FILE={CACHE_FILE}, BASE_URL={BASE_URL}")


def get_current_week_sunday():
    """Calculates the date of the Sunday commencing the current week."""
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    sunday_str = sunday.strftime("%Y-%m-%d")
    log_debug("date", f"Calculated current week commencing Sunday: {sunday_str} (today: {today}, weekday: {today.weekday()})")
    return sunday_str


def load_cached_timetable():
    """Loads cached timetable if it belongs to the current week commencing Sunday."""
    log_debug("cache", f"Checking if cache file exists: {CACHE_FILE}")
    if not os.path.exists(CACHE_FILE):
        log_debug("cache", "Cache file does not exist.")
        return None
    try:
        log_debug("cache", "Opening cache file for reading...")
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            cached_sunday = data.get("week_commencing")
            current_sunday = get_current_week_sunday()
            log_debug("cache", f"Cache week_commencing: {cached_sunday} | Current week commencing Sunday: {current_sunday}")
            if cached_sunday == current_sunday:
                events = data.get("events", [])
                log_debug("cache", f"Cache is valid! Loaded {len(events)} events.")
                return events
            else:
                log_debug("cache", "Cache is outdated (week mismatch). Ignoring cache.")
    except Exception as e:
        log_debug("cache", f"Error reading cache file: {e}")
    return None


def save_cached_timetable(events):
    """Saves fetched timetable events along with the current week commencing Sunday."""
    log_debug("cache", f"Attempting to save {len(events)} events to cache file: {CACHE_FILE}")
    try:
        current_sunday = get_current_week_sunday()
        data = {
            "week_commencing": current_sunday,
            "events": events
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        log_debug("cache", f"Successfully saved cache for week commencing {current_sunday}.")
    except Exception as e:
        log_debug("cache", f"Warning: Could not save timetable cache: {e}")


def extract_events(livewire_responses):
    """Parses Livewire response payloads and extracts dispatched timetable events."""
    log_debug("livewire", f"Parsing {len(livewire_responses)} livewire response payloads...")
    events = []
    for idx, resp in enumerate(livewire_responses):
        components = resp if isinstance(resp, list) else resp.get("components", [])
        log_debug("livewire", f"Response packet {idx}: found {len(components)} components.")
        for comp in components:
            if not isinstance(comp, dict):
                continue
            dispatches = comp.get("effects", {}).get("dispatches", [])
            for dispatch in dispatches:
                if dispatch.get("name") == "event-changed":
                    evt_list = dispatch.get("params", {}).get("events", [])
                    log_debug("livewire", f"Extracted {len(evt_list)} events from dispatch 'event-changed'.")
                    events.extend(evt_list)
    log_debug("livewire", f"Total events extracted from livewire responses: {len(events)}")
    return events


def display_timetable(events):
    """Deduplicates, sorts, excludes Saturdays, and prints timetable events in formatted terminal tables."""
    log_debug("display", f"Starting display processing for {len(events)} total raw events.")
    if not events:
        log_debug("display", "No timetable events found to display.")
        print("No timetable events found.")
        return

    unique_events = {ev.get("id", idx): ev for idx, ev in enumerate(events)}
    log_debug("display", f"Deduplicated events count: {len(unique_events)}")

    sorted_events = sorted(unique_events.values(), key=lambda x: str(x.get("start", "")))
    log_debug("display", "Sorted events chronologically.")

    grouped_days = {}
    excluded_saturdays_count = 0

    for ev in sorted_events:
        start_raw = str(ev.get("start", ""))
        end_raw = str(ev.get("end", ""))

        try:
            clean_start = start_raw.split(".")[0].replace("T", " ")
            clean_end = end_raw.split(".")[0].replace("T", " ")

            dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

            # Exclude Saturdays completely (weekday 5 is Saturday)
            if dt_start.weekday() == 5:
                excluded_saturdays_count += 1
                log_debug("display", f"Excluding Saturday event: {start_raw} - {ev.get('title')}")
                continue

            day_header = dt_start.strftime("%A, %d %B %Y")
            time_str = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
        except ValueError as ve:
            log_debug("display", f"ValueError parsing dates ('{start_raw}', '{end_raw}'): {ve}")
            dt_start = datetime.min
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

    log_debug("display", f"Excluded {excluded_saturdays_count} Saturday events. Grouped into {len(grouped_days)} day headers.")

    print("\n" + "=" * 70)
    print("                     WEEKLY TIMETABLE                     ")
    print("=" * 70)

    for day, day_events in grouped_days.items():
        print(f"\n--- {day} " + "-" * max(0, (65 - len(day))))
        print(f"{'Time':<17} | {'Event Title':<28} | {'Room':<8} | {'Staff'}")
        print("-" * 70)
        for e in day_events:
            print(f"{e['time']:<17} | {e['title'][:28]:<28} | {e['room']:<8} | {e['staff']}")
    log_debug("display", "Timetable display render complete.")


def perform_login(p):
    """Launches interactive browser for authentication and closes window immediately upon login."""
    log_debug("auth", "Launching interactive browser window for login...")
    print("\n" + "=" * 60)
    print("  ACTION REQUIRED: Complete login in the browser window.")
    print("  (Window will close automatically as soon as login succeeds)")
    print("=" * 60)

    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    log_debug("auth", f"Navigating to BASE_URL: {BASE_URL}")
    page.goto(BASE_URL)

    try:
        log_debug("auth", "Waiting for post-login redirect...")
        page.wait_for_url(
            lambda url: "focus.barton.ac.uk" in url.lower() and "login" not in url.lower() and "google.com" not in url.lower(),
            timeout=120000
        )
        page.wait_for_timeout(1500)
        log_debug("auth", "Login redirect detected successfully.")
    except Exception as e:
        log_debug("auth", f"Timeout waiting for automatic redirect: {e}")
        input("\n>>> Press [ENTER] in this terminal once you have logged in... ")

    log_debug("auth", f"Saving session storage state to {SESSION_FILE}")
    context.storage_state(path=SESSION_FILE)
    print("\n[+] Login detected! Session saved to session.json.")
    print("[+] Closing interactive browser window...\n")
    browser.close()
    log_debug("auth", "Interactive login browser closed.")


def fetch_timetable(p):
    """Loads saved session in headless mode and fetches current & next week, plus previous week from cache."""
    log_debug("fetch", "Launching headless browser for data scraping...")
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state=SESSION_FILE)
    page = context.new_page()

    livewire_responses = []

    def handle_response(response):
        if "livewire" in response.url or "message" in response.url:
            try:
                data = response.json()
                if data:
                    log_debug("network", f"Intercepted Livewire response URL: {response.url}")
                    livewire_responses.append(data)
            except Exception:
                pass

    page.on("response", handle_response)
    log_debug("fetch", f"Navigating to BASE_URL: {BASE_URL}")
    page.goto(BASE_URL)

    current_url = page.url
    log_debug("fetch", f"Current page URL after load: {current_url}")

    if "login" in current_url.lower() or "google.com" in current_url.lower():
        log_debug("fetch", "Saved session has expired (redirected to login/google).")
        browser.close()
        if os.path.exists(SESSION_FILE):
            log_debug("fetch", f"Removing expired session file: {SESSION_FILE}")
            os.remove(SESSION_FILE)
        return None

    i = current_url.rfind('/')
    log_debug("fetch", f"URL rfind('/') index: {i}")

    if(i < 0):
        log_debug("fetch", "Invalid focus redirect URL structure.")
        browser.close()
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        return None
    
    timetable_url = current_url[:i-len(current_url)] + "/timetable"
    log_debug("fetch", f"Constructed timetable URL: {timetable_url}")

    page.goto(timetable_url)
    
    try:
        log_debug("fetch", "Waiting for element #powerCalendar and network idle state...")
        page.wait_for_selector("#powerCalendar", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        log_debug("fetch", "PowerCalendar selector and network idle confirmed.")
    except Exception as e:
        log_debug("fetch", f"Timeout or warning during calendar page wait: {e}")

    log_debug("fetch", "Extracting current week schedule from livewire responses...")
    current_week_events = extract_events(livewire_responses)
    log_debug("fetch", f"Extracted {len(current_week_events)} events for current week.")
    livewire_responses.clear()

    # Collect next week's timetable using the calendar's Next week button
    try:
        log_debug("fetch", "Attempting to click calendar '.fc-next-button' for next week...")
        page.click(".fc-next-button")
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle", timeout=5000)
        log_debug("fetch", "Successfully clicked next week button.")
    except Exception as e:
        log_debug("fetch", f"Could not pull next week automatically via button click: {e}")

    next_week_events = extract_events(livewire_responses)
    log_debug("fetch", f"Extracted {len(next_week_events)} events for next week.")
    all_fetched = current_week_events + next_week_events
    log_debug("fetch", f"Combined current + next week fetched events count: {len(all_fetched)}")

    # Include previous week's events from existing cache with strict date validation
    previous_week_events = []
    log_debug("fetch", f"Checking existing cache file for previous week events: {CACHE_FILE}")
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                old_cache = json.load(f)
                old_events = old_cache.get("events", [])
                log_debug("fetch", f"Loaded {len(old_events)} events from existing cache for previous week check.")
                current_sunday_str = get_current_week_sunday()
                current_sunday_dt = datetime.strptime(current_sunday_str, "%Y-%m-%d")
                prev_sunday_dt = current_sunday_dt - timedelta(days=7)
                log_debug("fetch", f"Target previous week Sunday: {prev_sunday_dt.strftime('%Y-%m-%d')}")

                for ev in old_events:
                    start_raw = str(ev.get("start", ""))
                    try:
                        clean_start = start_raw.split(".")[0].replace("T", " ")
                        dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
                        days_since_sunday = (dt_start.weekday() + 1) % 7
                        ev_sunday = dt_start - timedelta(days=days_since_sunday)
                        if ev_sunday.date() == prev_sunday_dt.date():
                            previous_week_events.append(ev)
                    except Exception:
                        pass
            log_debug("fetch", f"Successfully retained {len(previous_week_events)} events from previous week cache.")
        except Exception as e:
            log_debug("fetch", f"Error processing previous week cache: {e}")

    events = previous_week_events + all_fetched
    log_debug("fetch", f"Total accumulated events across all weeks: {len(events)}")

    if not events:
        log_debug("fetch", "Network capture missed payload. Attempting fallback evaluation via JS context...")
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
        log_debug("fetch", f"Fallback JS context extraction found {len(events)} events.")

    browser.close()
    log_debug("fetch", "Headless browser closed successfully.")
    return events


def run():
    log_debug("main", "Starting execution pipeline.")
    
    # 1. Check for weekly cached timetable first
    log_debug("main", "Checking weekly cache...")
    cached_events = load_cached_timetable()
    if cached_events:
        log_debug("main", f"Cache hit! Skipping network fetch. Total cached events: {len(cached_events)}")
        display_timetable(cached_events)
        return

    log_debug("main", "Cache miss or expired. Proceeding to headless browser pipeline...")
    with sync_playwright() as p:
        log_debug("main", "Playwright context initialized.")
        if not os.path.exists(SESSION_FILE):
            log_debug("main", f"Session file '{SESSION_FILE}' not found. Triggering login routine.")
            perform_login(p)

        events = fetch_timetable(p)

        if events is None:
            log_debug("main", "Session expired detected during fetch. Re-authenticating...")
            perform_login(p)
            events = fetch_timetable(p)

        if events is not None:
            log_debug("main", f"Successfully retrieved {len(events)} events. Saving cache and displaying timetable.")
            save_cached_timetable(events)
            display_timetable(events)
        else:
            log_debug("main", "Error: Events object is None after re-authentication attempts.")

    log_debug("main", "Program execution finished.")


if __name__ == "__main__":
    run()