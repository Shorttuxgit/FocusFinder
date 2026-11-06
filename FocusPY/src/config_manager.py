import json

from FocusPY.src.constants import CONFIG_FILE

DEFAULT_CONFIG = {
    "time_format": False,
    "friends_system": True,
    "sett_enabled": True
}


def load_config():
    config = DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            user_config = json.load(file)

        if isinstance(user_config, dict):
            config.update(user_config)

    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as error:
        print(f"[!] Could not load configuration: {error}")

    return config


def write_to_config(key, value):
    config = load_config()
    config[key] = value

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

    except OSError as error:
        print(f"[!] Could not save configuration: {error}")
        raise