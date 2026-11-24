import re
import subprocess
import sys

_XRANDR_LINE = re.compile(
    r"^(?P<name>\S+) connected(?P<primary> primary)? "
    r"(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)",
    re.MULTILINE,
)


def parse_xrandr(output):
    """Return [{'name', 'primary', 'x', 'y', 'w', 'h'}] from `xrandr --query` text."""
    monitors = []
    for match in _XRANDR_LINE.finditer(output):
        monitors.append({
            "name": match.group("name"),
            "primary": bool(match.group("primary")),
            "x": int(match.group("x")),
            "y": int(match.group("y")),
            "w": int(match.group("w")),
            "h": int(match.group("h")),
        })
    return monitors


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
    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_xrandr(result.stdout)


def get_monitor_bounds(root, around=None):
    """Return (x, y, width, height) of the monitor to centre on, or None if it
    can't be determined (the caller should then let the window manager decide).

    `around` is a screen point (x, y); by default the mouse pointer is used.
    """
    if sys.platform.startswith("linux"):
        point = around
        if point is None:
            try:
                point = root.winfo_pointerxy()
            except Exception:
                point = (0, 0)

        monitor = pick_monitor(_linux_monitors(), point)
        if monitor is None:
            return None
        return monitor["x"], monitor["y"], monitor["w"], monitor["h"]

    # Windows reports the primary display, which is what we want there.
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def centre_geometry(bounds, width, height, scale=1.0, lift=20, margin=(40, 100)):
    """Pure helper: clamp the window to the monitor and return (w, h, x, y).

    `width`/`height` are in CustomTkinter units; `scale` converts them to pixels.
    """
    mx, my, mw, mh = bounds
    width = int(min(width, (mw - margin[0]) / scale))
    height = int(min(height, (mh - margin[1]) / scale))
    pixel_w = width * scale
    pixel_h = height * scale
    x = mx + max(0, int((mw - pixel_w) // 2))
    y = my + max(0, int((mh - pixel_h) // 2) - lift)
    return width, height, x, y