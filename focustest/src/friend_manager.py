import json
import os
import zlib
import base64
from src.constants import FRIENDS_FILE

def encode_timetable_string(student_name, events):
    # Compress and encode student name and slimmed events into a shareable string
    slim_events = []
    for ev in events:
        slim_events.append({
            "title": ev.get("title", "N/A"),
            "start": ev.get("start", ""),
            "end": ev.get("end", "")
        })
    
    payload = {
        "name": student_name,
        "events": slim_events
    }
    
    json_bytes = json.dumps(payload).encode("utf-8")
    compressed_bytes = zlib.compress(json_bytes, level=9)
    encoded_str = base64.b85encode(compressed_bytes).decode("ascii")
    
    return f"FF1:{encoded_str}"

def decode_timetable_string(share_string):
    # Decode and decompress a share string back into student name and events list
    if not share_string.startswith("FF1:"):
        raise ValueError("Invalid share string format.")
    
    encoded_part = share_string[4:].strip()
    compressed_bytes = base64.b85decode(encoded_part.encode("ascii"))
    json_bytes = zlib.decompress(compressed_bytes)
    payload = json.loads(json_bytes.decode("utf-8"))
    
    return payload.get("name", "Unknown"), payload.get("events", [])

def load_friends():
    # Load all saved friend timetables from local cache file
    if not os.path.exists(FRIENDS_FILE):
        return {}
    try:
        with open(FRIENDS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_friend(student_name, events):
    # Save or update a friend's timetable data in local cache storage
    friends = load_friends()
    friends[student_name] = events
    try:
        with open(FRIENDS_FILE, "w") as f:
            json.dump(friends, f, indent=2)
    except Exception:
        pass

def delete_friend(friend_name):
    # Remove a saved friend from local cache storage
    friends = load_friends()
    if friend_name in friends:
        del friends[friend_name]
        try:
            with open(FRIENDS_FILE, "w") as f:
                json.dump(friends, f, indent=2)
        except Exception:
            pass