
#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path


# --------------------------------------------------
# Configuration
# --------------------------------------------------

APP_NAME = "FocusFinder"
PACKAGE_NAME = "FocusPY"

CURRENT_OS = platform.system()

SOURCE_DIR = Path(__file__).resolve().parent
SOURCE_MAIN = SOURCE_DIR / "main.py"
SOURCE_SRC = SOURCE_DIR / "src"

REQUIRED_PACKAGES = [
    "customtkinter",
    "playwright",
]

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

def get_install_dir():
    """Return the platform-specific installation directory."""

    if CURRENT_OS == "Windows":
        base_dir = Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local"
            )
        )

    elif CURRENT_OS == "Linux":
        base_dir = Path(
            os.environ.get(
                "XDG_DATA_HOME",
                Path.home() / ".local" / "share"
            )
        )

    else:
        return None

    return base_dir / APP_NAME


# --------------------------------------------------
# Validation
# --------------------------------------------------

def validate_source():
    """Check that the downloaded application folder is complete."""

    if not SOURCE_MAIN.is_file():
        raise FileNotFoundError(
            f"Could not find main.py beside installer.py:\n{SOURCE_MAIN}"
        )

    if not SOURCE_SRC.is_dir():
        raise FileNotFoundError(
            f"Could not find the src folder:\n{SOURCE_SRC}"
        )


# --------------------------------------------------
# Application files
# --------------------------------------------------

def copy_application(install_dir):
    """Copy the application into the installation directory."""

    print("[*] Copying application files...")

    install_package = install_dir / PACKAGE_NAME

    if SOURCE_DIR.resolve() == install_package.resolve():
        print("    + Application is already in the installation directory.")
    else:
        shutil.copytree(
            SOURCE_DIR,
            install_package,
            dirs_exist_ok=True,
            ignore=IGNORE_PATTERNS,
        )

        print(f"    + Application copied to: {install_package}")

    # Windows uses .pyw to launch without a console window.
    if CURRENT_OS == "Windows":
        shutil.copy2(
            install_package / "main.py",
            install_package / "main.pyw"
        )

        print("    + Created Windows GUI entry point.")

    return install_package


# --------------------------------------------------
# Virtual environment
# --------------------------------------------------

def setup_venv(install_dir):
    """Create the application's isolated Python environment."""

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
            [
                sys.executable,
                "-m",
                "venv",
                str(venv_dir)
            ],
            check=True
        )

    if not venv_python.exists():
        raise FileNotFoundError(
            f"Virtual environment Python was not created:\n{venv_python}"
        )

    # Ensure pip is available.
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "ensurepip",
            "--upgrade"
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return venv_python, venv_pythonw


# --------------------------------------------------
# Dependencies
# --------------------------------------------------

def install_dependencies(venv_python, install_package):
    """Install the application's Python dependencies."""

    print("[*] Installing Python dependencies...")

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip"
        ],
        check=True
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
                str(requirements_file)
            ],
            check=True
        )

    else:
        subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                *REQUIRED_PACKAGES
            ],
            check=True
        )

    # Install the Chromium browser required by Playwright.
    print("[*] Installing Playwright Chromium...")

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "playwright",
            "install",
            "chromium"
        ],
        check=True
    )


# --------------------------------------------------
# Windows integration
# --------------------------------------------------

def powershell_literal(value):
    """Safely quote a string for PowerShell."""

    return "'" + str(value).replace("'", "''") + "'"


def setup_windows(install_package, venv_pythonw):
    """Create a Windows Start Menu shortcut."""

    print("[*] Creating Windows shortcut...")

    pythonw = (
        venv_pythonw
        if venv_pythonw.exists()
        else venv_pythonw.with_name("python.exe")
    )

    target_script = install_package / "main.pyw"
    icon_path = install_package / "icon.ico"

    start_menu = (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )

    start_menu.mkdir(parents=True, exist_ok=True)

    shortcut_path = start_menu / f"{APP_NAME}.lnk"

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
            "-Command",
            powershell_script
        ],
        check=True
    )

    print(f"    + Created: {shortcut_path}")


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

    applications_dir = (
        Path.home()
        / ".local"
        / "share"
        / "applications"
    )

    applications_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = applications_dir / "focusfinder.desktop"

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
        f"Name={APP_NAME}",
        f"Exec={exec_command}",
        f"Path={install_package}",
        f"Icon={icon_path}" if icon_path.exists() else "",
        "StartupWMClass=focusfinder",
        "Terminal=false",
        "Categories=Education;Utility;",
    ]

    desktop_file.write_text(
        "\n".join(
            line for line in desktop_entry if line
        ) + "\n",
        encoding="utf-8"
    )

    desktop_file.chmod(0o755)

    update_database = shutil.which("update-desktop-database")

    if update_database:
        subprocess.run(
            [update_database, str(applications_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    print(f"    + Created: {desktop_file}")


# --------------------------------------------------
# Main installer
# --------------------------------------------------

def main():

    print()
    print("=" * 60)
    print(f"       {APP_NAME} Installer & Updater")
    print(f"       Operating system: {CURRENT_OS}")
    print("=" * 60)
    print()

    if CURRENT_OS not in ("Windows", "Linux"):
        print("[!] This operating system is not supported.")
        return 1

    try:

        # Validate downloaded files.
        validate_source()

        # Determine installation location.
        install_dir = get_install_dir()

        install_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        is_update = (
            (install_dir / PACKAGE_NAME).exists()
        )

        if is_update:
            print("[*] Existing installation detected.")
            print("[*] Updating application files...")

        else:
            print("[*] Starting fresh installation...")

        print(f"[*] Installation directory: {install_dir}")
        print()

        # Copy application files.
        install_package = copy_application(install_dir)

        # Create or reuse the virtual environment.
        venv_python, venv_pythonw = setup_venv(install_dir)

        # Install dependencies.
        install_dependencies(venv_python, install_package)

        # Create operating-system integration.
        if CURRENT_OS == "Windows":

            setup_windows(
                install_package,
                venv_pythonw
            )

        else:

            setup_linux(
                install_package,
                venv_python
            )

        print()
        print("=" * 60)

        if is_update:
            print(f"[+] {APP_NAME} successfully updated!")

        else:
            print(f"[+] {APP_NAME} successfully installed!")

        print()
        print(f"    Installed at: {install_dir}")
        print("    Launch it from your applications menu.")

        print("=" * 60)

        return 0

    except Exception as error:

        print()
        print("=" * 60)
        print("[!] INSTALLATION FAILED")
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
