
#!/usr/bin/env python3

import os
import re
import sys
import shutil
import platform
import subprocess
import tempfile
from pathlib import Path


# --------------------------------------------------
# Configuration
# --------------------------------------------------

APP_NAME = "focusfinder"
DISPLAY_NAME = "FocusFinder"
APP_ID = "focusfinder"
APP_USER_MODEL_ID = "uk.shortclaws.focusfinder"

PACKAGE_NAME = "FocusPY"

VERSION = "1.1.0"

# Rebuild application files and the virtual environment during updates.
CLEAN_INSTALL = True

# Delete saved settings, timetables, friends and sessions during clean updates.
# This setting requires CLEAN_INSTALL to be True.
WIPE_USER_DATA = True

CURRENT_OS = platform.system()

SOURCE_DIR = Path(__file__).resolve().parent
SOURCE_MAIN = SOURCE_DIR / "main.py"
SOURCE_SRC = SOURCE_DIR / "src"

REQUIRED_PACKAGES = [
    "customtkinter",
    "playwright",
]

USER_DATA_FILES = {
    "session.json",
    "timetable_cache.json",
    "friends_cache.json",
    "config.json",
}

PRESERVE_SUFFIXES = {
    ".json",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".ini",
    ".toml",
    ".fff",
}

PRESERVE_DIRECTORIES = {
    "userdata",
    "user_data",
    "user-data",
    "saves",
}

IGNORE_PATTERNS = shutil.ignore_patterns(
    "installer.py",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


# --------------------------------------------------
# Installation paths
# --------------------------------------------------

def get_data_home():
    """Return the platform-specific application data directory."""

    if CURRENT_OS == "Windows":
        return Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local",
            )
        )

    if CURRENT_OS == "Linux":
        return Path(
            os.environ.get(
                "XDG_DATA_HOME",
                Path.home() / ".local" / "share",
            )
        )

    return None


def get_install_dir():
    """Return the canonical installation directory."""

    base_dir = get_data_home()
    return base_dir / APP_NAME if base_dir else None


def get_existing_install_dir():
    """Find the current installation, including the previous mixed-case path."""

    canonical_dir = get_install_dir()
    legacy_dir = canonical_dir.parent / "FocusFinder"

    if canonical_dir.exists():
        return canonical_dir

    if legacy_dir.exists():
        return legacy_dir

    return canonical_dir


def get_linux_applications_dir():
    return get_data_home() / "applications"


def get_windows_start_menu():
    return (
        Path(
            os.environ.get(
                "APPDATA",
                Path.home() / "AppData" / "Roaming",
            )
        )
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )


# --------------------------------------------------
# Validation and version checking
# --------------------------------------------------

def validate_configuration():
    """Validate release configuration."""

    if WIPE_USER_DATA and not CLEAN_INSTALL:
        raise ValueError(
            "WIPE_USER_DATA can only be enabled when CLEAN_INSTALL is True."
        )

    parse_version(VERSION)


def validate_source():
    """Check that the application source folder is complete."""

    if not SOURCE_MAIN.is_file():
        raise FileNotFoundError(
            f"Could not find main.py beside installer.py:\n{SOURCE_MAIN}"
        )

    if not SOURCE_SRC.is_dir():
        raise FileNotFoundError(
            f"Could not find the src folder:\n{SOURCE_SRC}"
        )


def validate_install_location(install_dir):
    """Ensure destructive operations target a recognised installation path."""

    expected_parent = get_data_home().resolve()

    if install_dir.name not in {APP_NAME, "FocusFinder"}:
        raise ValueError("Invalid installation directory.")

    if install_dir.parent.resolve() != expected_parent:
        raise ValueError(
            "Installation directory is outside the expected location."
        )


def parse_version(version):
    """Parse a numeric release version."""

    version = str(version).strip()

    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise ValueError(
            f"Invalid version '{version}'. Use numeric versions such as 1.2.3."
        )

    return tuple(int(part) for part in version.split("."))


def compare_versions(first, second):
    """Return -1, 0 or 1 after comparing version components."""

    first_parts = parse_version(first)
    second_parts = parse_version(second)

    length = max(len(first_parts), len(second_parts))

    first_parts += (0,) * (length - len(first_parts))
    second_parts += (0,) * (length - len(second_parts))

    return (first_parts > second_parts) - (first_parts < second_parts)


def get_installed_version(install_dir):
    """Read the installed version."""

    version_file = install_dir / "version.txt"

    if not version_file.is_file():
        return "Unknown"

    try:
        version = version_file.read_text(encoding="utf-8").strip()
        return version or "Unknown"
    except OSError:
        return "Unknown"


def check_installed_version(install_dir):
    """Prevent installation of an older release."""

    package_dir = install_dir / PACKAGE_NAME

    if not install_dir.is_dir() or not package_dir.is_dir():
        return True

    installed_version = get_installed_version(install_dir)

    print(f"Installed version: {installed_version}")
    print(f"Installer version: {VERSION}")

    if installed_version == "Unknown":
        if CLEAN_INSTALL:
            print(
                "[!] This is a legacy installation without version information."
            )
            print(
                "[!] It will be handled using the configured clean-install process."
            )
            return True

        print("\n[!] INSTALLER BLOCKED")
        print(
            "This installation has no recorded version, "
            "so its age cannot be verified."
        )
        print(
            "This release has CLEAN_INSTALL disabled; "
            "refusing to continue safely."
        )
        return False

    try:
        comparison = compare_versions(VERSION, installed_version)

    except ValueError:
        print("\n[!] INSTALLER BLOCKED")
        print(
            f"The installed version number '{installed_version}' "
            "is not recognised."
        )
        print(
            "Please install a valid newer release "
            "or resolve the version file first."
        )
        return False

    if comparison < 0:
        print("\n[!] INSTALLER BLOCKED — THIS IS AN OLDER VERSION")
        print(f"You currently have FocusFinder {installed_version} installed.")
        print(f"This installer contains FocusFinder {VERSION}.")
        print("Please download the latest release before continuing.")
        return False

    if comparison == 0:
        print("[+] This installer matches the installed version.")
    else:
        print("[+] This installer is newer than the installed version.")

    return True


def save_installed_version(install_dir):
    """Record the installed version."""

    version_file = install_dir / "version.txt"
    version_file.write_text(VERSION + "\n", encoding="utf-8")


# --------------------------------------------------
# User data backup and restoration
# --------------------------------------------------

def should_preserve_file(path, package_dir):
    """Identify files that may contain user data."""

    relative_path = path.relative_to(package_dir)

    if path.name.lower() in USER_DATA_FILES:
        return True

    if path.suffix.lower() in PRESERVE_SUFFIXES:
        return True

    return any(
        part.lower() in PRESERVE_DIRECTORIES
        for part in relative_path.parts
    )


def backup_user_data(package_dir, backup_dir):
    """Copy recognised user data to a temporary directory."""

    if not package_dir.exists():
        return

    for path in package_dir.rglob("*"):

        if not path.is_file():
            continue

        if not should_preserve_file(path, package_dir):
            continue

        relative_path = path.relative_to(package_dir)
        backup_path = backup_dir / relative_path

        backup_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(path, backup_path)


def restore_user_data(package_dir, backup_dir):
    """Restore backed-up user data."""

    if not backup_dir.exists():
        return

    for path in backup_dir.rglob("*"):

        if not path.is_file():
            continue

        relative_path = path.relative_to(backup_dir)
        destination = package_dir / relative_path

        destination.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(path, destination)


def describe_user_data_wipe():
    """Describe the user data that will be removed."""

    print("\nUSER DATA REMOVAL")
    print(
        "This release is configured to remove saved application data, "
        "including:"
    )
    print("  - Application settings and configuration")
    print("  - Cached timetables")
    print("  - Saved friends and shared timetable data")
    print("  - Login/session information")
    print("  - Other recognised saved-data files and folders")
    print("\nThis data will NOT be backed up or restored.")


# --------------------------------------------------
# Application files
# --------------------------------------------------

def copy_application(install_dir, preserve_data=False):
    """Copy application files into the installation directory."""

    print("[*] Copying application files...")

    install_package = install_dir / PACKAGE_NAME

    if SOURCE_DIR.resolve() == install_package.resolve():
        raise RuntimeError(
            "Run installer.py from the downloaded FocusPY folder, "
            "not from the installed application."
        )

    if preserve_data:

        with tempfile.TemporaryDirectory(
            prefix="focusfinder-update-"
        ) as temporary:

            backup_dir = Path(temporary)

            backup_user_data(install_package, backup_dir)

            try:
                shutil.copytree(
                    SOURCE_DIR,
                    install_package,
                    dirs_exist_ok=True,
                    ignore=IGNORE_PATTERNS,
                )

            finally:
                restore_user_data(install_package, backup_dir)

    else:

        shutil.copytree(
            SOURCE_DIR,
            install_package,
            dirs_exist_ok=True,
            ignore=IGNORE_PATTERNS,
        )

    if CURRENT_OS == "Windows":
        shutil.copy2(
            install_package / "main.py",
            install_package / "main.pyw",
        )

        print("    + Created Windows GUI entry point.")

    print(f"    + Application copied to: {install_package}")

    return install_package


