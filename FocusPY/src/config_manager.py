import json
import os

from FocusPY.src.constants import CONFIG_FILE
from FocusPY.src.settings import DEFAULTS

# Kept for anything that still imports it; the real defaults live in settings.py
DEFAULT_CONFIG = dict(DEFAULTS)

_cache = None


def load_config(force=False):
    """Return the configuration (defaults overlaid with config.json).

    The file is read once and kept in memory; pass force=True to re-read it.
    A copy is returned so callers can't change the cache by accident.
    """
    global _cache

    if _cache is None or force:
        config = dict(DEFAULTS)

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                user_config = json.load(file)

            if isinstance(user_config, dict):
                config.update(user_config)

        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError) as error:
            print(f"[!] Could not load configuration: {error}")

        _cache = config

    return dict(_cache)


def write_to_config(key, value):
    global _cache

    config = load_config()
    config[key] = value

    temporary = f"{CONFIG_FILE}.tmp"

    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)
        os.replace(temporary, CONFIG_FILE)

    except OSError as error:
        print(f"[!] Could not save configuration: {error}")
        raise

    _cache = config