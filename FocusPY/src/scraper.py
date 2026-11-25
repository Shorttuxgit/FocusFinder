# --------------------------------------------------
# Talks to the Focus website and keeps a weekly cache
# --------------------------------------------------

import json
import os
from datetime import date, timedelta

from FocusPY.src.constants import BASE_URL, SESSION_FILE, CACHE_FILE

# How many weeks of timetable to download, and how many times to retry a login
TOTAL_WEEKS = 5
LOGIN_ATTEMPTS = 4

# The browser never needs these, so they are not downloaded (faster loading)
BLOCKED_RESOURCES = {"image", "font", "media"}


# --------------------------------------------------
# Weekly cache
# --------------------------------------------------

def get_current_week_sunday():
    # The cache is only valid for the week (Sunday to Saturday) it was saved in
    today = date.today()
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    return sunday.strftime("%Y-%m-%d")


def load_cached_timetable(need_progress=False):
    """Return (events, student_name, progress) saved this week, or None.

    need_progress=True means the grades panel is switched on, so a cache that
    was saved without grades is treated as out of date and fetched again.
    """
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Wrong week
    if data.get("week_commencing") != get_current_week_sunday():
        return None

    # Caches written before grades were added have no "progress" key
    if "progress" not in data:
        return None

    if need_progress:
        # Grades are wanted but this cache was saved with the grades panel off
        if not data.get("has_progress", True):
            return None

        # Caches from before the Progress view have no grade history
        if any("history" not in course for course in data["progress"]):
            return None

    return (
        data.get("events", []),
        data.get("student_name", "Student"),
        data.get("progress", []),
    )


def save_cached_timetable(events, student_name, progress=None, has_progress=True):
    # has_progress records whether grades were downloaded (they are skipped
    # when the progress system is switched off)
    data = {
        "week_commencing": get_current_week_sunday(),
        "student_name": student_name,
        "events": events,
        "progress": progress or [],
        "has_progress": has_progress,
    }

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
    except Exception as error:
        print(f"[!] Warning: Could not save timetable cache: {error}")


# --------------------------------------------------
# Reading the timetable out of the page's background (Livewire) responses
# --------------------------------------------------

def extract_events(livewire_responses):
    events = []

    for response in livewire_responses:
        components = response if isinstance(response, list) else response.get("components", [])

        for component in components:
            if not isinstance(component, dict):
                continue

            for dispatch in component.get("effects", {}).get("dispatches", []):
                if dispatch.get("name") == "event-changed":
                    events.extend(dispatch.get("params", {}).get("events", []))

    return events


# --------------------------------------------------
# Grades / progress page
# --------------------------------------------------

# Runs inside the browser: reads every course table on the progress page
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
        # Every column that has a grade (or target) recorded, oldest first.
        # Each new grade Focus adds becomes another column in the table.
        history = [
            {key: column[key] for key in ("period", "label", "grade", "ttg", "commit")}
            for column in course["columns"]
            if column["grade"] or column["ttg"]
        ]
        if not history:
            continue

        # The home page shows the most recent column; the Progress view uses all of them
        courses.append({"title": course["title"], **history[-1], "history": history})

    logger_fn(f"[+] Loaded grades for {len(courses)} course(s).")
    return courses


# --------------------------------------------------
# Signing in
# --------------------------------------------------

def perform_login(p, logger_fn):
    # Opens a visible browser so the student can sign in, then saves the session
    logger_fn("\n" + "=" * 50, "Sign in using the browser window")
    logger_fn("ACTION REQUIRED: Complete login in the browser window.")
    logger_fn("=" * 50 + "\n")

    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)

    try:
        page.wait_for_url(
            lambda url: "focus.barton.ac.uk" in url.lower()
            and "login" not in url.lower()
            and "google.com" not in url.lower(),
            timeout=120000
        )
        page.wait_for_timeout(1500)
    except Exception:
        logger_fn("[!] Waiting for user to complete login in browser...")

    # Tell the person straight away that the sign-in worked
    logger_fn("[+] Login detected!", "Signed in! Saving your session...")
    context.storage_state(path=str(SESSION_FILE))

    # The sign-in window closes here. Update the status the moment it does,
    # because starting the hidden browser that follows takes a few seconds.
    browser.close()
    logger_fn("[+] Session saved.", "Signed in! Connecting to your timetable...")


