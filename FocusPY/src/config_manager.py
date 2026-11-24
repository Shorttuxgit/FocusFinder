# --------------------------------------------------
# Reading and writing config.json
# --------------------------------------------------

import json
import os
import shutil

from FocusPY.src.constants import CONFIG_FILE, LEGACY_CONFIG_FILE
from FocusPY.src.settings import DEFAULTS

# Kept for anything that still imports it; the real defaults live in settings.py
DEFAULT_CONFIG = dict(DEFAULTS)

# The loaded configuration is kept here after the first read
_cache = None

# Plain-English description of the last problem found in config.json (or None)
_error = None

# Text values that are accepted for on / off settings
_TRUE_WORDS = {"true", "1", "yes", "on"}
_FALSE_WORDS = {"false", "0", "no", "off"}


def config_path():
    """The file that is read: the new location, or the old one if only that exists."""
    if CONFIG_FILE.exists() or not LEGACY_CONFIG_FILE.exists():
        return CONFIG_FILE
    return LEGACY_CONFIG_FILE


def get_config_error():
    """A message describing why config.json could not be used, or None if it was fine."""
    return _error


def _coerce(key, value):
    # On / off settings must be real booleans. Without this, a hand-typed
    # "false" (text) would count as True and the setting would seem ignored.
    default = DEFAULTS.get(key)
    if not isinstance(default, bool) or isinstance(value, bool):
        return value

    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_WORDS:
            return True
        if text in _FALSE_WORDS:
            return False
        return default

    if isinstance(value, (int, float)):
        return bool(value)

    return default


def _read_user_config(path):
    """Return the settings stored in the file ({} if there are none)."""
    global _error

    try:
        # utf-8-sig also accepts files saved with a byte-order mark (Notepad does this)
        with open(path, "r", encoding="utf-8-sig") as file:
            user_config = json.load(file)

    except FileNotFoundError:
        return {}

    except json.JSONDecodeError as error:
        _error = f"{path.name} line {error.lineno}: {error.msg}"

    except OSError as error:
        _error = f"{path.name} could not be read ({error.strerror or error})"

    else:
        if isinstance(user_config, dict):
            return user_config
        _error = f"{path.name} must contain a {{ }} object"

    print(f"[!] Could not load configuration: {_error}")
    return {}


def load_config(force=False):
    """Return the configuration (defaults overlaid with config.json).

    The file is read once and kept in memory; pass force=True to re-read it.
    A copy is returned so callers can't change the cache by accident.
    """
    global _cache, _error

    if _cache is None or force:
        _error = None
        path = config_path()

        config = dict(DEFAULTS)
        config.update(_read_user_config(path))
        _cache = {key: _coerce(key, value) for key, value in config.items()}

        print(f"[*] Configuration file: {path}")

    return dict(_cache)


def write_to_config(key, value):
    """Save one setting. Raises OSError if the file cannot be written."""
    global _cache

    config = load_config()
    config[key] = value

    # If the existing file was unreadable, keep a copy before replacing it so
    # hand-typed settings are never lost
    if _error and CONFIG_FILE.exists():
        try:
            shutil.copy2(CONFIG_FILE, CONFIG_FILE.with_name(CONFIG_FILE.name + ".bak"))
        except OSError:
            pass

    # Write to a temporary file first so a crash can never leave half a file
    temporary = CONFIG_FILE.with_name(CONFIG_FILE.name + ".tmp")

    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)
        os.replace(temporary, CONFIG_FILE)

    except OSError as error:
        print(f"[!] Could not save configuration: {error}")
        raise

    _cache = config