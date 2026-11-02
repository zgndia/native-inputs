"""Windows backend implemented with the Win32 SendInput API."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from .base import InputBackend
from ..exceptions import BackendUnavailableError, InputInjectionError, UnsupportedInputError


if __import__("os").name != "nt":  # Keep imports safe on non-Windows hosts.
    raise ImportError("The Windows backend can only be loaded on Windows.")

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
WHEEL_DELTA = 120

# Set-1 scan codes. Entries are (scan code, E0/extended flag).
_SCANS: dict[str, tuple[int, bool]] = {}
_SCANS.update({
    "a": (0x1E, False), "b": (0x30, False), "c": (0x2E, False),
    "d": (0x20, False), "e": (0x12, False), "f": (0x21, False),
    "g": (0x22, False), "h": (0x23, False), "i": (0x17, False),
    "j": (0x24, False), "k": (0x25, False), "l": (0x26, False),
    "m": (0x32, False), "n": (0x31, False), "o": (0x18, False),
    "p": (0x19, False), "q": (0x10, False), "r": (0x13, False),
    "s": (0x1F, False), "t": (0x14, False), "u": (0x16, False),
    "v": (0x2F, False), "w": (0x11, False), "x": (0x2D, False),
    "y": (0x15, False), "z": (0x2C, False),
    "1": (0x02, False), "2": (0x03, False), "3": (0x04, False),
    "4": (0x05, False), "5": (0x06, False), "6": (0x07, False),
    "7": (0x08, False), "8": (0x09, False), "9": (0x0A, False),
    "0": (0x0B, False),
    "minus": (0x0C, False), "equal": (0x0D, False),
    "backspace": (0x0E, False), "tab": (0x0F, False),
    "left_bracket": (0x1A, False), "right_bracket": (0x1B, False),
    "enter": (0x1C, False), "left_ctrl": (0x1D, False),
    "semicolon": (0x27, False), "apostrophe": (0x28, False),
    "grave": (0x29, False), "left_shift": (0x2A, False),
    "backslash": (0x2B, False), "comma": (0x33, False),
    "period": (0x34, False), "slash": (0x35, False),
    "right_shift": (0x36, False), "numpad_multiply": (0x37, False),
    "left_alt": (0x38, False), "space": (0x39, False),
    "caps_lock": (0x3A, False),
    "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False),
    "f4": (0x3E, False), "f5": (0x3F, False), "f6": (0x40, False),
    "f7": (0x41, False), "f8": (0x42, False), "f9": (0x43, False),
    "f10": (0x44, False), "num_lock": (0x45, False),
    "scroll_lock": (0x46, False),
    "numpad_7": (0x47, False), "numpad_8": (0x48, False),
    "numpad_9": (0x49, False), "numpad_subtract": (0x4A, False),
    "numpad_4": (0x4B, False), "numpad_5": (0x4C, False),
    "numpad_6": (0x4D, False), "numpad_add": (0x4E, False),
    "numpad_1": (0x4F, False), "numpad_2": (0x50, False),
    "numpad_3": (0x51, False), "numpad_0": (0x52, False),
    "numpad_decimal": (0x53, False), "escape": (0x01, False),
    "f11": (0x57, False), "f12": (0x58, False),
    "right_ctrl": (0x1D, True), "right_alt": (0x38, True),
    "numpad_enter": (0x1C, True), "numpad_divide": (0x35, True),
    "home": (0x47, True), "up": (0x48, True), "page_up": (0x49, True),
    "left": (0x4B, True), "right": (0x4D, True), "end": (0x4F, True),
    "down": (0x50, True), "page_down": (0x51, True),
    "insert": (0x52, True), "delete": (0x53, True),
    "left_super": (0x5B, True), "right_super": (0x5C, True),
    "menu": (0x5D, True), "print_screen": (0x37, True),
})

_VK_ONLY = {
    "pause": 0x13,
    "numpad_equal": 0x92,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "media_next": 0xB0, "media_previous": 0xB1, "media_stop": 0xB2,
    "media_play_pause": 0xB3,
    "browser_back": 0xA6, "browser_forward": 0xA7, "browser_home": 0xAC,
}
for _number in range(13, 25):
    _VK_ONLY[f"f{_number}"] = 0x7C + (_number - 13)


class WindowsBackend(InputBackend):
    name = "windows"

    def __init__(self) -> None:
        try:
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._send_input = self._user32.SendInput
            self._send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
            self._send_input.restype = wintypes.UINT
            self._get_system_metrics = self._user32.GetSystemMetrics
            self._get_system_metrics.argtypes = (ctypes.c_int,)
            self._get_system_metrics.restype = ctypes.c_int
        except Exception as exc:
            raise BackendUnavailableError(f"Could not initialize Win32 SendInput: {exc}") from exc
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()

    def _send(self, event: INPUT) -> None:
        sent = self._send_input(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        if sent != 1:
            error = ctypes.get_last_error()
            raise InputInjectionError(
                f"SendInput inserted {sent}/1 events (GetLastError={error}). "
                "The target may reject injected input or run at a higher integrity level."
            )

    @staticmethod
    def _keyboard_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
        event = INPUT()
        event.type = INPUT_KEYBOARD
        event.union.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        return event

    @staticmethod
    def _mouse_input(dx: int = 0, dy: int = 0, data: int = 0, flags: int = 0) -> INPUT:
        event = INPUT()
        event.type = INPUT_MOUSE
        event.union.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
        return event

    def key_down(self, key: str) -> None:
        if key in _SCANS:
            scan, extended = _SCANS[key]
            flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0)
            self._send(self._keyboard_input(scan=scan, flags=flags))
        elif key in _VK_ONLY:
            self._send(self._keyboard_input(vk=_VK_ONLY[key]))
        else:
            raise UnsupportedInputError(f"Key {key!r} has no Windows mapping.")
        self._held_keys.add(key)

    def key_up(self, key: str) -> None:
        if key in _SCANS:
            scan, extended = _SCANS[key]
            flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if extended else 0)
            self._send(self._keyboard_input(scan=scan, flags=flags))
        elif key in _VK_ONLY:
            self._send(self._keyboard_input(vk=_VK_ONLY[key], flags=KEYEVENTF_KEYUP))
        else:
            raise UnsupportedInputError(f"Key {key!r} has no Windows mapping.")
        self._held_keys.discard(key)

    def mouse_down(self, button: str) -> None:
        flags_data = {
            "left": (MOUSEEVENTF_LEFTDOWN, 0),
            "right": (MOUSEEVENTF_RIGHTDOWN, 0),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, 0),
            "x1": (MOUSEEVENTF_XDOWN, 1),
            "x2": (MOUSEEVENTF_XDOWN, 2),
        }
        if button not in flags_data:
            raise UnsupportedInputError(f"Mouse button {button!r} is unsupported on Windows.")
        flags, data = flags_data[button]
        self._send(self._mouse_input(data=data, flags=flags))
        self._held_buttons.add(button)

    def mouse_up(self, button: str) -> None:
        flags_data = {
            "left": (MOUSEEVENTF_LEFTUP, 0),
            "right": (MOUSEEVENTF_RIGHTUP, 0),
            "middle": (MOUSEEVENTF_MIDDLEUP, 0),
            "x1": (MOUSEEVENTF_XUP, 1),
            "x2": (MOUSEEVENTF_XUP, 2),
        }
        if button not in flags_data:
            raise UnsupportedInputError(f"Mouse button {button!r} is unsupported on Windows.")
        flags, data = flags_data[button]
        self._send(self._mouse_input(data=data, flags=flags))
        self._held_buttons.discard(button)

    def move_relative(self, dx: int, dy: int) -> None:
        self._send(self._mouse_input(dx=int(dx), dy=int(dy), flags=MOUSEEVENTF_MOVE))

    def move_to(self, x: int, y: int, screen_size=None) -> None:
        # Use virtual-desktop coordinates so multi-monitor layouts are handled.
        left = self._get_system_metrics(76)  # SM_XVIRTUALSCREEN
        top = self._get_system_metrics(77)   # SM_YVIRTUALSCREEN
        width = self._get_system_metrics(78) # SM_CXVIRTUALSCREEN
        height = self._get_system_metrics(79) # SM_CYVIRTUALSCREEN
        if width <= 1 or height <= 1:
            raise InputInjectionError("Windows returned invalid virtual desktop dimensions.")
        nx = round((int(x) - left) * 65535 / (width - 1))
        ny = round((int(y) - top) * 65535 / (height - 1))
        nx = max(0, min(65535, nx))
        ny = max(0, min(65535, ny))
        self._send(self._mouse_input(nx, ny, flags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK))

    def scroll(self, horizontal: int, vertical: int) -> None:
        if vertical:
            self._send(self._mouse_input(data=int(vertical) * WHEEL_DELTA, flags=MOUSEEVENTF_WHEEL))
        if horizontal:
            self._send(self._mouse_input(data=int(horizontal) * WHEEL_DELTA, flags=MOUSEEVENTF_HWHEEL))

    def release_all(self) -> None:
        errors = []
        for key in tuple(self._held_keys):
            try:
                self.key_up(key)
            except Exception as exc:
                errors.append(exc)
        for button in tuple(self._held_buttons):
            try:
                self.mouse_up(button)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise InputInjectionError(f"Could not release {len(errors)} held input(s): {errors[0]}")
