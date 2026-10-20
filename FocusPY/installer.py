#!/bin/python3
import os
import sys
import platform
import subprocess
import shutil

CURRENT_OS = platform.system()
APP_NAME = "FocusFinder"

def get_install_dir():
    """Returns the correct installation directory based on the OS."""
    if CURRENT_OS == "Windows":
        app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(app_data, APP_NAME)
    elif CURRENT_OS == "Linux":
        return os.path.expanduser(f"~/.local/share/{APP_NAME.lower()}")
    return None


def setup_windows(install_dir):
    """Handles installation, script placement, and Start Menu shortcut on Windows."""
    print("[*] Configuring Windows integration...")
    
    target_script = os.path.join(install_dir, "Focus.py")
    icon_path = os.path.join(install_dir, "icon.ico")

    # Create a batch launcher runner script if it doesn't exist
    bat_path = os.path.join(install_dir, "run_focus.bat")
    if not os.path.exists(bat_path):
        with open(bat_path, "w") as f:
            f.write(f'@echo off\npython "{target_script}"\npause\n')

    # Create Windows Start Menu Shortcut using PowerShell
    start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft\\Windows\\Start Menu\\Programs")
    shortcut_path = os.path.join(start_menu, f"{APP_NAME}.lnk")

    ps_command = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{bat_path}"
    $Shortcut.WorkingDirectory = "{install_dir}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Save()
    """
    subprocess.run(["powershell", "-Command", ps_command], capture_output=True)


def setup_linux(install_dir):
    """Handles installation, script placement, and Desktop entry on Linux."""
    print("[*] Configuring Linux integration...")

    target_script = os.path.join(install_dir, "Focus.py")
    icon_path = os.path.join(install_dir, "icon.png")

    # Create Applications desktop entry
    applications_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(applications_dir, exist_ok=True)
    desktop_file_path = os.path.join(applications_dir, f"{APP_NAME.lower()}.desktop")

    desktop_entry = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec=python3 "{target_script}"
Icon={icon_path if os.path.exists(icon_path) else ""}
Terminal=false
Categories=Education;Utility;
"""

    with open(desktop_file_path, "w") as f:
        f.write(desktop_entry)

    os.chmod(desktop_file_path, 0o755)


def install_dependencies():
    """Installs required Python packages automatically."""
    print("[*] Checking and updating required Python packages (customtkinter, playwright)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "customtkinter", "playwright"])
        print("[*] Ensuring Playwright Chromium browser binaries are up to date...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"[!] Warning during dependency installation: {e}")


if __name__ == "__main__":
    print(f"--- {APP_NAME} Installer & Updater ({CURRENT_OS}) ---")
    
    install_dir = get_install_dir()
    if not install_dir:
        print(f"[!] Unsupported operating system: {CURRENT_OS}")
        sys.exit(1)

    is_update = os.path.exists(install_dir)
    if is_update:
        print(f"[*] Existing installation detected at: {install_dir}")
        print("[*] Updating app files (your login session and cache will be preserved)...")
    else:
        print(f"[*] Performing fresh installation to: {install_dir}")

    os.makedirs(install_dir, exist_ok=True)

    # 1. Copy app files over (Safely overwriting code/icons, leaving session/cache untouched)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_copy = ["Focus.py", "icon.png", "icon.ico"]
    
    for file_name in files_to_copy:
        src = os.path.join(current_dir, file_name)
        if os.path.exists(src):
            shutil.copy(src, install_dir)
            print(f"    + Updated {file_name}")

    # 2. Install / Update dependencies and browser drivers
    install_dependencies()

    # 3. Register shortcuts depending on OS
    if CURRENT_OS == "Windows":
        setup_windows(install_dir)
    elif CURRENT_OS == "Linux":
        setup_linux(install_dir)

    action_word = "Updated" if is_update else "Installed"
    print(f"\n[+] Success! FocusFinder has been successfully {action_word}.")
    print("[+] Press Enter to exit.")
    input()