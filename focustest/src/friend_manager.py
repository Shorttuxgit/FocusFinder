
import os
import json
import gzip
import zlib
import base64

from datetime import date, datetime, time, timedelta

from src.constants import FRIENDS_FILE


# Encoding configuration

ASCII_ATLAS = ''.join(chr(i) for i in range(33, 127))
BASE = len(ASCII_ATLAS)
ANDROID_DAYS = 6


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
            dt = datetime.fromisoformat(
                str(event.get("start", "")).replace("Z", "+00:00")
            )
            dates.append(dt.date())
        except (ValueError, TypeError):
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

    bi = int.from_bytes(data, byteorder="big", signed=True)

    if bi < 0:
        raise ValueError("Negative integer cannot be encoded.")

    output = []

    while bi > 0:
        digit = bi % BASE
        output.append(ASCII_ATLAS[digit])
        bi //= BASE

    return ''.join(output)


def base94_decode(encoded):
    bi = 0

    for char in reversed(encoded):
        digit = ASCII_ATLAS.find(char)

        if digit == -1:
            raise ValueError(f"Invalid Base94 character: {repr(char)}")

        bi = bi * BASE + digit

    if bi == 0:
        return b""

    byte_length = (bi.bit_length() + 7) // 8

    return bi.to_bytes(byte_length, byteorder="big")


# Event conversion

def serialize_event(event, reference_date):
    start = parse_datetime(event.get("start", ""), reference_date)
    end = parse_datetime(event.get("end", ""), start.date())

    start_time = start.strftime("%H:%M")
    end_time = end.strftime("%H:%M")

    title = str(event.get("title", "N/A") or "N/A").strip()
    room = str(event.get("room", "") or "").strip()
    staff = str(event.get("staff", "") or "").strip()

    for value in (title, room, staff):
        if any(char in value for char in ("@", ";", "^")):
            raise ValueError(f"Reserved character in event field: {value}")

    parts = [start_time, end_time, title]

    if room and room != "—":
        parts.append(room)

        if staff and staff != "—":
            parts.append(staff)

    elif staff and staff != "—":
        parts.extend(["", staff])

    return '@'.join(parts) + ';', start


def deserialize_day(day_string, day_date):
    events = []

    for raw_event in day_string.split(";"):
        raw_event = raw_event.strip()

        if not raw_event:
            continue

        parts = raw_event.split("@")

        if len(parts) < 3:
            continue

        start_time = parts[0]
        end_time = parts[1]
        title = parts[2]

        room = parts[3] if len(parts) > 3 else ""
        staff = parts[4] if len(parts) > 4 else ""

        start = datetime.combine(
            day_date,
            time.fromisoformat(start_time)
        )

        end = datetime.combine(
            day_date,
            time.fromisoformat(end_time)
        )

        if end <= start:
            end += timedelta(days=1)

        events.append({
            "title": title,
            "start": start.isoformat(timespec="seconds"),
            "end": end.isoformat(timespec="seconds"),
            "room": room or "—",
            "staff": staff or "—"
        })

    return events


# Android timetable encoding

def encode_timetable_string(student_name, events, reference_date=None):
    student_name = str(student_name).strip()

    if "^" in student_name:
        raise ValueError("Invalid character in student name.")

    events = list(events)
    monday = get_reference_date(events, reference_date)

    days = [[] for _ in range(ANDROID_DAYS)]

    for event in events:
        encoded_event, start = serialize_event(event, monday)

        day_index = start.date().weekday()

        if 0 <= day_index < ANDROID_DAYS:
            days[day_index].append((start, encoded_event))

    day_strings = []

    for day in days:
        day.sort(key=lambda item: item[0])
        day_strings.append(
            ''.join(encoded for _, encoded in day)
        )

    epoch_day = (monday - date(1970, 1, 1)).days

    payload = (
        str(epoch_day)
        + "^"
        + student_name
        + "^"
        + "^".join(day_strings)
        + "^"
    )

    compressed = gzip.compress(
        payload.encode("utf-8"),
        compresslevel=6,
        mtime=0
    )

    return base94_encode(compressed)


# Android timetable decoding

def decode_android_timetable(share_string):
    compressed = base94_decode(share_string)

    if not compressed.startswith(b"\x1f\x8b\x08"):
        raise ValueError("Invalid GZIP header.")

    payload = gzip.decompress(compressed).decode("utf-8")
    parts = payload.split("^")

    if len(parts) < 8:
        raise ValueError("Invalid timetable payload.")

    epoch_day = int(parts[0])
    student_name = parts[1]

    monday = date(1970, 1, 1) + timedelta(days=epoch_day)

    events = []

    for day_index in range(ANDROID_DAYS):
        day_date = monday + timedelta(days=day_index)
        day_string = parts[day_index + 2]

        events.extend(
            deserialize_day(day_string, day_date)
        )

    return student_name, events


# Legacy timetable decoding

def decode_legacy_timetable(share_string):
    encoded_part = share_string[4:].strip()

    compressed = base64.b85decode(
        encoded_part.encode("ascii")
    )

    if compressed.startswith(b"\x1f\x8b"):
        json_bytes = gzip.decompress(compressed)
    else:
        json_bytes = zlib.decompress(compressed)

    payload = json.loads(json_bytes.decode("utf-8"))

    return (
        payload.get("name", "Unknown"),
        payload.get("events", [])
    )


# Timetable decoding

def decode_timetable_string(share_string):
    share_string = str(share_string).strip()

    if not share_string:
        raise ValueError("Empty timetable code.")

    if share_string.startswith("FF1:"):
        return decode_legacy_timetable(share_string)

    return decode_android_timetable(share_string)


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
