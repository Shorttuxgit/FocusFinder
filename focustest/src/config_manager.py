import json
import os
from src.constants import CONFIG_FILE

# Define default configuration settings as the single source of truth
DEFAULT_CONFIG = {
    "sett_enabled": False,
    "time_format": False,
    "autoupdate": False,
    "profile_enabled": False,
    "weather_enabled": True,
    "friends_system": True
}

def load_config():
    # Load user overrides from config file and merge them with code defaults
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
                if isinstance(user_config, dict):
                    config.update(user_config)
        except Exception:
            pass
    return config

def write_to_config(key, value):
    # Write a single user override setting to the config file
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception:
            config = {}
    
    config[key] = value
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass