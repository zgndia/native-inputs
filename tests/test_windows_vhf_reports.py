"""Pure HID report-encoding tests; no Windows driver or device is required."""
import unittest

from native_keyboard_inputs.backends.windows_vhf import (
    _IOCTL_SEND_KEYBOARD_REPORT,
    _IOCTL_SEND_MOUSE_REPORT,
    build_keyboard_report,
    build_mouse_report,
)
from native_keyboard_inputs.backends import create_backend
from native_keyboard_inputs.exceptions import BackendUnavailableError, UnsupportedInputError


class WindowsVHFReportTests(unittest.TestCase):
    def test_backend_is_windows_only(self):
        import os
        if os.name != "nt":
            with self.assertRaises(BackendUnavailableError):
                create_backend("windows_vhf")

    def test_ioctl_codes_match_shared_driver_header(self):
        self.assertEqual(_IOCTL_SEND_KEYBOARD_REPORT, 0x22A000)
        self.assertEqual(_IOCTL_SEND_MOUSE_REPORT, 0x22A004)

    def test_simple_keyboard_key_uses_hid_usage_slot(self):
        self.assertEqual(build_keyboard_report({"a"}), bytes([0, 0, 0x04, 0, 0, 0, 0, 0]))

    def test_modifier_uses_modifier_bitmap(self):
        self.assertEqual(
            build_keyboard_report({"left_ctrl", "left_shift", "c"}),
            bytes([0x03, 0, 0x06, 0, 0, 0, 0, 0]),
        )

    def test_f13_through_f24_are_supported_by_descriptor_range(self):
        self.assertEqual(build_keyboard_report({"f24"})[2], 0x73)

    def test_six_key_rollover_limit(self):
        self.assertEqual(len(build_keyboard_report(set("abcdef"))), 8)
        with self.assertRaises(UnsupportedInputError):
            build_keyboard_report(set("abcdefg"))

    def test_consumer_keys_are_rejected(self):
        with self.assertRaises(UnsupportedInputError):
            build_keyboard_report({"volume_up"})

    def test_mouse_buttons_and_signed_axis_bytes(self):
        self.assertEqual(
            build_mouse_report({"left", "x2"}, -5, 7, -1),
            bytes([0x11, 0xFB, 0x07, 0xFF]),
        )

    def test_mouse_report_range_is_checked(self):
        with self.assertRaises(ValueError):
            build_mouse_report(set(), 128, 0, 0)


if __name__ == "__main__":
    unittest.main()
