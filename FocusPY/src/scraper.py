import os
import json
from datetime import datetime, date, timedelta
from FocusPY.src.constants import BASE_URL, SESSION_FILE, CACHE_FILE

def get_current_week_sunday():
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    return sunday.strftime("%Y-%m-%d")

def load_cached_timetable():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if data.get("week_commencing") == get_current_week_sunday():
                # Caches written before grades were added have no "progress" key,
                # so treat them as stale and fetch again.
                if "progress" not in data:
                    return None
                return (
                    data.get("events", []),
                    data.get("student_name", "Student"),
                    data.get("progress", []),
                )
    except Exception:
        pass
    return None

def save_cached_timetable(events, student_name, progress=None):
    try:
        data = {
            "week_commencing": get_current_week_sunday(),
            "student_name": student_name,
            "events": events,
            "progress": progress or []
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Could not save timetable cache: {e}")

def extract_events(livewire_responses):
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

PROGRESS_JS = """
() => Array.from(document.querySelectorAll('div.mb-8')).map(section => {
    const title = section.querySelector('h1');
    const table = section.querySelector('table');
    if (!title || !table) return null;

    const rows = table.querySelectorAll('tr');
    if (rows.length < 3) return null;

    const periods = [];
    Array.from(rows[0].querySelectorAll('th')).slice(1).forEach(th => {
        const span = parseInt(th.getAttribute('colspan') || '1', 10);
        for (let i = 0; i < span; i++) periods.push(th.innerText.trim());
    });

    const labels = Array.from(rows[1].querySelectorAll('th')).slice(1)
        .map(th => th.innerText.trim());

    const columns = Array.from(rows[2].querySelectorAll('td')).slice(1).map((td, i) => {
        const values = Array.from(td.querySelectorAll('div')).map(d => d.innerText.trim());
        return {
            period: periods[i] || '',
            label: labels[i] || '',
            grade: values[0] || '',
            ttg: values[1] || '',
            commit: values[2] || ''
        };
    });

    return { title: title.innerText.trim(), columns: columns };
}).filter(Boolean)
"""


def fetch_progress(page, base_url, logger_fn):
    """Scrape the current grade, target grade and commitment for each course."""
    try:
        page.goto(base_url + "/progress")
        page.wait_for_selector("div.mb-8 table", timeout=15000)
        raw_courses = page.evaluate(PROGRESS_JS)
    except Exception as error:
        logger_fn(f"[!] Could not read the progress page: {error}")
        return []

    courses = []
    for course in raw_courses:
        # Use the most recent column that actually has a grade recorded.
        filled = [c for c in course["columns"] if c["grade"] or c["ttg"]]
        if not filled:
            continue
        latest = filled[-1]
        courses.append({
            "title": course["title"],
            "period": latest["period"],
            "label": latest["label"],
            "grade": latest["grade"],
            "ttg": latest["ttg"],
            "commit": latest["commit"],
        })

    logger_fn(f"[+] Loaded grades for {len(courses)} course(s).")
    return courses


def perform_login(p, logger_fn):
    logger_fn("\n" + "=" * 50, "Sign in using the browser window")
    logger_fn("ACTION REQUIRED: Complete login in the browser window.")
    logger_fn("=" * 50 + "\n")

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
        logger_fn("[!] Waiting for user to complete login in browser...")

    context.storage_state(path=SESSION_FILE)
    logger_fn("[+] Login detected! Session saved.")
    browser.close()

TOTAL_WEEKS = 5


def fetch_timetable_data(sync_playwright_fn, logger_fn, progress_fn=None):
    def step(fraction, status):
        # Log a human-readable step and move the loading bar forward
        logger_fn(f"[*] {status}", status)
        if progress_fn:
            progress_fn(fraction)

    step(0.10, "Connecting to Focus portal...")

    with sync_playwright_fn() as p:
        if not os.path.exists(SESSION_FILE):
            perform_login(p, logger_fn)

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
        page.goto(BASE_URL)
    
        if "login" in page.url.lower() or "google.com" in page.url.lower():
            logger_fn("[!] Session expired. Re-authenticating...")
            browser.close()
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            
            login_success = False
            for attempt in range(4):
                perform_login(p, logger_fn)
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(storage_state=SESSION_FILE)
                page = context.new_page()
                page.on("response", handle_response)
                page.goto(BASE_URL)
                
                if not ("login" in page.url.lower() or "google.com" in page.url.lower()):
                    login_success = True
                    break
                else:
                    browser.close()
                    if os.path.exists(SESSION_FILE):
                        os.remove(SESSION_FILE)

            if not login_success:
                return None

        step(0.25, "Signed in. Reading your profile...")
        student_name = "Student"
        try:
            h1_text = page.locator("h1.text-3xl.font-bold").inner_text(timeout=5000)
            if "Welcome Back," in h1_text:
                student_name = h1_text.replace("Welcome Back,", "").strip()
            else:
                student_name = h1_text.strip()
        except Exception:
            pass

        url = page.url
        i = url.rfind('/')
        if i < 0:
            browser.close()
            return None
        student_base = url[:i]
        url = student_base + "/timetable"

        step(0.30, "Opening your timetable...")
        page.goto(url)
        step(0.35, f"Loading week 1 of {TOTAL_WEEKS}...")
        try:
            page.wait_for_selector("#powerCalendar", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        current_week_events = extract_events(livewire_responses)
        livewire_responses.clear()

        all_fetched = list(current_week_events)
        for week_idx in range(TOTAL_WEEKS - 1):
            step(0.35 + 0.45 * (week_idx + 1) / TOTAL_WEEKS, f"Loading week {week_idx + 2} of {TOTAL_WEEKS}...")
            try:
                page.click(".fc-next-button")
                page.wait_for_timeout(2000)
                page.wait_for_load_state("networkidle", timeout=5000)
                week_events = extract_events(livewire_responses)
                all_fetched.extend(week_events)
                livewire_responses.clear()
            except Exception:
                pass

        step(0.88, "Collecting your grades...")
        progress = fetch_progress(page, student_base, logger_fn)
        step(0.97, "Finishing up...")

        browser.close()
        return all_fetched, student_name, progress