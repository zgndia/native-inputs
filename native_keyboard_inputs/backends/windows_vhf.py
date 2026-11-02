"""Windows software-backed HID input via the NativeInputsVhf KMDF/VHF driver.

This backend sends standard HID input report payloads to a companion kernel
mode driver. It is a virtual HID device, not a physical USB device.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .base import InputBackend
from ..exceptions import (
    BackendUnavailableError,
    InputInjectionError,
    UnsupportedInputError,
)

_DEVICE_PATH = r"\\.\NativeInputsVhf"
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# CTL_CODE(FILE_DEVICE_UNKNOWN, function, METHOD_BUFFERED, FILE_WRITE_ACCESS)
_IOCTL_SEND_KEYBOARD_REPORT = 0x22A000
_IOCTL_SEND_MOUSE_REPORT = 0x22A004

# USB HID Keyboard/Keypad usage IDs. These are key positions/usages, not
# character codes; the active Windows keyboard layout determines characters.
_KEY_USAGES: dict[str, int] = {}
_KEY_USAGES.update({chr(ord("a") + i): 0x04 + i for i in range(26)})
_KEY_USAGES.update({str(i + 1): 0x1E + i for i in range(9)})
_KEY_USAGES["0"] = 0x27
_KEY_USAGES.update({
    "enter": 0x28, "escape": 0x29, "backspace": 0x2A, "tab": 0x2B,
    "space": 0x2C, "minus": 0x2D, "equal": 0x2E,
    "left_bracket": 0x2F, "right_bracket": 0x30, "backslash": 0x31,
    "semicolon": 0x33, "apostrophe": 0x34, "grave": 0x35,
    "comma": 0x36, "period": 0x37, "slash": 0x38,
    "caps_lock": 0x39,
    "print_screen": 0x46, "scroll_lock": 0x47, "pause": 0x48,
    "insert": 0x49, "home": 0x4A, "page_up": 0x4B,
    "delete": 0x4C, "end": 0x4D, "page_down": 0x4E,
    "right": 0x4F, "left": 0x50, "down": 0x51, "up": 0x52,
    "num_lock": 0x53, "numpad_divide": 0x54,
    "numpad_multiply": 0x55, "numpad_subtract": 0x56,
    "numpad_add": 0x57, "numpad_enter": 0x58,
    "numpad_1": 0x59, "numpad_2": 0x5A, "numpad_3": 0x5B,
    "numpad_4": 0x5C, "numpad_5": 0x5D, "numpad_6": 0x5E,
    "numpad_7": 0x5F, "numpad_8": 0x60, "numpad_9": 0x61,
    "numpad_0": 0x62, "numpad_decimal": 0x63,
    "menu": 0x65, "numpad_equal": 0x67,
    "left_ctrl": 0xE0, "left_shift": 0xE1, "left_alt": 0xE2,
    "left_super": 0xE3, "right_ctrl": 0xE4, "right_shift": 0xE5,
    "right_alt": 0xE6, "right_super": 0xE7,
})
_KEY_USAGES.update({f"f{i}": 0x39 + i for i in range(1, 13)})
_KEY_USAGES.update({f"f{i}": 0x68 + (i - 13) for i in range(13, 25)})

_MODIFIER_BITS = {
    0xE0: 0, 0xE1: 1, 0xE2: 2, 0xE3: 3,
    0xE4: 4, 0xE5: 5, 0xE6: 6, 0xE7: 7,
}
_MOUSE_BUTTON_BITS = {"left": 0, "right": 1, "middle": 2, "x1": 3, "x2": 4}


def build_keyboard_report(held_keys: set[str] | frozenset[str]) -> bytes:
    """Return the 8-byte boot-keyboard payload (report ID is sent separately)."""
    modifiers = 0
    ordinary: list[int] = []
    for key in held_keys:
        try:
            usage = _KEY_USAGES[key]
        except KeyError as exc:
            raise UnsupportedInputError(
                f"Key {key!r} is not represented by this HID keyboard descriptor."
            ) from exc
        if usage in _MODIFIER_BITS:
            modifiers |= 1 << _MODIFIER_BITS[usage]
        else:
            ordinary.append(usage)
    if len(ordinary) > 6:
        raise UnsupportedInputError(
            "The virtual keyboard uses 6-key rollover; at most six non-modifier keys "
            "can be held simultaneously."
        )
    ordinary.sort()
    ordinary.extend([0] * (6 - len(ordinary)))
    return bytes([modifiers, 0, *ordinary])


def build_mouse_report(
    held_buttons: set[str] | frozenset[str], dx: int = 0, dy: int = 0, wheel: int = 0
) -> bytes:
    """Return the 4-byte relative mouse payload (report ID is sent separately)."""
    buttons = 0
    for button in held_buttons:
        try:
            buttons |= 1 << _MOUSE_BUTTON_BITS[button]
        except KeyError as exc:
            raise UnsupportedInputError(f"Mouse button {button!r} is unsupported.") from exc
    for value, name in ((dx, "dx"), (dy, "dy"), (wheel, "wheel")):
        if not -127 <= int(value) <= 127:
            raise ValueError(f"{name} must be between -127 and 127 in one HID report.")
    return bytes([buttons, int(dx) & 0xFF, int(dy) & 0xFF, int(wheel) & 0xFF])


class WindowsVHFBackend(InputBackend):
    """Send keyboard/mouse HID reports through the companion VHF driver."""

    name = "windows_vhf"

    def __init__(self) -> None:
        if os.name != "nt":
            raise BackendUnavailableError("The windows_vhf backend is available only on Windows.")

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._create_file = self._kernel32.CreateFileW
        self._create_file.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        self._create_file.restype = wintypes.HANDLE
        self._device_io_control = self._kernel32.DeviceIoControl
        self._device_io_control.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        )
        self._device_io_control.restype = wintypes.BOOL
        self._close_handle = self._kernel32.CloseHandle
        self._close_handle.argtypes = (wintypes.HANDLE,)
        self._close_handle.restype = wintypes.BOOL

        handle = self._create_file(
            _DEVICE_PATH,
            _GENERIC_WRITE,
            0,  # The WDF control device is exclusive.
            None,
            _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error in (2, 3, 1167):
                detail = (
                    "The NativeInputsVhf driver device was not found. Install and start "
                    "the companion driver first; see drivers/windows-vhf/README.md."
                )
            elif error == 5:
                detail = "Access was denied. Run the Python process as Administrator."
            else:
                detail = f"CreateFileW failed with Win32 error {error}."
            raise BackendUnavailableError(detail)

        self._handle = handle
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()
        self._closed = False

    def _send_report(self, ioctl: int, payload: bytes) -> None:
        if self._closed:
            raise BackendUnavailableError("The Windows VHF backend is closed.")
        buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        returned = wintypes.DWORD()
        ok = self._device_io_control(
            self._handle, ioctl, ctypes.cast(buffer, wintypes.LPVOID), len(payload),
            None, 0, ctypes.byref(returned), None,
        )
        if not ok:
            error = ctypes.get_last_error()
            raise InputInjectionError(
                f"The VHF driver rejected an input report (Win32 error {error})."
            )

    def _send_keyboard(self) -> None:
        self._send_report(_IOCTL_SEND_KEYBOARD_REPORT, build_keyboard_report(self._held_keys))

    def _send_mouse(self, dx: int = 0, dy: int = 0, wheel: int = 0) -> None:
        self._send_report(
            _IOCTL_SEND_MOUSE_REPORT,
            build_mouse_report(self._held_buttons, dx, dy, wheel),
        )

    def key_down(self, key: str) -> None:
        if key in self._held_keys:
            return
        # Validate before mutating state, including the six-key rollover limit.
        proposed = set(self._held_keys)
        proposed.add(key)
        build_keyboard_report(proposed)
        self._held_keys.add(key)
        try:
            self._send_keyboard()
        except Exception:
            self._held_keys.discard(key)
            raise

    def key_up(self, key: str) -> None:
        if key not in self._held_keys:
            return
        self._held_keys.remove(key)
        try:
            self._send_keyboard()
        except Exception:
            self._held_keys.add(key)
            raise

    def type_text(self, text: str) -> None:
        raise UnsupportedInputError(
            "windows_vhf sends HID key usages, not Unicode text. Use keyboard.tap() "
            "for key presses or the standard Windows backend for keyboard.type()."
        )

    def mouse_down(self, button: str) -> None:
        if button in self._held_buttons:
            return
        self._held_buttons.add(button)
        try:
            self._send_mouse()
        except Exception:
            self._held_buttons.discard(button)
            raise

    def mouse_up(self, button: str) -> None:
        if button not in self._held_buttons:
            return
        self._held_buttons.remove(button)
        try:
            self._send_mouse()
        except Exception:
            self._held_buttons.add(button)
            raise

    def move_relative(self, dx: int, dy: int) -> None:
        remaining_x, remaining_y = int(dx), int(dy)
        while remaining_x or remaining_y:
            step_x = max(-127, min(127, remaining_x))
            step_y = max(-127, min(127, remaining_y))
            self._send_mouse(dx=step_x, dy=step_y)
            remaining_x -= step_x
            remaining_y -= step_y

    def move_to(self, x: int, y: int, screen_size=None) -> None:
        raise UnsupportedInputError(
            "The VHF mouse descriptor uses relative movement. move_to() absolute "
            "coordinates are not supported; use move_relative() instead."
        )

    def scroll(self, horizontal: int, vertical: int) -> None:
        if horizontal:
            raise UnsupportedInputError(
                "Horizontal wheel scrolling is not included in this VHF mouse descriptor."
            )
        remaining = int(vertical)
        while remaining:
            step = max(-127, min(127, remaining))
            self._send_mouse(wheel=step)
            remaining -= step

    def release_all(self) -> None:
        errors: list[Exception] = []
        if self._held_keys:
            previous = set(self._held_keys)
            self._held_keys.clear()
            try:
                self._send_keyboard()
            except Exception as exc:
                self._held_keys = previous
                errors.append(exc)
        if self._held_buttons:
            previous_buttons = set(self._held_buttons)
            self._held_buttons.clear()
            try:
                self._send_mouse()
            except Exception as exc:
                self._held_buttons = previous_buttons
                errors.append(exc)
        if errors:
            raise InputInjectionError(f"Could not release VHF input state: {errors[0]}")

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.release_all()
        finally:
            self._close_handle(self._handle)
            self._closed = True