def remove_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


def on_login_page(page):
    url = page.url.lower()
    return "login" in url or "google.com" in url


def block_heavy_resources(route):
    # Skip images, fonts and media: the timetable data does not need them
    if route.request.resource_type in BLOCKED_RESOURCES:
        route.abort()
    else:
        route.continue_()


def open_portal(p, on_response):
    # Start a hidden browser with the saved session and open the portal home page
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(SESSION_FILE))
    context.route("**/*", block_heavy_resources)

    page = context.new_page()
    page.on("response", on_response)
    page.goto(BASE_URL)
    return browser, page


def sign_in(p, on_response, logger_fn):
    """Open the portal, signing in again if the saved session has expired.

    Returns (browser, page), or (None, None) if every login attempt failed.
    """
    if not os.path.exists(SESSION_FILE):
        perform_login(p, logger_fn)

    browser, page = open_portal(p, on_response)
    if not on_login_page(page):
        return browser, page

    logger_fn("[!] Session expired. Re-authenticating...")

    for _ in range(LOGIN_ATTEMPTS):
        browser.close()
        remove_session()
        perform_login(p, logger_fn)

        browser, page = open_portal(p, on_response)
        if not on_login_page(page):
            return browser, page

    browser.close()
    remove_session()
    return None, None


def read_student_name(page):
    # The dashboard heading looks like "Welcome Back, <name>"
    try:
        heading = page.locator("h1.text-3xl.font-bold").inner_text(timeout=5000)
    except Exception:
        return "Student"

    return heading.replace("Welcome Back,", "").strip() or "Student"


# --------------------------------------------------
# Downloading the timetable
# --------------------------------------------------

def wait_for_week(page, responses, timeout_ms=2500):
    # After clicking "next week", wait until event data actually arrives
    # instead of always pausing for a fixed time
    waited = 0
    while waited < timeout_ms and not extract_events(responses):
        page.wait_for_timeout(100)
        waited += 100

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass


def fetch_timetable_data(sync_playwright_fn, logger_fn, progress_fn=None, fetch_grades=True):
    """Download the timetable (and optionally grades).

    Returns (events, student_name, progress) or None if signing in failed.
    """

    def step(fraction, status):
        # Log a human-readable step and move the loading bar forward
        logger_fn(f"[*] {status}", status)
        if progress_fn:
            progress_fn(fraction)

    # Every background response from the page is collected here
    responses = []

    def on_response(response):
        if "livewire" in response.url or "message" in response.url:
            try:
                data = response.json()
                if data:
                    responses.append(data)
            except Exception:
                pass

    step(0.10, "Connecting to Focus portal...")

    with sync_playwright_fn() as p:
        browser, page = sign_in(p, on_response, logger_fn)
        if browser is None:
            return None

        try:
            step(0.25, "Signed in. Reading your profile...")
            student_name = read_student_name(page)

            # The student's pages share a base address, e.g. https://.../student/123
            cut = page.url.rfind("/")
            if cut < 0:
                return None
            student_base = page.url[:cut]

            step(0.30, "Opening your timetable...")
            page.goto(student_base + "/timetable")

            step(0.35, f"Loading week 1 of {TOTAL_WEEKS}...")
            try:
                page.wait_for_selector("#powerCalendar", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            events = extract_events(responses)
            responses.clear()

            # Click "next" to load the remaining weeks
            for week in range(1, TOTAL_WEEKS):
                step(0.35 + 0.45 * week / TOTAL_WEEKS, f"Loading week {week + 1} of {TOTAL_WEEKS}...")
                try:
                    page.click(".fc-next-button")
                    wait_for_week(page, responses)
                    events.extend(extract_events(responses))
                    responses.clear()
                except Exception:
                    pass

            # Grades are skipped completely when the progress system is off
            progress = []
            if fetch_grades:
                step(0.88, "Collecting your grades...")
                progress = fetch_progress(page, student_base, logger_fn)

            step(0.97, "Finishing up...")
            return events, student_name, progress

        finally:
            browser.close()