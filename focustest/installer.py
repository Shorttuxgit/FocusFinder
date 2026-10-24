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

    # Target the .pyw version for Windows background execution
    target_script = os.path.join(install_dir, "main.pyw")
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

    target_script = os.path.join(install_dir, "main.py")
    icon_path = os.path.join(install_dir, "icon.png")
    python_path = shutil.which("python3") or "/usr/bin/python3"

    applications_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(applications_dir, exist_ok=True)
    desktop_file_path = os.path.join(applications_dir, f"{APP_NAME.lower()}.desktop")

    desktop_entry = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec=env GDK_BACKEND=X11 {python_path} "{target_script}"
Path={install_dir}
Icon={icon_path if os.path.exists(icon_path) else ""}
StartupWMClass=focusfinder
Terminal=false
Categories=Education;Utility;
"""

    with open(desktop_file_path, "w") as f:
        f.write(desktop_entry)

    os.chmod(desktop_file_path, 0o755)

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", applications_dir], capture_output=True)

    print(f"    + Desktop entry created: {desktop_file_path}")


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

    #Copy root files (Handle main.py -> main.pyw conversion on Windows)
    root_files_to_copy = ["main.py", "icon.png", "icon.ico"]
    for file_name in root_files_to_copy:
        src = os.path.join(current_dir, file_name)
        if os.path.exists(src):
            if file_name == "main.py" and CURRENT_OS == "Windows":
                dst = os.path.join(install_dir, "main.pyw")
                shutil.copy(src, dst)
                print("    + Updated main.pyw (Windows GUI mode)")
            else:
                shutil.copy(src, install_dir)
                print(f"    + Updated {file_name}")

    #Copy the entire src subfolder 
    local_src_dir = os.path.join(current_dir, "src")
    install_src_dir = os.path.join(install_dir, "src")
    
    if os.path.exists(local_src_dir):
        os.makedirs(install_src_dir, exist_ok=True)
        for item in os.listdir(local_src_dir):
            s = os.path.join(local_src_dir, item)
            d = os.path.join(install_src_dir, item)
            if os.path.isfile(s):
                shutil.copy(s, d)
                print(f"    + Updated src/{item}")
            elif os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
                print(f"    + Updated src/{item}/ directory")

    #Clean up legacy
    legacy_files = ["Focus.py", "Focus.pyw", "focus.py", "focus.pyw", "main.py"] if CURRENT_OS == "Windows" else ["Focus.py", "Focus.pyw", "focus.py", "focus.pyw"]
    for legacy in legacy_files:
        legacy_path = os.path.join(install_dir, legacy)
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
                print(f"    + Cleaned up legacy {legacy}")
            except Exception as e:
                print(f"[!] Warning: Could not remove old {legacy}: {e}")

    install_dependencies()

    if CURRENT_OS == "Windows":
        setup_windows(install_dir)
    elif CURRENT_OS == "Linux":
        setup_linux(install_dir)

    action_word = "Updated" if is_update else "Installed"
    print(f"\n[+] Success! {APP_NAME} has been successfully {action_word}.")
    print("[+] Press Enter to exit.")
    input()