# --------------------------------------------------
# Virtual environment and dependencies
# --------------------------------------------------

def setup_venv(install_dir):
    """Create or reuse the application's virtual environment."""

    print("[*] Setting up virtual environment...")

    venv_dir = install_dir / "venv"

    if CURRENT_OS == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pythonw = venv_dir / "Scripts" / "pythonw.exe"

    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pythonw = venv_python

    if not venv_python.exists():

        print("    + Creating virtual environment...")

        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
        )

    if not venv_python.exists():
        raise FileNotFoundError(
            f"Virtual environment Python was not created:\n{venv_python}"
        )

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "ensurepip",
            "--upgrade",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return venv_python, venv_pythonw


def install_dependencies(venv_python, install_package):
    """Install or update application dependencies."""

    print("[*] Installing Python dependencies...")

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
        ],
        check=True,
    )

    requirements_file = install_package / "requirements.txt"

    if requirements_file.exists():

        subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_file),
            ],
            check=True,
        )

    else:

        subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                *REQUIRED_PACKAGES,
            ],
            check=True,
        )

    # Install Windows shortcut integration dependencies.
    if CURRENT_OS == "Windows":

        print("[*] Installing Windows integration dependencies...")

        subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pywin32",
            ],
            check=True,
        )

    print("[*] Installing Playwright Chromium...")

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        check=True,
    )


# --------------------------------------------------
# Windows integration
# --------------------------------------------------

def powershell_literal(value):
    """Safely quote a string for PowerShell."""

    return "'" + str(value).replace("'", "''") + "'"


def set_windows_shortcut_app_id(venv_python, shortcut_path):
    """Assign the FocusFinder AppUserModelID to a Windows shortcut."""

    print("[*] Assigning Windows application identity...")

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
    propsys.PROPVARIANTType(
        app_id,
        pythoncom.VT_LPWSTR,
    ),
)

