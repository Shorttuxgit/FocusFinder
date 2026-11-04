import os
import json
import gzip
import zlib
import base64
import shlex
import re

from pathlib import Path
from datetime import date, datetime, time, timedelta

from FocusPY.src.constants import FRIENDS_FILE


ASCII_ATLAS = ''.join(chr(i) for i in range(33, 127))
BASE = len(ASCII_ATLAS)
ANDROID_DAYS = 6
ANDROID_SLOTS = (8, 10, 12, 14)
SPECIAL_SUBJECTS = {"Personal Development", "Study Period"}


# Date handling

def parse_datetime(value, fallback_date=None):
    value = str(value).strip()

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        pass

    try:
        parsed_time = time.fromisoformat(value)
        if fallback_date is None:
            raise ValueError("A reference date is required.")
        return datetime.combine(fallback_date, parsed_time)
    except ValueError:
        raise ValueError(f"Invalid date/time: {value}")


def get_reference_date(events, reference_date=None):
    if reference_date is not None:
        if isinstance(reference_date, str):
            reference_date = date.fromisoformat(reference_date)
        if isinstance(reference_date, datetime):
            reference_date = reference_date.date()
        if not isinstance(reference_date, date):
            raise ValueError("Invalid reference date.")
        return reference_date - timedelta(days=reference_date.weekday())

    dates = []
    for event in events:
        try:
            dates.append(parse_datetime(event.get("start", "")).date())
        except (ValueError, TypeError, AttributeError):
            continue

    if dates:
        earliest = min(dates)
        return earliest - timedelta(days=earliest.weekday())

    today = date.today()
    return today - timedelta(days=today.weekday())


# Base94 encoding

def base94_encode(data):
    if not data:
        return ""

    value = int.from_bytes(data, byteorder="big", signed=False)
    output = []

    while value > 0:
        output.append(ASCII_ATLAS[value % BASE])
        value //= BASE

    return ''.join(output)


def base94_decode(encoded):
    value = 0

    for char in reversed(encoded):
        digit = ASCII_ATLAS.find(char)
        if digit == -1:
            raise ValueError(f"Invalid Base94 character: {repr(char)}")
        value = value * BASE + digit

    if value == 0:
        return b""

    byte_length = (value.bit_length() + 7) // 8
    return value.to_bytes(byte_length, byteorder="big", signed=False)


# Android event conversion

def serialize_event(event, reference_date):
    start = parse_datetime(event.get("start", ""), reference_date)
    end = parse_datetime(event.get("end", ""), start.date())

    title = str(event.get("title", "N/A") or "N/A").strip()
    room = str(event.get("room", "") or "").strip()
    staff = str(event.get("staff", "") or "").strip()

    for value in (title, room, staff):
        if any(char in value for char in ("@", ";", "^")):
            raise ValueError(f"Reserved character in event field: {value}")

    start_time = start.strftime("%H:%M")
    end_time = end.strftime("%H:%M")

    if title in SPECIAL_SUBJECTS:
        encoded = f"{start_time}@{end_time}@{title};"
    else:
        encoded = f"{start_time}@{end_time}@{title}@{room}@{staff};"

    return encoded, start


def deserialize_day(day_string, day_date):
    events = []

    for raw_event in day_string.split(";"):
        raw_event = raw_event.strip()
        if not raw_event:
            continue

        parts = raw_event.split("@")
        if len(parts) < 3:
            continue

        try:
            start_time = time.fromisoformat(parts[0])
            end_time = time.fromisoformat(parts[1])
            title = parts[2].strip()

            if title in SPECIAL_SUBJECTS:
                room = "—"
                staff = "—"
            else:
                room = parts[3].strip() if len(parts) > 3 else ""
                staff = parts[4].strip() if len(parts) > 4 else ""
                room = room or "—"
                staff = staff or "—"

            start = datetime.combine(day_date, start_time)
            end = datetime.combine(day_date, end_time)
            if end <= start:
                end += timedelta(days=1)

            events.append({
                "title": title,
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "room": room,
                "staff": staff
            })
        except (ValueError, IndexError):
            continue

    return events


# Share code conversion

