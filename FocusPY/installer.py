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


def find_pythonw():
    """Locates pythonw.exe on the system."""
    path = shutil.which("pythonw")
    if path:
        return path
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Python", "bin"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Python"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Python"),
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            candidate = os.path.join(base, entry, "pythonw.exe")
            if os.path.isfile(candidate):
                return candidate
        direct = os.path.join(base, "pythonw.exe")
        if os.path.isfile(direct):
            return direct
    return None


def setup_windows(install_dir):
    """Handles installation, script placement, and Start Menu shortcut on Windows."""
    print("[*] Configuring Windows integration...")

    target_script = os.path.join(install_dir, "Focus.py")
    icon_path = os.path.join(install_dir, "icon.ico")

    pythonw = find_pythonw()
    if not pythonw:
        print("[!] Could not find pythonw.exe. Shortcut will use 'python' instead.")
        pythonw = shutil.which("python") or "python"

    start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft\\Windows\\Start Menu\\Programs")
    shortcut_path = os.path.join(start_menu, f"{APP_NAME}.lnk")

    ps_command = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{pythonw}"
    $Shortcut.Arguments = "{target_script}"
    $Shortcut.WorkingDirectory = "{install_dir}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
    """
    subprocess.run(["powershell", "-Command", ps_command], capture_output=True)
    print(f"    + Shortcut created: {shortcut_path}")
    print(f"    + Using interpreter: {pythonw}")


def setup_linux(install_dir):
    """Handles installation, script placement, and Desktop entry on Linux."""
    print("[*] Configuring Linux integration...")

    target_script = os.path.join(install_dir, "Focus.py")
    icon_path = os.path.join(install_dir, "icon.png")

    applications_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(applications_dir, exist_ok=True)
    desktop_file_path = os.path.join(applications_dir, f"{APP_NAME.lower()}.desktop")

    desktop_entry = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec=GDK_BACKEND=X11 python3 "{target_script}"
Icon={icon_path if os.path.exists(icon_path) else ""}
StartupWMClass=focusfinder
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

    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_copy = ["Focus.py", "icon.png", "icon.ico"]

    for file_name in files_to_copy:
        src = os.path.join(current_dir, file_name)
        if os.path.exists(src):
            shutil.copy(src, install_dir)
            print(f"    + Updated {file_name}")

    install_dependencies()

    if CURRENT_OS == "Windows":
        setup_windows(install_dir)
    elif CURRENT_OS == "Linux":
        setup_linux(install_dir)

    action_word = "Updated" if is_update else "Installed"
    print(f"\n[+] Success! {APP_NAME} has been successfully {action_word}.")
    print("[+] Press Enter to exit.")
    input()   