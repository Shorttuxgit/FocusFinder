#!/usr/bin/env python3
# --------------------------------------------------
# FocusFinder installer: install, update and uninstall (Windows and Linux)
# --------------------------------------------------

import os
import re
import sys
import shutil
import platform
import subprocess
import tempfile
from pathlib import Path


# --------------------------------------------------
# Release settings
# --------------------------------------------------

APP_NAME = "focusfinder"
DISPLAY_NAME = "FocusFinder"
APP_ID = "focusfinder"
APP_USER_MODEL_ID = "uk.shortclaws.focusfinder"   # must match main.py
PACKAGE_NAME = "FocusPY"
VERSION = "1.1.0"

# Rebuild application files and the virtual environment during updates.
CLEAN_INSTALL = True

# Delete saved settings, timetables, friends and sessions during clean updates.
# This setting requires CLEAN_INSTALL to be True.
WIPE_USER_DATA = True

CURRENT_OS = platform.system()

# Where this installer was run from (the downloaded FocusPY folder)
SOURCE_DIR = Path(__file__).resolve().parent
SOURCE_MAIN = SOURCE_DIR / "main.py"
SOURCE_SRC = SOURCE_DIR / "src"

# Installed when there is no requirements.txt
REQUIRED_PACKAGES = ["customtkinter", "playwright"]

# Files, file types and folders treated as saved user data
USER_DATA_FILES = {"session.json", "timetable_cache.json", "friends_cache.json", "config.json"}
PRESERVE_SUFFIXES = {".json", ".db", ".sqlite", ".sqlite3", ".ini", ".toml", ".fff"}
PRESERVE_DIRECTORIES = {"userdata", "user_data", "user-data", "saves"}

# Files that are never copied into the installation
IGNORE_PATTERNS = shutil.ignore_patterns(
    "installer.py", "__pycache__", "*.pyc", "*.pyo", ".git", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
)


# --------------------------------------------------
# Installation paths
# --------------------------------------------------

def get_data_home():
    """Return the platform-specific application data directory."""
    if CURRENT_OS == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    if CURRENT_OS == "Linux":
        return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return None


def get_install_dir():
    """Return the canonical installation directory."""
    base_dir = get_data_home()
    return base_dir / APP_NAME if base_dir else None


def get_existing_install_dir():
    """Find the current installation, including the previous mixed-case path."""
    canonical = get_install_dir()
    legacy = canonical.parent / "FocusFinder"

    if not canonical.exists() and legacy.exists():
        return legacy
    return canonical


def get_linux_applications_dir():
    return get_data_home() / "applications"


def get_windows_start_menu():
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"


# --------------------------------------------------
# Validation and version checking
# --------------------------------------------------

def validate_configuration():
    """Validate release configuration."""
    if WIPE_USER_DATA and not CLEAN_INSTALL:
        raise ValueError("WIPE_USER_DATA can only be enabled when CLEAN_INSTALL is True.")
    parse_version(VERSION)


def validate_source():
    """Check that the application source folder is complete."""
    if not SOURCE_MAIN.is_file():
        raise FileNotFoundError(f"Could not find main.py beside installer.py:\n{SOURCE_MAIN}")
    if not SOURCE_SRC.is_dir():
        raise FileNotFoundError(f"Could not find the src folder:\n{SOURCE_SRC}")


def validate_install_location(install_dir):
    """Ensure destructive operations target a recognised installation path."""
    if install_dir.name not in {APP_NAME, "FocusFinder"}:
        raise ValueError("Invalid installation directory.")
    if install_dir.parent.resolve() != get_data_home().resolve():
        raise ValueError("Installation directory is outside the expected location.")


def refuse_to_run_from_install(install_dir):
    """The installer must be run from the download, not from the installed copy."""
    if SOURCE_DIR.resolve() == (install_dir / PACKAGE_NAME).resolve():
        raise RuntimeError(
            "Run installer.py from the downloaded FocusPY folder, "
            "not from the installed application."
        )