def encode_timetable_string(student_name, events, reference_date=None):
    student_name = str(student_name).strip()
    if any(char in student_name for char in "^@;"):
        raise ValueError("Invalid character in student name.")

    events = list(events)
    monday = get_reference_date(events, reference_date)
    days = [{hour: None for hour in ANDROID_SLOTS} for _ in range(ANDROID_DAYS)]

    for event in events:
        encoded_event, start = serialize_event(event, monday)
        day_index = start.date().weekday()

        if not 0 <= day_index < ANDROID_DAYS:
            continue

        if start.hour not in ANDROID_SLOTS:
            continue

        days[day_index][start.hour] = encoded_event

    day_strings = []
    for day in days:
        day_strings.append(''.join(day[hour] or "" for hour in ANDROID_SLOTS))

    epoch_day = (monday - date(1970, 1, 1)).days
    payload = str(epoch_day) + "^" + student_name + "^" + "^".join(day_strings) + "^"

    compressed = gzip.compress(
        payload.encode("utf-8"),
        compresslevel=6,
        mtime=0
    )

    return base94_encode(compressed)


def decode_android_timetable(share_string):
    compressed = base94_decode(share_string)
    if not compressed.startswith(b"\x1f\x8b\x08"):
        raise ValueError("Invalid GZIP header.")

    payload = gzip.decompress(compressed).decode("utf-8")
    parts = payload.split("^")
    if len(parts) < 8:
        raise ValueError("Invalid timetable payload.")

    try:
        epoch_day = int(parts[0])
        monday = date(1970, 1, 1) + timedelta(days=epoch_day)
    except (ValueError, OverflowError):
        raise ValueError("Invalid timetable date.")

    student_name = parts[1]
    events = []

    for day_index in range(ANDROID_DAYS):
        day_date = monday + timedelta(days=day_index)
        events.extend(deserialize_day(parts[day_index + 2], day_date))

    return student_name, events


# Legacy share support

def decode_legacy_timetable(share_string):
    encoded_part = share_string[4:].strip()
    compressed = base64.b85decode(encoded_part.encode("ascii"))

    if compressed.startswith(b"\x1f\x8b"):
        json_bytes = gzip.decompress(compressed)
    else:
        json_bytes = zlib.decompress(compressed)

    payload = json.loads(json_bytes.decode("utf-8"))
    return payload.get("name", "Unknown"), payload.get("events", [])


def decode_timetable_string(share_string):
    share_string = str(share_string).strip()
    if not share_string:
        raise ValueError("Empty timetable code.")

    if share_string.startswith("FF1:"):
        return decode_legacy_timetable(share_string)

    return decode_android_timetable(share_string)


# File import and export

def get_desktop_directory():
    home = Path.home()

    if os.name == "nt":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                desktop, _ = winreg.QueryValueEx(key, "Desktop")
            desktop = os.path.expandvars(desktop)
            return Path(desktop).expanduser()
        except (ImportError, OSError):
            pass

    config_file = home / ".config" / "user-dirs.dirs"
    if config_file.is_file():
        try:
            for line in config_file.read_text(encoding="utf-8").splitlines():
                match = re.match(r'^\s*XDG_DESKTOP_DIR=(.*)\s*$', line)
                if match:
                    value = shlex.split(match.group(1))[0]
                    value = value.replace("$HOME", str(home))
                    return Path(os.path.expandvars(value)).expanduser()
        except (OSError, IndexError, ValueError):
            pass

    return home / "Desktop"


def export_friend_file(student_name, events, reference_date=None):
    share_string = encode_timetable_string(student_name, events, reference_date)
    desktop = get_desktop_directory()
    desktop.mkdir(parents=True, exist_ok=True)

    output_file = desktop / "friend.fff"
    output_file.write_text(share_string, encoding="utf-8", newline="")
    return output_file


def import_friend_file(file_path):
    path = Path(file_path)
    share_string = path.read_text(encoding="utf-8-sig").strip()

    name, events = decode_timetable_string(share_string)
    save_friend(name, events)
    return name, events


# Friend storage

def load_friends():
    if not os.path.exists(FRIENDS_FILE):
        return {}

    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_friends(friends):
    path = os.fspath(FRIENDS_FILE)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(friends, f, indent=2, ensure_ascii=False)

    os.replace(temporary_path, path)


def save_friend(student_name, events):
    friends = load_friends()
    friends[student_name] = events
    save_friends(friends)


def delete_friend(friend_name):
    friends = load_friends()
    if friend_name in friends:
        del friends[friend_name]
        save_friends(friends)
