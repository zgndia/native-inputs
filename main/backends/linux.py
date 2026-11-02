"""Linux backend using the kernel's /dev/uinput virtual-device interface.

No third-party package is required. Creating a uinput device normally needs
access to /dev/uinput (often via a udev rule or an appropriate group).
"""

from __future__ import annotations

import ctypes
import fcntl
import os
import struct
import time
from typing import Optional

from .base import InputBackend
from ..exceptions import BackendPermissionError, BackendUnavailableError, InputInjectionError, UnsupportedInputError


if __import__("sys").platform != "linux":
    raise ImportError("The Linux backend can only be loaded on Linux.")

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
SYN_REPORT = 0
REL_X = 0x00
REL_Y = 0x01
REL_HWHEEL = 0x06
REL_WHEEL = 0x08
ABS_X = 0x00
ABS_Y = 0x01
BUS_USB = 0x03
INPUT_PROP_POINTER = 0x00

# Linux input-event-codes.h values (evdev key codes).
_KEY_CODES = {
    "escape": 1,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "minus": 12, "equal": 13, "backspace": 14, "tab": 15,
    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23, "o": 24, "p": 25,
    "left_bracket": 26, "right_bracket": 27, "enter": 28, "left_ctrl": 29,
    "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35, "j": 36, "k": 37, "l": 38,
    "semicolon": 39, "apostrophe": 40, "grave": 41, "left_shift": 42, "backslash": 43,
    "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
    "comma": 51, "period": 52, "slash": 53, "right_shift": 54, "numpad_multiply": 55,
    "left_alt": 56, "space": 57, "caps_lock": 58,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "num_lock": 69, "scroll_lock": 70,
    "numpad_7": 71, "numpad_8": 72, "numpad_9": 73, "numpad_subtract": 74,
    "numpad_4": 75, "numpad_5": 76, "numpad_6": 77, "numpad_add": 78,
    "numpad_1": 79, "numpad_2": 80, "numpad_3": 81, "numpad_0": 82, "numpad_decimal": 83,
    "f11": 87, "f12": 88,
    "numpad_enter": 96, "right_ctrl": 97, "numpad_divide": 98, "print_screen": 99,
    "right_alt": 100, "home": 102, "up": 103, "page_up": 104, "left": 105,
    "right": 106, "end": 107, "down": 108, "page_down": 109, "insert": 110, "delete": 111,
    "volume_mute": 113, "volume_down": 114, "volume_up": 115, "pause": 119,
    "left_super": 125, "right_super": 126, "menu": 127,
    "numpad_equal": 117,
    "media_play_pause": 164, "media_stop": 166, "media_previous": 165, "media_next": 163,
    "browser_home": 172, "browser_back": 158, "browser_forward": 159,
}
for _number in range(13, 25):
    _KEY_CODES[f"f{_number}"] = 183 + (_number - 13)

_BUTTON_CODES = {"left": 0x110, "right": 0x111, "middle": 0x112, "x1": 0x113, "x2": 0x114}


