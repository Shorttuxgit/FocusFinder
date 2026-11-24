# --------------------------------------------------
# Finding the right monitor and centring windows on it
# --------------------------------------------------

import re
import subprocess
import sys

# One monitor line from `xrandr --query`, e.g. "HDMI-1 connected primary 1920x1080+0+0"
_XRANDR_LINE = re.compile(
    r"^(?P<name>\S+) connected(?P<primary> primary)? "
    r"(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)",
    re.MULTILINE,
)


# --------------------------------------------------
# Linux
# --------------------------------------------------

def parse_xrandr(output):
    """Return [{'name', 'primary', 'x', 'y', 'w', 'h'}] from `xrandr --query` text."""
    return [
        {
            "name": match.group("name"),
            "primary": bool(match.group("primary")),
            "x": int(match.group("x")),
            "y": int(match.group("y")),
            "w": int(match.group("w")),
            "h": int(match.group("h")),
        }
        for match in _XRANDR_LINE.finditer(output)
    ]


def pick_monitor(monitors, point):
    """Monitor containing the point, else the primary one, else the first."""
    if not monitors:
        return None

    px, py = point
    for monitor in monitors:
        if (monitor["x"] <= px < monitor["x"] + monitor["w"]
                and monitor["y"] <= py < monitor["y"] + monitor["h"]):
            return monitor

    for monitor in monitors:
        if monitor["primary"]:
            return monitor

    return monitors[0]


def _linux_monitors():
    # Ask xrandr for the monitor layout (empty list if it isn't available)
    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_xrandr(result.stdout)


# --------------------------------------------------
# Windows
# --------------------------------------------------

def _windows_work_area(point):
    """Work area (monitor minus taskbar) of the monitor containing the point."""
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.WinDLL("user32")
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    MONITOR_DEFAULTTONEAREST = 2
    monitor = user32.MonitorFromPoint(wintypes.POINT(int(point[0]), int(point[1])), MONITOR_DEFAULTTONEAREST)

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None

    work = info.rcWork
    return work.left, work.top, work.right - work.left, work.bottom - work.top


# --------------------------------------------------
# Public helpers
# --------------------------------------------------

def get_monitor_bounds(root, around=None):
    """Return (x, y, width, height) of the monitor to centre on, or None if it
    can't be determined (the caller should then let the window manager decide).

    `around` is a screen point (x, y); by default the mouse pointer is used.
    """
    point = around
    if point is None:
        try:
            point = root.winfo_pointerxy()
        except Exception:
            point = (0, 0)

    if sys.platform.startswith("linux"):
        monitor = pick_monitor(_linux_monitors(), point)
        if monitor is None:
            return None
        return monitor["x"], monitor["y"], monitor["w"], monitor["h"]

    if sys.platform == "win32":
        try:
            area = _windows_work_area(point)
        except Exception:
            area = None
        if area:
            return area

    # Anything else (or a failed lookup): the whole primary screen
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def centre_geometry(bounds, width, height, scale=1.0, lift=20, margin=(40, 100)):
    """Pure helper: clamp the window to the monitor and return (w, h, x, y).

    `width`/`height` are in CustomTkinter units; `scale` converts them to pixels.
    """
    mx, my, mw, mh = bounds

    # Never larger than the monitor (minus a margin for borders and taskbars)
    width = int(min(width, (mw - margin[0]) / scale))
    height = int(min(height, (mh - margin[1]) / scale))

    # Centre it, nudged up slightly so it looks balanced
    x = mx + max(0, int((mw - width * scale) // 2))
    y = my + max(0, int((mh - height * scale) // 2) - lift)
    return width, height, x, y