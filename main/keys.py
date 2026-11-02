"""Portable key and mouse-button names, categories, and aliases.

Names describe physical key positions on a conventional PC keyboard where
possible. Layout-dependent text entry is intentionally separate from key
injection; ``keyboard.press('y')`` means the key named ``y`` in this registry,
not a promise to type the Unicode character y on every keyboard layout.
"""

from __future__ import annotations

import re
from typing import Iterable


def _normalize(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Input names must be strings.")
    value = value.strip().lower()
    value = re.sub(r"[\s-]+", "_", value)
    return value


LETTERS = tuple("abcdefghijklmnopqrstuvwxyz")
NUMBER_ROW = tuple("1234567890")
FUNCTION_KEYS = tuple(f"f{i}" for i in range(1, 25))

PUNCTUATION = (
    "minus", "equal", "left_bracket", "right_bracket", "backslash",
    "semicolon", "apostrophe", "grave", "comma", "period", "slash",
)

CONTROL_KEYS = (
    "escape", "enter", "tab", "backspace", "space", "caps_lock",
    "left_shift", "right_shift", "left_ctrl", "right_ctrl",
    "left_alt", "right_alt", "left_super", "right_super", "menu",
)

NAVIGATION_KEYS = (
    "insert", "delete", "home", "end", "page_up", "page_down",
    "left", "right", "up", "down",
)

NUMPAD_KEYS = (
    *(f"numpad_{i}" for i in range(10)),
    "numpad_decimal", "numpad_divide", "numpad_multiply",
    "numpad_subtract", "numpad_add", "numpad_enter", "numpad_equal",
)

SYSTEM_KEYS = ("print_screen", "scroll_lock", "pause", "num_lock")

# Consumer/system keys are included in the portable registry when common OS
# keycode sets expose them. A particular backend may still reject a key.
MEDIA_KEYS = (
    "volume_mute", "volume_down", "volume_up", "media_play_pause",
    "media_stop", "media_previous", "media_next",
    "browser_back", "browser_forward", "browser_home",
)

KEY_CATEGORIES = {
    "letters": LETTERS,
    "number_row": NUMBER_ROW,
    "function": FUNCTION_KEYS,
    "punctuation": PUNCTUATION,
    "control": CONTROL_KEYS,
    "navigation": NAVIGATION_KEYS,
    "numpad": NUMPAD_KEYS,
    "system": SYSTEM_KEYS,
    "media": MEDIA_KEYS,
}

KEY_NAMES = tuple(dict.fromkeys(
    key for group in KEY_CATEGORIES.values() for key in group
))

KEY_ALIASES = {
    "esc": "escape",
    "return": "enter",
    "spacebar": "space",
    "bksp": "backspace",
    "ctrl": "left_ctrl",
    "control": "left_ctrl",
    "lctrl": "left_ctrl",
    "rctrl": "right_ctrl",
    "left_control": "left_ctrl",
    "right_control": "right_ctrl",
    "shift": "left_shift",
    "lshift": "left_shift",
    "rshift": "right_shift",
    "alt": "left_alt",
    "option": "left_alt",
    "lalt": "left_alt",
    "ralt": "right_alt",
    "win": "left_super",
    "windows": "left_super",
    "command": "left_super",
    "cmd": "left_super",
    "super": "left_super",
    "meta": "left_super",
    "lwin": "left_super",
    "rwin": "right_super",
    "left_windows": "left_super",
    "right_windows": "right_super",
    "left_command": "left_super",
    "right_command": "right_super",
    "left_meta": "left_super",
    "right_meta": "right_super",
    "arrow_left": "left",
    "arrow_right": "right",
    "arrow_up": "up",
    "arrow_down": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "arrowup": "up",
    "arrowdown": "down",
    "pgup": "page_up",
    "prior": "page_up",
    "pgdn": "page_down",
    "next": "page_down",
    "ins": "insert",
    "del": "delete",
    "prtsc": "print_screen",
    "printscreen": "print_screen",
    "numlock": "num_lock",
    "capslock": "caps_lock",
    "scrolllock": "scroll_lock",
    "np_enter": "numpad_enter",
    "np_decimal": "numpad_decimal",
    "np_divide": "numpad_divide",
    "np_multiply": "numpad_multiply",
    "np_subtract": "numpad_subtract",
    "np_add": "numpad_add",
    "np_equal": "numpad_equal",
}
for _i in range(10):
    KEY_ALIASES[f"np{_i}"] = f"numpad_{_i}"
    KEY_ALIASES[f"num{_i}"] = f"numpad_{_i}"
    KEY_ALIASES[f"numpad{_i}"] = f"numpad_{_i}"
    KEY_ALIASES[f"keypad_{_i}"] = f"numpad_{_i}"

# Convenient symbol aliases for punctuation keys.
KEY_ALIASES.update({
    "-": "minus", "=": "equal", "[": "left_bracket", "]": "right_bracket",
    "\\": "backslash", ";": "semicolon", "'": "apostrophe", "`": "grave",
    ",": "comma", ".": "period", "/": "slash",
})

MOUSE_BUTTONS = ("left", "right", "middle", "x1", "x2")
MOUSE_ALIASES = {
    "lmb": "left", "left_mouse": "left", "mouse_left": "left",
    "rmb": "right", "right_mouse": "right", "mouse_right": "right",
    "mmb": "middle", "middle_mouse": "middle", "mouse_middle": "middle",
    "mouse1": "left", "mouse2": "right", "mouse3": "middle",
    "button1": "left", "button2": "right", "button3": "middle",
    "mouse_x1": "x1", "side1": "x1", "mouse_x2": "x2", "side2": "x2",
}


class NameRegistry:
    """Resolve canonical names and support caller-defined aliases."""

    def __init__(self, canonical_names: Iterable[str], aliases: dict[str, str]) -> None:
        self._canonical = frozenset(canonical_names)
        self._aliases = {_normalize(k): _normalize(v) for k, v in aliases.items()}

    def resolve(self, name: str) -> str:
        normalized = _normalize(name)
        target = self._aliases.get(normalized, normalized)
        if target not in self._canonical:
            raise ValueError(f"Unknown input {name!r}. Use a canonical name or register an alias.")
        return target

    def register_alias(self, alias: str, target: str) -> None:
        alias_name = _normalize(alias)
        target_name = self.resolve(target)
        if alias_name in self._canonical and alias_name != target_name:
            raise ValueError(f"{alias!r} is already a canonical input name.")
        if not alias_name:
            raise ValueError("Alias cannot be empty.")
        self._aliases[alias_name] = target_name

    def unregister_alias(self, alias: str) -> None:
        alias_name = _normalize(alias)
        if alias_name not in self._aliases:
            raise KeyError(f"No alias named {alias!r}.")
        del self._aliases[alias_name]

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)
