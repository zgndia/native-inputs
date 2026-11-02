# Changelog

## 0.1.0 — 2026-11-02

- Initial cross-platform package structure.
- Windows `SendInput`, Linux `uinput`, and macOS Core Graphics backends.
- Portable key and mouse names with built-in/custom aliases.
- Blocking and non-blocking timed holds, hotkeys, context managers, and release cleanup.
- Fake backend and initial automated test suite.

## 0.2.0 — 2026-11-02

- Added asynchronous `keyboard.type(text, interval=0.05)` text entry.
- Added native Unicode text injection on Windows and macOS.
- Added dependency-free ASCII text entry on Linux using a documented US QWERTY mapping.
- Added simulated-backend tests for text entry and newline normalization.


## 0.3.0

- Added Windows keyboard injection mode selection: `scancode` (default), `virtual_key`, and legacy `keybd_event` for compatibility testing.
- Kept mouse injection on `SendInput`; documented that API-level dispatch does not prove target-application consumption.

## 0.4.0

- Add an optional Windows `windows_vhf` backend using a companion KMDF/VHF virtual HID source driver.
- Add keyboard and relative mouse HID report encoders and pure Python report tests.
- Keep the existing Win32 `SendInput` backend as the default Windows backend.
