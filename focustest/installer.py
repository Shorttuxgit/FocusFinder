#!/bin/python3
import os
import sys
import platform
import subprocess
import shutil
import urllib.request
import tempfile

CURRENT_OS = platform.system()
APP_NAME = "FocusFinder"


def print_welcome_instructions():
    """Prints platform-specific guidance right at the start of execution."""
    print(f"--- {APP_NAME} Installer & Updater ({CURRENT_OS}) ---")
    print("=" * 60)
    if CURRENT_OS == "Windows":
        print(" [INFO] Windows Installation Notes:")
        print("  - Setting up application files locally in your AppData folder.")
        print("  - Creating a Start Menu shortcut using an isolated environment.")
    elif CURRENT_OS == "Linux":
        print(" [INFO] Linux Installation Notes:")
        print("  - Creating an isolated Python virtual environment (venv) to comply")
        print("    with modern system package protection policies (PEP 668).")
        print("  - Automatically bootstrapping pip inside the isolated environment.")
        print("  - Setting up a desktop shortcut in your local applications folder.")
    else:
        print(f" [INFO] Running installer on unsupported/other OS: {CURRENT_OS}")
    print("=" * 60)
    print()


def get_install_dir():
    """Returns the correct installation directory based on the OS."""
    if CURRENT_OS == "Windows":
        app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(app_data, APP_NAME)
    elif CURRENT_OS == "Linux":
        return os.path.expanduser(f"~/.local/share/{APP_NAME.lower()}")
    return None


def setup_venv(install_dir):
    """Sets up an isolated Python virtual environment and ensures pip is available."""
    print("[*] Setting up isolated Python virtual environment...")
    venv_dir = os.path.join(install_dir, "venv")
    
    if not os.path.exists(venv_dir):
        try:
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        except Exception as e:
            print(f"[!] Error creating virtual environment: {e}")
            if CURRENT_OS == "Linux":
                print("[!] Hint: Ensure venv support is installed on your system.")
                print("    - Ubuntu/Debian: sudo apt install python3-full python3-venv")
                print("    - Fedora: sudo dnf install python3-virtualenv")
            sys.exit(1)

    # Determine executable paths inside the venv
    if CURRENT_OS == "Windows":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        venv_pythonw = os.path.join(venv_dir, "Scripts", "pythonw.exe")
        venv_pip = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        venv_pythonw = venv_python
        venv_pip = os.path.join(venv_dir, "bin", "pip")

    # Bootstrap pip if it's missing had to add due to some Linux distributions not including it in venv by default
    if not os.path.exists(venv_pip):
        print("[*] Bootstrapping pip inside virtual environment...")
        try:
            # Try ensurepip first
            subprocess.run([venv_python, "-m", "ensurepip", "--default-pip"], check=True, capture_output=True)
        except Exception:
            # Fallback: Download and run get-pip.py
            try:
                get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
                    urllib.request.urlretrieve(get_pip_url, tmp.name)
                    subprocess.check_call([venv_python, tmp.name])
                    os.unlink(tmp.name)
            except Exception as ex:
                print(f"[!] Critical Error: Could not bootstrap pip: {ex}")
                sys.exit(1)

    return venv_python, venv_pythonw, venv_pip


def setup_windows(install_dir, venv_pythonw):
    """Handles installation, script placement, and Start Menu shortcut on Windows."""
    print("[*] Configuring Windows integration...")

    target_script = os.path.join(install_dir, "main.pyw")
    icon_path = os.path.join(install_dir, "icon.ico")

    pythonw = venv_pythonw if os.path.exists(venv_pythonw) else venv_pythonw.replace("pythonw.exe", "python.exe")

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
    print(f"    + Using virtual environment interpreter: {pythonw}")


def setup_linux(install_dir, venv_python):
    """Handles installation, script placement, and Desktop entry on Linux."""
    print("[*] Configuring Linux integration...")

    target_script = os.path.join(install_dir, "main.py")
    icon_path = os.path.join(install_dir, "icon.png")

    applications_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(applications_dir, exist_ok=True)
    desktop_file_path = os.path.join(applications_dir, f"{APP_NAME.lower()}.desktop")

    desktop_entry = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec=env GDK_BACKEND=X11 {venv_python} "{target_script}"
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
    print(f"    + Using virtual environment interpreter: {venv_python}")


def install_dependencies(venv_pip, venv_python):
    """Installs required Python packages inside the isolated virtual environment."""
    print("[*] Installing required Python packages in isolated environment (customtkinter, playwright)...")
    try:
        subprocess.check_call([venv_pip, "install", "--upgrade", "pip", "customtkinter", "playwright"])
        print("[*] Ensuring Playwright Chromium browser binaries are up to date...")
        subprocess.check_call([venv_python, "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"[!] Warning during dependency installation: {e}")


if __name__ == "__main__":
    print_welcome_instructions()

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

    # Copy root files
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

    # Copy the entire src subfolder 
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

    # Clean up legacy files
    legacy_files = ["Focus.py", "Focus.pyw", "focus.py", "focus.pyw", "main.py"] if CURRENT_OS == "Windows" else ["Focus.py", "Focus.pyw", "focus.py", "focus.pyw"]
    for legacy in legacy_files:
        legacy_path = os.path.join(install_dir, legacy)
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
                print(f"    + Cleaned up legacy {legacy}")
            except Exception as e:
                print(f"[!] Warning: Could not remove old {legacy}: {e}")

    # Set up venv, bootstrap pip if needed, and install dependencies locally
    venv_python, venv_pythonw, venv_pip = setup_venv(install_dir)
    install_dependencies(venv_pip, venv_python)

    if CURRENT_OS == "Windows":
        setup_windows(install_dir, venv_pythonw)
    elif CURRENT_OS == "Linux":
        setup_linux(install_dir, venv_python)

    action_word = "Updated" if is_update else "Installed"
    print(f"\n[+] Success! {APP_NAME} has been successfully {action_word}.")
    print("[+] Press Enter to exit.")
    input()