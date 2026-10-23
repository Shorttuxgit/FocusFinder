import os
import json

CONFIG_DIR = os.path.expanduser("~/.local/share/focusfinder/config.json")

def init_config():
    os.makedirs(os.path.dirname(CONFIG_DIR), exist_ok=True)
    try:
        default_file = {
            "sett_enabled": False,
            "time_format": False, # False for 24H, True for 12H
            "autoupdate": False,
            "profile_enabled": False,
            "weather_enabled": True
        }
        with open(CONFIG_DIR, "x") as config:
            json.dump(default_file, config, indent=4)
    except FileExistsError:
        pass

def load_config():
    init_config()
    with open(CONFIG_DIR, "r") as config_read:
        return json.load(config_read)

def write_to_config(key, value):
    config_data = load_config()
    config_data[key] = value
    with open(CONFIG_DIR, 'w') as writecon:
        json.dump(config_data, writecon, indent=4)