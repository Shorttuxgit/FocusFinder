"""

HOW TO ADD A SETTING
--------------------
1. Add a Setting(...) line to SETTINGS below. That is all that is needed for it
   to get a default value, be saved to config.json, and appear in Options.
2. If changing it should do something right away, add a method to
   TimetableWidget named  apply_setting_<key>(self, value).
   Read the current value anywhere with  self.cfg["<key>"].

HOW TO ADD AN OPTIONS BUTTON
----------------------------
1. Add an Action(...) line to ACTIONS below.
2. Add the method named in `handler` to TimetableWidget.

HOW TO ADD A SECTION WITH CUSTOM CONTENT
----------------------------------------
Add a method  options_extra_<section>(self, parent)  to TimetableWidget (section
name lower-cased, spaces as underscores). It receives the panel card to draw
into and returns True if it drew anything. Settings and actions for the same
section are drawn first, then the extra.

FEATURE SWITCHES
----------------
Setting(..., hidden=True) values live in config.json but never appear in
Options. Use them to turn a whole feature on or off, and put the same key in
`requires=` on an Action to hide the action when the feature is off.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    default: object
    kind: str = "toggle"          # "toggle" or "choice"
    section: str = "General"
    choices: tuple = ()           # for kind="choice"
    hidden: bool = False          # config-only value, not shown in Options
    requires: str = ""            # only show when this config key is truthy


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    section: str
    handler: str                  # name of a TimetableWidget method
    requires: str = ""            # only show when this config key is truthy


SETTINGS = (
    Setting("time_format", "12-hour time", False, section="Display", requires="sett_enabled"),

    # Feature switches (edit config.json to change these)
    Setting("friends_system", "Friends system", True, hidden=True),
    Setting("sett_enabled", "Settings panel", True, hidden=True),
)

ACTIONS = (
    Action("export", "Export my timetable", "Friends", "export_my_timetable_file", requires="friends_system"),
    Action("import", "Import friend timetable", "Friends", "open_add_friend_dialog", requires="friends_system"),
)

# Order sections appear in Options; any other section is added after these
SECTION_ORDER = ("Display", "Friends")

DEFAULTS = {setting.key: setting.default for setting in SETTINGS}