def parse_version(version):
    """Parse a numeric release version such as 1.2.3 into (1, 2, 3)."""
    version = str(version).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise ValueError(f"Invalid version '{version}'. Use numeric versions such as 1.2.3.")
    return tuple(int(part) for part in version.split("."))


def compare_versions(first, second):
    """Return -1, 0 or 1 after comparing version components."""
    a, b = parse_version(first), parse_version(second)
    length = max(len(a), len(b))
    a += (0,) * (length - len(a))
    b += (0,) * (length - len(b))
    return (a > b) - (a < b)


def get_installed_version(install_dir):
    """Read the installed version ("Unknown" if there is none)."""
    try:
        return (install_dir / "version.txt").read_text(encoding="utf-8").strip() or "Unknown"
    except OSError:
        return "Unknown"


def save_installed_version(install_dir):
    """Record the installed version."""
    (install_dir / "version.txt").write_text(VERSION + "\n", encoding="utf-8")


def check_installed_version(install_dir):
    """Prevent installation of an older release. Returns False to stop."""
    if not (install_dir / PACKAGE_NAME).is_dir():
        return True

    installed = get_installed_version(install_dir)
    print(f"Installed version: {installed}")
    print(f"Installer version: {VERSION}")

    # An install from before version numbers were recorded
    if installed == "Unknown":
        if CLEAN_INSTALL:
            print("[!] This is a legacy installation without version information.")
            print("[!] It will be handled using the configured clean-install process.")
            return True

        print("\n[!] INSTALLER BLOCKED")
        print("This installation has no recorded version, so its age cannot be verified.")
        print("This release has CLEAN_INSTALL disabled; refusing to continue safely.")
        return False

    try:
        comparison = compare_versions(VERSION, installed)
    except ValueError:
        print("\n[!] INSTALLER BLOCKED")
        print(f"The installed version number '{installed}' is not recognised.")
        print("Please install a valid newer release or resolve the version file first.")
        return False

    if comparison < 0:
        print("\n[!] INSTALLER BLOCKED — THIS IS AN OLDER VERSION")
        print(f"You currently have FocusFinder {installed} installed.")
        print(f"This installer contains FocusFinder {VERSION}.")
        print("Please download the latest release before continuing.")
        return False

    print("[+] This installer matches the installed version." if comparison == 0
          else "[+] This installer is newer than the installed version.")
    return True


# --------------------------------------------------
# User data backup and restoration
# --------------------------------------------------

def should_preserve_file(path, package_dir):
    """Identify files that may contain user data."""
    relative = path.relative_to(package_dir)

    return (
        path.name.lower() in USER_DATA_FILES
        or path.suffix.lower() in PRESERVE_SUFFIXES
        or any(part.lower() in PRESERVE_DIRECTORIES for part in relative.parts)
    )