def _ioc(direction: int, type_: int, number: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (type_ << 8) | number


def _iow(number: int, size: int = ctypes.sizeof(ctypes.c_int)) -> int:
    return _ioc(1, ord("U"), number, size)


def _io(number: int) -> int:
    return _ioc(0, ord("U"), number, 0)


class _InputID(ctypes.Structure):
    _fields_ = [("bustype", ctypes.c_ushort), ("vendor", ctypes.c_ushort),
                ("product", ctypes.c_ushort), ("version", ctypes.c_ushort)]


class _UInputSetup(ctypes.Structure):
    _fields_ = [("id", _InputID), ("name", ctypes.c_char * 80), ("ff_effects_max", ctypes.c_uint32)]


class _InputAbsInfo(ctypes.Structure):
    _fields_ = [("value", ctypes.c_int32), ("minimum", ctypes.c_int32),
                ("maximum", ctypes.c_int32), ("fuzz", ctypes.c_int32),
                ("flat", ctypes.c_int32), ("resolution", ctypes.c_int32)]


class _UInputAbsSetup(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("absinfo", _InputAbsInfo)]


_EVENT = struct.Struct("@llHHi")


class LinuxBackend(InputBackend):
    name = "linux"

    def __init__(self, device_path: Optional[str] = None,
                 screen_size: Optional[tuple[int, int]] = None,
                 device_name: str = "Native keyboard inputs") -> None:
        self.screen_size = screen_size
        self._fd: Optional[int] = None
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()
        paths = [device_path] if device_path else ["/dev/uinput", "/dev/input/uinput"]
        last_error = None
        for path in paths:
            if not path:
                continue
            try:
                self._fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
                self._device_path = path
                break
            except OSError as exc:
                last_error = exc
        if self._fd is None:
            if isinstance(last_error, PermissionError):
                raise BackendPermissionError(
                    "Permission denied opening /dev/uinput. Configure a udev rule or grant "
                    "the current user access to the uinput device; avoid running the whole "
                    "application as root unless necessary."
                ) from last_error
            raise BackendUnavailableError(
                "Could not open /dev/uinput. Ensure the uinput kernel module is available "
                "and that the device node exists."
            ) from last_error
        try:
            self._create_device(device_name)
        except Exception:
            self.close()
            raise

    def _ioctl_int(self, number: int, value: int) -> None:
        assert self._fd is not None
        fcntl.ioctl(self._fd, _iow(number), struct.pack("i", int(value)))

    def _ioctl_struct(self, command: int, value: ctypes.Structure) -> None:
        assert self._fd is not None
        raw = bytearray(ctypes.string_at(ctypes.addressof(value), ctypes.sizeof(value)))
        fcntl.ioctl(self._fd, command, raw, True)

    def _create_device(self, device_name: str) -> None:
        assert self._fd is not None
        try:
            self._ioctl_int(100, EV_KEY)  # UI_SET_EVBIT
            self._ioctl_int(100, EV_REL)
            self._ioctl_int(100, EV_ABS)
            for code in set(_KEY_CODES.values()) | set(_BUTTON_CODES.values()):
                self._ioctl_int(101, code)  # UI_SET_KEYBIT
            for code in (REL_X, REL_Y, REL_HWHEEL, REL_WHEEL):
                self._ioctl_int(102, code)  # UI_SET_RELBIT
            for code in (ABS_X, ABS_Y):
                self._ioctl_int(103, code)  # UI_SET_ABSBIT
            self._ioctl_int(110, INPUT_PROP_POINTER)  # UI_SET_PROPBIT

            setup = _UInputSetup()
            setup.id = _InputID(BUS_USB, 0x1209, 0x0001, 1)
            encoded_name = device_name.encode("utf-8")[:79]
            setup.name = encoded_name
            self._ioctl_struct(_iow(3, ctypes.sizeof(_UInputSetup)), setup)  # UI_DEV_SETUP

            for code in (ABS_X, ABS_Y):
                axis = _UInputAbsSetup()
                axis.code = code
                axis.absinfo = _InputAbsInfo(0, 0, 65535, 0, 0, 0)
                self._ioctl_struct(_iow(4, ctypes.sizeof(_UInputAbsSetup)), axis)  # UI_ABS_SETUP

            fcntl.ioctl(self._fd, _io(1))  # UI_DEV_CREATE
        except PermissionError as exc:
            raise BackendPermissionError(
                "Permission denied configuring /dev/uinput. Check device permissions and udev rules."
            ) from exc
        except OSError as exc:
            raise BackendUnavailableError(f"Could not create Linux uinput device: {exc}") from exc

    def _emit(self, events: list[tuple[int, int, int]]) -> None:
        if self._fd is None:
            raise BackendUnavailableError("The Linux uinput device is closed.")
        now_ns = time.time_ns()
        sec, nsec = divmod(now_ns, 1_000_000_000)
        usec = nsec // 1000
        chunks = [_EVENT.pack(sec, usec, type_, code, value) for type_, code, value in events]
        chunks.append(_EVENT.pack(sec, usec, EV_SYN, SYN_REPORT, 0))
        try:
            payload = b"".join(chunks)
            written = os.write(self._fd, payload)
            if written != len(payload):
                raise OSError(f"short write to uinput device ({written}/{len(payload)} bytes)")
        except OSError as exc:
            raise InputInjectionError(f"Writing to the Linux uinput device failed: {exc}") from exc

    def key_down(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise UnsupportedInputError(f"Key {key!r} has no Linux evdev mapping.")
        self._emit([(EV_KEY, _KEY_CODES[key], 1)])
        self._held_keys.add(key)

    def key_up(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise UnsupportedInputError(f"Key {key!r} has no Linux evdev mapping.")
        self._emit([(EV_KEY, _KEY_CODES[key], 0)])
        self._held_keys.discard(key)

    def mouse_down(self, button: str) -> None:
        if button not in _BUTTON_CODES:
            raise UnsupportedInputError(f"Mouse button {button!r} has no Linux evdev mapping.")
        self._emit([(EV_KEY, _BUTTON_CODES[button], 1)])
        self._held_buttons.add(button)

    def mouse_up(self, button: str) -> None:
        if button not in _BUTTON_CODES:
            raise UnsupportedInputError(f"Mouse button {button!r} has no Linux evdev mapping.")
        self._emit([(EV_KEY, _BUTTON_CODES[button], 0)])
        self._held_buttons.discard(button)

    def move_relative(self, dx: int, dy: int) -> None:
        events = []
        if dx:
            events.append((EV_REL, REL_X, int(dx)))
        if dy:
            events.append((EV_REL, REL_Y, int(dy)))
        if events:
            self._emit(events)

    def move_to(self, x: int, y: int, screen_size: Optional[tuple[int, int]] = None) -> None:
        size = screen_size or self.screen_size
        if size is None:
            raise ValueError(
                "Linux absolute pointer movement requires screen_size=(width, height), "
                "because uinput absolute axes must be scaled to a display."
            )
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("screen_size dimensions must be positive.")
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"Coordinates must be inside the supplied screen_size {size}.")
        ax = 0 if width == 1 else round(int(x) * 65535 / (width - 1))
        ay = 0 if height == 1 else round(int(y) * 65535 / (height - 1))
        self._emit([(EV_ABS, ABS_X, ax), (EV_ABS, ABS_Y, ay)])

    def scroll(self, horizontal: int, vertical: int) -> None:
        events = []
        if horizontal:
            events.append((EV_REL, REL_HWHEEL, int(horizontal)))
        if vertical:
            events.append((EV_REL, REL_WHEEL, int(vertical)))
        if events:
            self._emit(events)

    def release_all(self) -> None:
        events = [(EV_KEY, _KEY_CODES[key], 0) for key in self._held_keys if key in _KEY_CODES]
        events += [(EV_KEY, _BUTTON_CODES[button], 0) for button in self._held_buttons if button in _BUTTON_CODES]
        if events and self._fd is not None:
            self._emit(events)
        self._held_keys.clear()
        self._held_buttons.clear()

    def close(self) -> None:
        if self._fd is None:
            return
        try:
            self.release_all()
        finally:
            try:
                fcntl.ioctl(self._fd, _io(2))  # UI_DEV_DESTROY
            except OSError:
                pass
            os.close(self._fd)
            self._fd = None
