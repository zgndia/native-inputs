"""Pure mapping tests for the Windows backend; no Windows APIs are invoked."""
from __future__ import annotations

import importlib
import os
import unittest


# The module guard prevents accidental backend use off Windows. Temporarily
# satisfy that guard for these pure mapping/structure tests; no Win32 DLL is
# loaded because the backend is constructed with __new__ below.
_original_os_name = os.name
try:
    if os.name != "nt":
        os.name = "nt"
    windows_backend = importlib.import_module("native_keyboard_inputs.backends.windows")
finally:
    os.name = _original_os_name


class WindowsModeMappingTests(unittest.TestCase):
    def _backend(self, mode: str):
        backend = object.__new__(windows_backend.WindowsBackend)
        backend.keyboard_mode = mode
        backend._held_keys = set()
        backend._held_buttons = set()
        # Map Set-1 T/V scan codes to their matching virtual-key values.
        mapping = {
            (0x14, windows_backend.MAPVK_VSC_TO_VK_EX): 0x54,
            (0x2F, windows_backend.MAPVK_VSC_TO_VK_EX): 0x56,
        }
        backend._map_virtual_key = lambda code, kind: mapping.get((code, kind), 0)
        return backend

    def test_t_and_v_codes_are_correct(self):
        backend = self._backend("virtual_key")
        self.assertEqual(backend._key_codes("t"), (0x54, 0x14, False))
        self.assertEqual(backend._key_codes("v"), (0x56, 0x2F, False))

    def test_virtual_key_mode_sends_vk_events(self):
        backend = self._backend("virtual_key")
        sent = []
        backend._send = sent.append
        backend.key_down("t")
        backend.key_up("t")
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0].union.ki.wVk, 0x54)
        self.assertEqual(sent[0].union.ki.dwFlags, 0)
        self.assertEqual(sent[1].union.ki.wVk, 0x54)
        self.assertEqual(sent[1].union.ki.dwFlags, windows_backend.KEYEVENTF_KEYUP)

    def test_legacy_mode_sends_vk_and_scan_code(self):
        backend = self._backend("keybd_event")
        sent = []
        backend._keybd_event = lambda *args: sent.append(args)
        backend.key_down("v")
        backend.key_up("v")
        self.assertEqual(sent[0], (0x56, 0x2F, 0, 0))
        self.assertEqual(sent[1], (0x56, 0x2F, windows_backend.KEYEVENTF_KEYUP, 0))


if __name__ == "__main__":
    unittest.main()