property_store.Commit()
'''

    subprocess.run(
        [
            str(venv_python),
            "-c",
            script,
            str(shortcut_path),
            APP_USER_MODEL_ID,
        ],
        check=True,
    )

    print("    + AppUserModelID assigned successfully.")


def setup_windows(install_package, venv_python, venv_pythonw):
    """Create a Windows Start Menu shortcut with the correct application identity."""

    print("[*] Creating Windows shortcut...")

    pythonw = (
        venv_pythonw
        if venv_pythonw.exists()
        else venv_python
    )

    target_script = install_package / "main.pyw"
    icon_path = install_package / "icon.ico"

    start_menu = get_windows_start_menu()
    start_menu.mkdir(parents=True, exist_ok=True)

    shortcut_path = start_menu / f"{APP_ID}.lnk"

    icon_setting = ""

    if icon_path.exists():
        icon_setting = (
            f"$Shortcut.IconLocation = "
            f"{powershell_literal(icon_path)}"
        )

    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut({powershell_literal(shortcut_path)})
$Shortcut.TargetPath = {powershell_literal(pythonw)}
$Shortcut.Arguments = {powershell_literal('"' + str(target_script) + '"')}
$Shortcut.WorkingDirectory = {powershell_literal(install_package)}
{icon_setting}
$Shortcut.Save()
"""

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
        ],
        check=True,
    )

    # Assign the same identity used by main.py.
    set_windows_shortcut_app_id(
        venv_python,
        shortcut_path,
    )

    print(f"    + Shortcut created: {shortcut_path}")


# --------------------------------------------------
# Linux integration
# --------------------------------------------------

def desktop_quote(value):
    """Escape a path for use in a desktop entry."""

    value = str(value)

    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("`", "\\`")
    value = value.replace("$", "\\$")

    return f'"{value}"'


def setup_linux(install_package, venv_python):
    """Create a Linux desktop application shortcut."""

    print("[*] Creating Linux desktop shortcut...")

    applications_dir = get_linux_applications_dir()
    applications_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = applications_dir / f"{APP_ID}.desktop"

    target_script = install_package / "main.py"
    icon_path = install_package / "icon.png"

    exec_command = (
        f"env GDK_BACKEND=X11 "
        f"{desktop_quote(venv_python)} "
        f"{desktop_quote(target_script)}"
    )

    desktop_entry = [
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

    desktop_file.write_text(
        "\n".join(line for line in desktop_entry if line) + "\n",
        encoding="utf-8",
    )

    desktop_file.chmod(0o755)

    update_database = shutil.which("update-desktop-database")

    if update_database:

        subprocess.run(
            [
                update_database,
                str(applications_dir),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

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

        applications_dirs = {
            get_linux_applications_dir(),
            Path.home() / ".local" / "share" / "applications",
        }

        for applications_dir in applications_dirs:

            desktop_file = applications_dir / f"{APP_ID}.desktop"

            if desktop_file.exists():
                desktop_file.unlink()
                print(f"    + Removed: {desktop_file}")

            update_database = shutil.which("update-desktop-database")

            if update_database and applications_dir.exists():

                subprocess.run(
                    [
                        update_database,
                        str(applications_dir),
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


def remove_installation(install_dir):
    """Remove a complete FocusFinder installation directory."""

    validate_install_location(install_dir)

    if install_dir.is_symlink():
        install_dir.unlink()

    elif install_dir.exists():
        shutil.rmtree(install_dir)

    print(f"    + Removed installation directory: {install_dir}")


# --------------------------------------------------
# Confirmation
# --------------------------------------------------

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

    install_dependencies(
        venv_python,
        install_package,
    )

    if CURRENT_OS == "Windows":

        setup_windows(
            install_package,
            venv_python,
            venv_pythonw,
        )

    else:

        setup_linux(
            install_package,
            venv_python,
        )

    save_installed_version(install_dir)


def install_application(install_dir):
    """Perform a completely fresh installation."""

    validate_source()

    install_package = install_dir / PACKAGE_NAME

    if SOURCE_DIR.resolve() == install_package.resolve():
        raise RuntimeError(
            "Run installer.py from the downloaded FocusPY folder, "
            "not from the installed application."
        )

    # Always remove an existing installation before copying.
    if install_dir.exists():

        print("[*] Removing existing installation...")

        remove_shortcuts()
        remove_installation(install_dir)

    # Create a completely fresh installation directory.
    install_dir.mkdir(parents=True, exist_ok=True)

    copy_application(install_dir)

    finish_installation(install_dir)


def clean_update_application(old_install_dir):
    """Rebuild the installation while preserving or wiping user data."""

    validate_source()

    new_install_dir = get_install_dir()
    old_package = old_install_dir / PACKAGE_NAME

    if SOURCE_DIR.resolve() == old_package.resolve():
        raise RuntimeError(
            "Run installer.py from the downloaded FocusPY folder, "
            "not from the installed application."
        )

    backup_dir = None

    if not WIPE_USER_DATA:

        backup_dir = Path(
            tempfile.mkdtemp(
                prefix="focusfinder-user-data-"
            )
        )

        backup_user_data(
            old_package,
            backup_dir,
        )

        print(
            f"[*] User data backed up temporarily: {backup_dir}"
        )

    else:

        print(
            "[!] WIPE_USER_DATA is enabled. "
            "No user data backup will be made."
        )

    try:

        remove_shortcuts()
        remove_installation(old_install_dir)

        new_install_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        copy_application(new_install_dir)

        if backup_dir is not None:

            restore_user_data(
                new_install_dir / PACKAGE_NAME,
                backup_dir,
            )

        finish_installation(new_install_dir)

    except Exception:

        if backup_dir is not None:

            print("\n[!] The clean update did not finish successfully.")
            print("[!] Your user-data backup has been retained at:")
            print(f"    {backup_dir}")
            print(
                "[!] Do not delete that folder until your data "
                "has been recovered."
            )

        raise

    else:

        if backup_dir is not None:
            shutil.rmtree(
                backup_dir,
                ignore_errors=True,
            )


def update_application(install_dir):
    """Update FocusFinder using the configured update strategy."""

    validate_source()

    install_package = install_dir / PACKAGE_NAME

    if not install_package.is_dir():
        raise FileNotFoundError(
            "No existing FocusFinder installation was found.\n"
            "Choose Install / Reinstall instead."
        )

    previous_version = get_installed_version(install_dir)

    print(f"[*] Installed version: {previous_version}")
    print(f"[*] New version: {VERSION}")
    print()

    if CLEAN_INSTALL:

        print(
            "[*] This release is configured for a clean installation."
        )

        clean_update_application(install_dir)

        return

    install_package = copy_application(
        install_dir,
        preserve_data=True,
    )

    venv_python, venv_pythonw = setup_venv(install_dir)

    install_dependencies(
        venv_python,
        install_package,
    )

    if CURRENT_OS == "Windows":

        setup_windows(
            install_package,
            venv_python,
            venv_pythonw,
        )

    else:

        setup_linux(
            install_package,
            venv_python,
        )

    save_installed_version(install_dir)


def uninstall_application(install_dir):
    """Completely remove FocusFinder."""

    remove_shortcuts()

    if install_dir.exists():

        remove_installation(install_dir)

    else:

        print("[*] No installation directory was found.")

    print("\n[+] FocusFinder has been uninstalled.")


# --------------------------------------------------
# Main menu
# --------------------------------------------------

def main():
    print()
    print("=" * 60)
    print(f"             {DISPLAY_NAME} Installer")
    print(f"             Version: {VERSION}")
    print(f"             Operating system: {CURRENT_OS}")
    print("=" * 60)

    if CURRENT_OS not in ("Windows", "Linux"):

        print("\n[!] This operating system is not supported.")

        return 1

    try:

        validate_configuration()

    except ValueError as error:

        print(f"\n[!] RELEASE CONFIGURATION ERROR: {error}")

        return 1

    install_dir = get_existing_install_dir()

    installed = (
        install_dir.exists()
        and (install_dir / PACKAGE_NAME).is_dir()
    )

    # Check the installed version before displaying the menu.
    if not check_installed_version(install_dir):
        return 1

    installed_version = (
        get_installed_version(install_dir)
        if installed
        else "Not installed"
    )

    print()
    print(f"Installation directory: {install_dir}")
    print(f"Installed version: {installed_version}")
    print()
    print("-" * 60)
    print("  1. Install / Reinstall")
    print("  2. Update")
    print("  3. Uninstall")
    print("  4. Exit")
    print("-" * 60)

    try:

        choice = input("\nSelect an option: ").strip()

        # --------------------------------------------------
        # Install / Reinstall
        # --------------------------------------------------

        if choice == "1":

            if install_dir.exists():

                if not confirm_action(
                    "This will completely remove the existing installation, "
                    "including saved data inside its installation folder, "
                    "before installing a fresh copy.\n"
                    "Type YES only if you are happy to proceed."
                ):

                    print("\n[*] Installation cancelled.")

                    return 0

            install_application(install_dir)

            print("\n" + "=" * 60)
            print(f"[+] {DISPLAY_NAME} successfully installed!")
            print(f"    Version: {VERSION}")
            print(f"    Location: {get_install_dir()}")
            print("    Launch it from your applications menu.")
            print("=" * 60)

        # --------------------------------------------------
        # Update
        # --------------------------------------------------

        elif choice == "2":

            if not installed:

                print(
                    "\n[!] FocusFinder is not currently installed."
                )

                print(
                    "[!] Choose Install / Reinstall instead."
                )

                return 1

            if CLEAN_INSTALL:

                print("\n" + "=" * 60)
                print("THIS UPDATE REQUIRES A CLEAN INSTALLATION")
                print("=" * 60)

                print(
                    "The existing application files and "
                    "virtual environment will be removed."
                )

                if WIPE_USER_DATA:

                    describe_user_data_wipe()

                    confirmation = (
                        "\nWARNING: Your saved FocusFinder data will "
                        "also be permanently deleted. "
                        "This cannot be undone."
                    )

                else:

                    print(
                        "\nYour recognised saved data will be "
                        "backed up and restored."
                    )

                    confirmation = ""

                if not confirm_action(
                    "This update will rebuild FocusFinder from scratch."
                    + confirmation
                ):

                    print("\n[*] Update cancelled. Nothing has been changed.")

                    return 0

                clean_update_application(install_dir)

            else:

                update_application(install_dir)

            print("\n" + "=" * 60)
            print(f"[+] {DISPLAY_NAME} successfully updated!")
            print(f"    Version: {VERSION}")

            if WIPE_USER_DATA:

                print(
                    "    Saved application data was wiped "
                    "as requested by this release."
                )

            else:

                print(
                    "    Recognised saved data has been preserved."
                )

            print("=" * 60)

        # --------------------------------------------------
        # Uninstall
        # --------------------------------------------------

        elif choice == "3":

            if not confirm_action(
                "This will permanently remove FocusFinder, including its "
                "virtual environment, saved data and shortcuts."
            ):

                print("\n[*] Uninstallation cancelled.")

                return 0

            uninstall_application(install_dir)

        # --------------------------------------------------
        # Exit
        # --------------------------------------------------

        elif choice == "4":

            print("\n[*] Exiting installer.")

            return 0

        else:

            print("\n[!] Invalid selection.")

            return 1

        return 0

    except Exception as error:

        print("\n" + "=" * 60)
        print("[!] OPERATION FAILED")
        print()
        print(error)
        print("=" * 60)

        return 1


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":

    exit_code = main()

    if sys.stdin.isatty():
        input("\nPress Enter to exit...")

    sys.exit(exit_code)
