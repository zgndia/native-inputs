"""macOS backend using Core Graphics Quartz event injection."""

from __future__ import annotations

import ctypes
from typing import Optional

from .base import InputBackend
from ..exceptions import BackendUnavailableError, InputInjectionError, UnsupportedInputError


if __import__("sys").platform != "darwin":
    raise ImportError("The macOS backend can only be loaded on macOS.")


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


# Virtual key codes from the macOS hardware/Carbon keyboard table.
_KEY_CODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B,
    "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11,
    "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17,
    "equal": 0x18, "9": 0x19, "7": 0x1A, "minus": 0x1B, "8": 0x1C, "0": 0x1D,
    "right_bracket": 0x1E, "o": 0x1F, "u": 0x20, "left_bracket": 0x21,
    "i": 0x22, "p": 0x23, "enter": 0x24, "l": 0x25, "j": 0x26,
    "apostrophe": 0x27, "k": 0x28, "semicolon": 0x29, "backslash": 0x2A,
    "comma": 0x2B, "slash": 0x2C, "n": 0x2D, "m": 0x2E, "period": 0x2F,
    "tab": 0x30, "space": 0x31, "grave": 0x32, "backspace": 0x33,
    "escape": 0x35, "left_super": 0x37, "left_shift": 0x38,
    "caps_lock": 0x39, "left_alt": 0x3A, "left_ctrl": 0x3B,
    "right_shift": 0x3C, "right_alt": 0x3D, "right_ctrl": 0x3E,
    "numpad_decimal": 0x41, "numpad_multiply": 0x43, "numpad_add": 0x45,
    "numpad_divide": 0x4B, "numpad_enter": 0x4C, "numpad_subtract": 0x4E,
    "numpad_equal": 0x51, "numpad_0": 0x52, "numpad_1": 0x53,
    "numpad_2": 0x54, "numpad_3": 0x55, "numpad_4": 0x56,
    "numpad_5": 0x57, "numpad_6": 0x58, "numpad_7": 0x59,
    "numpad_8": 0x5B, "numpad_9": 0x5C,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f3": 0x63,
    "f8": 0x64, "f9": 0x65, "f11": 0x67, "f13": 0x69,
    "f16": 0x6A, "f14": 0x6B, "f10": 0x6D, "f12": 0x6F,
    "f15": 0x71, "help": 0x72, "home": 0x73, "page_up": 0x74,
    "delete": 0x75, "f4": 0x76, "end": 0x77, "f2": 0x78,
    "page_down": 0x79, "f1": 0x7A, "left": 0x7B, "right": 0x7C,
    "down": 0x7D, "up": 0x7E, "right_super": 0x36,
    "f17": 0x40, "f18": 0x4F, "f19": 0x50, "f20": 0x5A,
}

# Quartz event types and mouse button identifiers.
_HID_EVENT_TAP = 0
_EVENT_LEFT_DOWN = 1
_EVENT_LEFT_UP = 2
_EVENT_RIGHT_DOWN = 3
_EVENT_RIGHT_UP = 4
_EVENT_MOUSE_MOVED = 5
_EVENT_OTHER_DOWN = 25
_EVENT_OTHER_UP = 26
_BUTTON_IDS = {"left": 0, "right": 1, "middle": 2, "x1": 3, "x2": 4}


class MacOSBackend(InputBackend):
    name = "macos"

    def __init__(self) -> None:
        try:
            self._cg = ctypes.CDLL(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            self._cf = ctypes.CDLL(
                "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
            )
            self._cg.CGEventCreateKeyboardEvent.argtypes = (ctypes.c_void_p, ctypes.c_ushort, ctypes.c_bool)
            self._cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
            self._cg.CGEventCreateMouseEvent.argtypes = (ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32)
            self._cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
            self._cg.CGEventCreateScrollWheelEvent.argtypes = (
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_int32, ctypes.c_int32,
            )
            self._cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
            self._cg.CGEventCreate.argtypes = (ctypes.c_void_p,)
            self._cg.CGEventCreate.restype = ctypes.c_void_p
            self._cg.CGEventGetLocation.argtypes = (ctypes.c_void_p,)
            self._cg.CGEventGetLocation.restype = CGPoint
            self._cg.CGEventPost.argtypes = (ctypes.c_uint32, ctypes.c_void_p)
            self._cg.CGEventPost.restype = None
            self._cf.CFRelease.argtypes = (ctypes.c_void_p,)
            self._cf.CFRelease.restype = None
        except Exception as exc:
            raise BackendUnavailableError(f"Could not initialize macOS Core Graphics: {exc}") from exc
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()

    def _post(self, event: int) -> None:
        if not event:
            raise InputInjectionError("Core Graphics could not create the requested event.")
        try:
            self._cg.CGEventPost(_HID_EVENT_TAP, event)
        finally:
            self._cf.CFRelease(event)

    def key_down(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise UnsupportedInputError(f"Key {key!r} has no macOS virtual-key mapping.")
        event = self._cg.CGEventCreateKeyboardEvent(None, _KEY_CODES[key], True)
        self._post(event)
        self._held_keys.add(key)

    def key_up(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise UnsupportedInputError(f"Key {key!r} has no macOS virtual-key mapping.")
        event = self._cg.CGEventCreateKeyboardEvent(None, _KEY_CODES[key], False)
        self._post(event)
        self._held_keys.discard(key)

    def _current_location(self) -> CGPoint:
        event = self._cg.CGEventCreate(None)
        if not event:
            raise InputInjectionError("Could not query the current mouse location.")
        try:
            return self._cg.CGEventGetLocation(event)
        finally:
            self._cf.CFRelease(event)

    def mouse_down(self, button: str) -> None:
        if button not in _BUTTON_IDS:
            raise UnsupportedInputError(f"Mouse button {button!r} is unsupported on macOS.")
        button_id = _BUTTON_IDS[button]
        event_type = _EVENT_LEFT_DOWN if button == "left" else (
            _EVENT_RIGHT_DOWN if button == "right" else _EVENT_OTHER_DOWN
        )
        self._post(self._cg.CGEventCreateMouseEvent(None, event_type, self._current_location(), button_id))
        self._held_buttons.add(button)

    def mouse_up(self, button: str) -> None:
        if button not in _BUTTON_IDS:
            raise UnsupportedInputError(f"Mouse button {button!r} is unsupported on macOS.")
        button_id = _BUTTON_IDS[button]
        event_type = _EVENT_LEFT_UP if button == "left" else (
            _EVENT_RIGHT_UP if button == "right" else _EVENT_OTHER_UP
        )
        self._post(self._cg.CGEventCreateMouseEvent(None, event_type, self._current_location(), button_id))
        self._held_buttons.discard(button)

    def move_relative(self, dx: int, dy: int) -> None:
        point = self._current_location()
        self.move_to(round(point.x + int(dx)), round(point.y + int(dy)))

    def move_to(self, x: int, y: int, screen_size: Optional[tuple[int, int]] = None) -> None:
        point = CGPoint(float(x), float(y))
        self._post(self._cg.CGEventCreateMouseEvent(None, _EVENT_MOUSE_MOVED, point, 0))

    def scroll(self, horizontal: int, vertical: int) -> None:
        if not horizontal and not vertical:
            return
        # Quartz expects vertical first, horizontal second. Values are line units.
        event = self._cg.CGEventCreateScrollWheelEvent(None, 1, 2, int(vertical), int(horizontal))
        self._post(event)

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
