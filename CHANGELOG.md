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