def backup_user_data(package_dir, backup_dir):
    """Copy recognised user data to a temporary directory."""
    if not package_dir.exists():
        return

    for path in package_dir.rglob("*"):
        if path.is_file() and should_preserve_file(path, package_dir):
            target = backup_dir / path.relative_to(package_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def restore_user_data(package_dir, backup_dir):
    """Restore backed-up user data."""
    if not backup_dir.exists():
        return

    for path in backup_dir.rglob("*"):
        if path.is_file():
            target = package_dir / path.relative_to(backup_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def describe_user_data_wipe():
    """Describe the user data that will be removed."""
    print("\nUSER DATA REMOVAL")
    print("This release is configured to remove saved application data, including:")
    print("  - Application settings and configuration")
    print("  - Cached timetables")
    print("  - Saved friends and shared timetable data")
    print("  - Login/session information")
    print("  - Other recognised saved-data files and folders")
    print("\nThis data will NOT be backed up or restored.")


# --------------------------------------------------
# Application files
# --------------------------------------------------

def copy_files(install_package):
    # Copy the downloaded folder over the installed one (skipping IGNORE_PATTERNS)
    shutil.copytree(SOURCE_DIR, install_package, dirs_exist_ok=True, ignore=IGNORE_PATTERNS)


def copy_application(install_dir, preserve_data=False):
    """Copy application files into the installation directory."""
    print("[*] Copying application files...")

    refuse_to_run_from_install(install_dir)
    install_package = install_dir / PACKAGE_NAME

    if preserve_data:
        # Back up saved data, copy the new files over, then put the data back
        with tempfile.TemporaryDirectory(prefix="focusfinder-update-") as temporary:
            backup_dir = Path(temporary)
            backup_user_data(install_package, backup_dir)
            try:
                copy_files(install_package)
            finally:
                restore_user_data(install_package, backup_dir)
    else:
        copy_files(install_package)

    # Windows starts the app from a .pyw file so no console window appears
    if CURRENT_OS == "Windows":
        shutil.copy2(install_package / "main.py", install_package / "main.pyw")
        print("    + Created Windows GUI entry point.")

    print(f"    + Application copied to: {install_package}")
    return install_package


# --------------------------------------------------
# Virtual environment and dependencies
# --------------------------------------------------

def run(*command, quiet=False):
    # Run a command and stop with an error if it fails
    output = subprocess.DEVNULL if quiet else None
    subprocess.run([str(part) for part in command], check=True, stdout=output, stderr=output)


def setup_venv(install_dir):
    """Create or reuse the application's virtual environment."""
    print("[*] Setting up virtual environment...")

    venv_dir = install_dir / "venv"
    scripts = venv_dir / ("Scripts" if CURRENT_OS == "Windows" else "bin")
    venv_python = scripts / ("python.exe" if CURRENT_OS == "Windows" else "python")
    venv_pythonw = scripts / "pythonw.exe" if CURRENT_OS == "Windows" else venv_python

    if not venv_python.exists():
        print("    + Creating virtual environment...")
        run(sys.executable, "-m", "venv", venv_dir)

    if not venv_python.exists():
        raise FileNotFoundError(f"Virtual environment Python was not created:\n{venv_python}")

    run(venv_python, "-m", "ensurepip", "--upgrade", quiet=True)
    return venv_python, venv_pythonw


def install_dependencies(venv_python, install_package):
    """Install or update application dependencies."""
    print("[*] Installing Python dependencies...")
    run(venv_python, "-m", "pip", "install", "--upgrade", "pip")

    # Use requirements.txt when the release includes one
    requirements = install_package / "requirements.txt"
    if requirements.exists():
        run(venv_python, "-m", "pip", "install", "-r", requirements)
    else:
        run(venv_python, "-m", "pip", "install", *REQUIRED_PACKAGES)

    # Needed to give the Windows shortcut its application identity
    if CURRENT_OS == "Windows":
        print("[*] Installing Windows integration dependencies...")
        run(venv_python, "-m", "pip", "install", "--upgrade", "pywin32")

    print("[*] Installing Playwright Chromium...")
    run(venv_python, "-m", "playwright", "install", "chromium")


# --------------------------------------------------
# Windows integration
# --------------------------------------------------

def powershell_literal(value):
    """Safely quote a string for PowerShell."""
    return "'" + str(value).replace("'", "''") + "'"


def set_windows_shortcut_app_id(venv_python, shortcut_path):
    """Assign the FocusFinder AppUserModelID to a Windows shortcut."""
    print("[*] Assigning Windows application identity...")

    # Small script run inside the virtual environment (where pywin32 is installed)
    script = r'''
import sys
import pythoncom

from win32com.propsys import propsys, pscon
from win32com.shell import shellcon

shortcut_path = sys.argv[1]
app_id = sys.argv[2]

property_store = propsys.SHGetPropertyStoreFromParsingName(
    shortcut_path,
    None,
    shellcon.GPS_READWRITE,
    propsys.IID_IPropertyStore,
)

property_store.SetValue(
    pscon.PKEY_AppUserModel_ID,
    propsys.PROPVARIANTType(app_id, pythoncom.VT_LPWSTR),
)

property_store.Commit()
'''
    run(venv_python, "-c", script, shortcut_path, APP_USER_MODEL_ID)
    print("    + AppUserModelID assigned successfully.")


def setup_windows(install_package, venv_python, venv_pythonw):
    """Create a Windows Start Menu shortcut with the correct application identity."""
    print("[*] Creating Windows shortcut...")

    pythonw = venv_pythonw if venv_pythonw.exists() else venv_python
    target_script = install_package / "main.pyw"
    icon_path = install_package / "icon.ico"

    start_menu = get_windows_start_menu()
    start_menu.mkdir(parents=True, exist_ok=True)
    shortcut_path = start_menu / f"{APP_ID}.lnk"

    icon_line = f"$Shortcut.IconLocation = {powershell_literal(icon_path)}" if icon_path.exists() else ""

    # PowerShell creates the .lnk file
    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut({powershell_literal(shortcut_path)})
$Shortcut.TargetPath = {powershell_literal(pythonw)}
$Shortcut.Arguments = {powershell_literal('"' + str(target_script) + '"')}
$Shortcut.WorkingDirectory = {powershell_literal(install_package)}
{icon_line}
$Shortcut.Save()
"""
    run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershell_script)

    # Assign the same identity used by main.py
    set_windows_shortcut_app_id(venv_python, shortcut_path)
    print(f"    + Shortcut created: {shortcut_path}")


# --------------------------------------------------
# Linux integration
# --------------------------------------------------

def desktop_quote(value):
    """Escape a path for use in a desktop entry."""
    value = str(value)
    for char, replacement in (("\\", "\\\\"), ('"', '\\"'), ("`", "\\`"), ("$", "\\$")):
        value = value.replace(char, replacement)
    return f'"{value}"'


def refresh_desktop_database(applications_dir):
    # Lets the desktop notice the new / removed shortcut (skipped if the tool is missing)
    update_database = shutil.which("update-desktop-database")
    if update_database and applications_dir.exists():
        subprocess.run([update_database, str(applications_dir)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def setup_linux(install_package, venv_python):
    """Create a Linux desktop application shortcut."""
    print("[*] Creating Linux desktop shortcut...")

    applications_dir = get_linux_applications_dir()
    applications_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = applications_dir / f"{APP_ID}.desktop"

    target_script = install_package / "main.py"
    icon_path = install_package / "icon.png"

    exec_command = f"env GDK_BACKEND=X11 {desktop_quote(venv_python)} {desktop_quote(target_script)}"

    entry = [
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        f"Name={DISPLAY_NAME}",
        f"Exec={exec_command}",
        f"Path={install_package}",
        f"Icon={icon_path}" if icon_path.exists() else "",
        f"StartupWMClass={APP_ID}",
        "Terminal=false",
        "Categories=Education;Utility;",
    ]

    desktop_file.write_text("\n".join(line for line in entry if line) + "\n", encoding="utf-8")
    desktop_file.chmod(0o755)
    refresh_desktop_database(applications_dir)

    print(f"    + Created: {desktop_file}")


# --------------------------------------------------
# Shortcut and installation removal
# --------------------------------------------------

def remove_shortcuts():
    """Remove FocusFinder shortcuts from the operating system."""
    print("[*] Removing application shortcuts...")

    if CURRENT_OS == "Windows":
        shortcut = get_windows_start_menu() / f"{APP_ID}.lnk"
        if shortcut.exists():
            shortcut.unlink()
            print(f"    + Removed: {shortcut}")

    elif CURRENT_OS == "Linux":
        for applications_dir in {get_linux_applications_dir(), Path.home() / ".local" / "share" / "applications"}:
            desktop_file = applications_dir / f"{APP_ID}.desktop"
            if desktop_file.exists():
                desktop_file.unlink()
                print(f"    + Removed: {desktop_file}")
            refresh_desktop_database(applications_dir)


def remove_installation(install_dir):
    """Remove a complete FocusFinder installation directory."""
    validate_install_location(install_dir)

    if install_dir.is_symlink():
        install_dir.unlink()
    elif install_dir.exists():
        shutil.rmtree(install_dir)

    print(f"    + Removed installation directory: {install_dir}")


def confirm_action(message):
    """Require explicit confirmation for destructive operations."""
    print()
    print(message)
    print("Type YES to continue.")
    return input("> ").strip() == "YES"


# --------------------------------------------------
# Installation modes
# --------------------------------------------------

def finish_installation(install_dir):
    """Install dependencies, create shortcuts and record the release version."""
    install_package = install_dir / PACKAGE_NAME
    venv_python, venv_pythonw = setup_venv(install_dir)

    install_dependencies(venv_python, install_package)

    if CURRENT_OS == "Windows":
        setup_windows(install_package, venv_python, venv_pythonw)
    else:
        setup_linux(install_package, venv_python)

    save_installed_version(install_dir)


def install_application(existing_dir):
    """Perform a completely fresh installation."""
    validate_source()
    refuse_to_run_from_install(existing_dir)

    new_dir = get_install_dir()

    # Always remove an existing installation (including an old mixed-case one) before copying
    for old_dir in {existing_dir, new_dir}:
        if old_dir.exists():
            print("[*] Removing existing installation...")
            remove_shortcuts()
            remove_installation(old_dir)

    new_dir.mkdir(parents=True, exist_ok=True)
    copy_application(new_dir)
    finish_installation(new_dir)


def clean_update_application(old_install_dir):
    """Rebuild the installation while preserving or wiping user data."""
    validate_source()
    refuse_to_run_from_install(old_install_dir)

    new_install_dir = get_install_dir()
    old_package = old_install_dir / PACKAGE_NAME
    backup_dir = None

    if WIPE_USER_DATA:
        print("[!] WIPE_USER_DATA is enabled. No user data backup will be made.")
    else:
        backup_dir = Path(tempfile.mkdtemp(prefix="focusfinder-user-data-"))
        backup_user_data(old_package, backup_dir)
        print(f"[*] User data backed up temporarily: {backup_dir}")

    try:
        remove_shortcuts()
        remove_installation(old_install_dir)

        new_install_dir.mkdir(parents=True, exist_ok=True)
        copy_application(new_install_dir)

        if backup_dir is not None:
            restore_user_data(new_install_dir / PACKAGE_NAME, backup_dir)

        finish_installation(new_install_dir)

    except Exception:
        # Keep the backup so nothing is lost if the update fails half-way
        if backup_dir is not None:
            print("\n[!] The clean update did not finish successfully.")
            print("[!] Your user-data backup has been retained at:")
            print(f"    {backup_dir}")
            print("[!] Do not delete that folder until your data has been recovered.")
        raise

    else:
        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)


def update_application(install_dir):
    """Update FocusFinder using the configured update strategy."""
    validate_source()

    if not (install_dir / PACKAGE_NAME).is_dir():
        raise FileNotFoundError(
            "No existing FocusFinder installation was found.\n"
            "Choose Install / Reinstall instead."
        )

    print(f"[*] Installed version: {get_installed_version(install_dir)}")
    print(f"[*] New version: {VERSION}")
    print()

    if CLEAN_INSTALL:
        print("[*] This release is configured for a clean installation.")
        clean_update_application(install_dir)
        return

    # In-place update: new files go over the old ones, saved data is kept
    copy_application(install_dir, preserve_data=True)
    finish_installation(install_dir)


def uninstall_application(install_dir):
    """Completely remove FocusFinder."""
    remove_shortcuts()

    if install_dir.exists():
        remove_installation(install_dir)
    else:
        print("[*] No installation directory was found.")

    print("\n[+] FocusFinder has been uninstalled.")


# --------------------------------------------------
# Menu choices
# --------------------------------------------------

def banner(*lines):
    # Print lines between two rows of "="
    print("\n" + "=" * 60)
    for line in lines:
        print(line)
    print("=" * 60)


def choose_install(install_dir):
    if install_dir.exists() and not confirm_action(
        "This will completely remove the existing installation, "
        "including saved data inside its installation folder, "
        "before installing a fresh copy.\n"
        "Type YES only if you are happy to proceed."
    ):
        print("\n[*] Installation cancelled.")
        return

    install_application(install_dir)

    banner(
        f"[+] {DISPLAY_NAME} successfully installed!",
        f"    Version: {VERSION}",
        f"    Location: {get_install_dir()}",
        "    Launch it from your applications menu.",
    )


def choose_update(install_dir, installed):
    if not installed:
        print("\n[!] FocusFinder is not currently installed.")
        print("[!] Choose Install / Reinstall instead.")
        return 1

    if CLEAN_INSTALL:
        banner("THIS UPDATE REQUIRES A CLEAN INSTALLATION")
        print("The existing application files and virtual environment will be removed.")

        warning = ""
        if WIPE_USER_DATA:
            describe_user_data_wipe()
            warning = (
                "\nWARNING: Your saved FocusFinder data will also be "
                "permanently deleted. This cannot be undone."
            )
        else:
            print("\nYour recognised saved data will be backed up and restored.")

        if not confirm_action("This update will rebuild FocusFinder from scratch." + warning):
            print("\n[*] Update cancelled. Nothing has been changed.")
            return 0

    update_application(install_dir)

    saved_data = (
        "    Saved application data was wiped as requested by this release."
        if WIPE_USER_DATA else
        "    Recognised saved data has been preserved."
    )
    banner(f"[+] {DISPLAY_NAME} successfully updated!", f"    Version: {VERSION}", saved_data)
    return 0


def choose_uninstall(install_dir):
    if not confirm_action(
        "This will permanently remove FocusFinder, including its "
        "virtual environment, saved data and shortcuts."
    ):
        print("\n[*] Uninstallation cancelled.")
        return

    uninstall_application(install_dir)


# --------------------------------------------------
# Main menu
# --------------------------------------------------

def main():
    banner(
        f"             {DISPLAY_NAME} Installer",
        f"             Version: {VERSION}",
        f"             Operating system: {CURRENT_OS}",
    )

    if CURRENT_OS not in ("Windows", "Linux"):
        print("\n[!] This operating system is not supported.")
        return 1

    try:
        validate_configuration()
    except ValueError as error:
        print(f"\n[!] RELEASE CONFIGURATION ERROR: {error}")
        return 1

    install_dir = get_existing_install_dir()
    installed = (install_dir / PACKAGE_NAME).is_dir()

    # Stop before showing the menu if this installer is older than what is installed
    if not check_installed_version(install_dir):
        return 1

    print()
    print(f"Installation directory: {install_dir}")
    print(f"Installed version: {get_installed_version(install_dir) if installed else 'Not installed'}")
    print()
    print("-" * 60)
    print("  1. Install / Reinstall")
    print("  2. Update")
    print("  3. Uninstall")
    print("  4. Exit")
    print("-" * 60)

    try:
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            choose_install(install_dir)
        elif choice == "2":
            return choose_update(install_dir, installed)
        elif choice == "3":
            choose_uninstall(install_dir)
        elif choice == "4":
            print("\n[*] Exiting installer.")
        else:
            print("\n[!] Invalid selection.")
            return 1

        return 0

    except Exception as error:
        banner("[!] OPERATION FAILED", "", str(error))
        return 1


if __name__ == "__main__":
    exit_code = main()

    # Keep the window open when started by double-clicking
    if sys.stdin.isatty():
        input("\nPress Enter to exit...")

    sys.exit(exit_code)