# Native keyboard inputs

**Native keyboard inputs** is a dependency-free Python package for injecting keyboard and mouse events on Windows, Linux, and macOS.

- Distribution name: `native-keyboard-inputs`
- Import name: `native_keyboard_inputs`
- Python: 3.10+
- Required third-party dependencies: none
- License: MIT

> **Compatibility note:** native input injection is inherently OS- and application-dependent. This package provides a shared API, not a guarantee that every application, game, remote desktop, secure desktop, or anti-cheat protected process will accept synthetic events. Unsupported key mappings raise `UnsupportedInputError` instead of silently sending a different key.

## Features

- Keyboard key-down and key-up events.
- Mouse button down/up for left, right, middle, X1, and X2 where supported.
- Relative pointer movement; absolute pointer movement where supported.
- Vertical and horizontal wheel events.
- Built-in aliases and custom aliases.
- Timed blocking and non-blocking holds.
- Chords/hotkeys and context-managed holds.
- Overlapping timed holds are reference-counted so one task cannot release an input still held by another task.
- A simulated backend for tests and dry runs.
- Native backends implemented with Python's standard library and OS APIs.

Text entry (Unicode strings) is deliberately not included in this first release. Typing text is not equivalent to pressing physical keys: it depends on keyboard layout, dead keys, IMEs, compose sequences, and OS-specific text services. The API focuses on portable physical input events.

## Installation

Install from a local checkout:

```bash
python -m pip install .
```

Or install an editable development copy:

```bash
python -m pip install -e .
```

There are no runtime dependencies. Building/installing the package may require a recent `setuptools` on systems that do not already have it.

## Quick start

```python
from native_keyboard_inputs import keyboard, mouse

# Press and release a key.
keyboard.press("a")
keyboard.release("a")

# A short key tap (50 ms by default).
keyboard.tap("space")

# Aliases are case-insensitive and accept spaces/hyphens.
keyboard.tap("ESC")
keyboard.tap("numpad-2")

# Hold a key for two seconds.
keyboard.hold("shift", duration=2)

# Send a chord; keys are released in reverse order.
keyboard.hotkey("ctrl", "c")

# Mouse buttons and movement.
mouse.click("left")
mouse.press("rmb")
mouse.release("right")
mouse.move_relative(20, -10)
mouse.scroll(vertical=3, horizontal=-1)

# Always release all inputs during shutdown/error handling.
keyboard.release_all()
mouse.release_all()
```

## Choosing a backend

The default backend is selected automatically using the current operating system. Backend initialization is lazy: importing the package does not create a virtual device or inject events.

```python
from native_keyboard_inputs import InputController, configure

# Replace the process-wide default backend.
configure("windows")

# Configure Linux absolute pointer coordinates.
configure("linux", screen_size=(1920, 1080))

# Use a simulated backend for testing (no real input is sent).
controller = InputController("fake")
controller.keyboard.tap("space")
print(controller.backend.events)
controller.close()
```

For isolated code and tests, prefer creating your own `InputController` rather than reconfiguring the process-wide default.

## API

### Keyboard

Text entry is available as an asynchronous operation:

```python
import asyncio
from native_keyboard_inputs import keyboard

async def main():
    await keyboard.type("Hello ;)", interval=0.05)

asyncio.run(main())
```

`keyboard.type()` injects text, whereas `keyboard.tap()` presses a physical key.
Text-entry support depends on the operating system: Windows uses Unicode
`SendInput` events, macOS uses Core Graphics Unicode keyboard events, and the
minimal-dependency Linux `uinput` backend currently maps ASCII using US QWERTY
physical key positions. Non-ASCII text is explicitly rejected on Linux rather
than silently producing incorrect characters. Linux text entry may not match
a non-US active keyboard layout. Synthetic text events may also be ignored by
some games or applications.

```python
keyboard.press(key)
keyboard.release(key)
keyboard.tap(key, duration=0.05, blocking=True)
keyboard.hold(key, duration=1.0, blocking=True)
keyboard.press_many("ctrl", "shift")
keyboard.release_many("ctrl", "shift")
keyboard.hotkey("ctrl", "c", interval=0.03)
keyboard.held("shift")       # context manager
keyboard.register_alias("jump", "space")
keyboard.unregister_alias("jump")
keyboard.release_all()
```

A non-blocking timed hold returns an `InputTask`:

```python
task = keyboard.hold("space", duration=5, blocking=False)
# Do other work...
task.cancel()  # releases the input immediately
# Or: task.wait(); task.done; task.error
```

### Mouse

```python
mouse.press("left")
mouse.release("left")
mouse.click("right", duration=0.05, blocking=True)
mouse.double_click("left")
mouse.held("left")             # context manager
mouse.move_relative(10, -5)
mouse.move_to(400, 300)
mouse.scroll(vertical=2, horizontal=-1)
mouse.register_alias("fire", "left")
mouse.release_all()
```

On Linux, absolute pointer movement requires a `screen_size=(width, height)` either when configuring the backend or on each `move_to` call. Coordinates are scaled to the uinput device's absolute range. Relative pointer movement does not need screen dimensions. On multi-monitor Linux desktops, the supplied size should describe the coordinate space expected by the compositor; per-monitor negative-origin layouts may require platform-specific handling.

On Windows, absolute coordinates are in the virtual desktop coordinate space, including multi-monitor offsets. On macOS, coordinates use Core Graphics desktop points.

### Aliases and canonical names

Names are case-insensitive. Spaces and hyphens are normalized to underscores. Some built-in examples:

| Alias | Canonical name |
|---|---|
| `esc` | `escape` |
| `return` | `enter` |
| `spacebar` | `space` |
| `ctrl` | `left_ctrl` |
| `shift` | `left_shift` |
| `alt` / `option` | `left_alt` |
| `cmd` / `win` / `super` | `left_super` |
| `pgup` | `page_up` |
| `pgdn` | `page_down` |
| `np2` / `num2` | `numpad_2` |
| `lmb` | mouse `left` |
| `rmb` | mouse `right` |
| `mmb` | mouse `middle` |

Punctuation can also be addressed by its symbol, for example `keyboard.tap("-")` or `keyboard.tap("[")`.

The complete canonical keyboard-name list is available as `KEY_NAMES`; categories are exposed as `KEY_CATEGORIES`. Mouse buttons are available as `MOUSE_BUTTONS`.

The canonical key names describe physical key positions on a conventional PC keyboard where the OS provides a mapping. They do not guarantee identical characters across international keyboard layouts. For example, key injection and Unicode text entry are separate problems.

### Concurrency and state

- A direct `press()` is idempotent until a matching `release()`.
- `hold()` and `tap()` use independent leases. Overlapping holds of the same key/button will only send key-up after the final lease ends and no direct press remains.
- `release_all()` cancels outstanding scheduled holds and attempts to release keys and buttons tracked by that controller.
- Use `with InputController(...) as controller:` or call `close()` to release inputs and close backend resources.
- Avoid using multiple independent controllers to inject the same physical key concurrently. Their state tracking is intentionally controller-local.
- If the process is forcibly terminated or the OS/backend crashes, Python cannot guarantee cleanup. Keep holds short and use `try/finally` or context managers.

## Platform details and limitations

### Windows

Backend: Win32 APIs through `ctypes` and `user32.dll`.

The default keyboard injection uses `SendInput` with Set-1 scan codes for physical keys where available; some extended/media keys use virtual-key codes. For compatibility testing, the Windows backend also accepts `keyboard_mode="virtual_key"` (SendInput using virtual-key codes) or `keyboard_mode="keybd_event"` (the legacy Windows keyboard API). For example:

```python
from native_keyboard_inputs import configure, keyboard

# Default: physical scan codes with SendInput.
configure("windows", keyboard_mode="scancode")
keyboard.tap("t")

# Compatibility test: virtual-key SendInput.
configure("windows", keyboard_mode="virtual_key")
keyboard.tap("t")

# Compatibility test: legacy keybd_event.
configure("windows", keyboard_mode="keybd_event")
keyboard.tap("t")
```

`keybd_event` is deprecated by Microsoft in favor of `SendInput`, has no return value, and is offered only as a legacy compatibility experiment. None of these modes guarantees that a game will consume synthetic events. Do not use these modes to evade anti-cheat or other application security controls. Mouse events always use `SendInput`.
- Mouse input supports buttons, relative motion, virtual-desktop absolute motion, and both wheel axes.
- Windows applies User Interface Privilege Isolation (UIPI). A process generally cannot inject into a target running at a higher integrity level. `SendInput` may fail without clearly identifying UIPI as the cause.
- Secure desktop, protected processes, anti-cheat software, and some games may reject synthetic events.

#### Optional Windows VHF backend

The project also includes an optional `windows_vhf` backend. It uses a companion KMDF driver and Microsoft's Virtual HID Framework to expose a **virtual** HID keyboard and mouse to the Windows HID stack. This is not a physical USB device and does not guarantee acceptance by any particular application. The existing `windows`/`SendInput` backend remains the default.

Build, signing, installation, supported controls, limitations, and usage are documented in [`drivers/windows-vhf/README.md`](drivers/windows-vhf/README.md). Once the driver is built, correctly signed, installed, and started, select it explicitly:

```python
from native_keyboard_inputs import InputController

with InputController("windows_vhf") as inputs:
    inputs.keyboard.hotkey("ctrl", "shift", "esc")
    inputs.keyboard.tap("a")
    inputs.mouse.move_relative(50, 0)
    inputs.mouse.click("left")
```

The initial VHF descriptor supports key down/up, modifiers, six-key rollover, relative mouse movement, five mouse buttons, and vertical scrolling. It does not support Unicode text entry, absolute mouse movement, horizontal wheel scrolling, or media/browser consumer keys. Run the Python process as Administrator because the driver control interface is restricted to Administrators and SYSTEM.

### Linux

Backend: `/dev/uinput`, using the Linux kernel uinput interface directly.

- No X11-only dependency is used; uinput creates a virtual input device consumed by the system input stack.
- The user needs permission to open/configure `/dev/uinput`. Prefer a narrowly scoped udev rule/group permission over running an entire application as root.
- Whether a compositor or application accepts the events still depends on its input/security policy.
- Relative mouse movement and wheel events are supported. Absolute movement requires a known `screen_size` and is scaled to the virtual device range.
- A kernel with the modern `UI_DEV_SETUP` and `UI_ABS_SETUP` uinput ioctls is required by this initial backend implementation.

### macOS

Backend: Core Graphics Quartz events through the Application Services framework.

- Keyboard events use macOS virtual key codes.
- Mouse buttons, pointer movement, and two-axis scrolling are supported by Core Graphics.
- macOS privacy controls may require the calling application/terminal to be granted the relevant Accessibility or Input Monitoring permission, depending on macOS version and how the process is launched.
- Some keys have no public virtual-key mapping on macOS; they raise `UnsupportedInputError`. In this initial key map, this includes browser navigation keys, F21–F24, Insert, Menu, Num Lock, Pause, Print Screen, Scroll Lock, and the media/volume keys.
- System security restrictions and protected applications may reject or ignore injected events.

## Testing

Tests use the fake backend and do not send real input:

```bash
python -m unittest discover -s tests -v
```

A quick manual smoke test on each operating system is still necessary to verify OS permissions and target-application behavior.

## Safety

This package injects input events; it does not record, monitor, or intercept the user's physical keyboard or mouse. Use it only on systems and applications where you are authorized to automate input. Do not use it to bypass application security controls, anti-cheat systems, or access restrictions.

## Native API references

- Microsoft: [SendInput](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput)
- Linux kernel: [uinput userspace API](https://docs.kernel.org/input/uinput.html)
- Apple: [CGEventCreateKeyboardEvent](https://developer.apple.com/documentation/coregraphics/cgevent/init%28keyboardeventsource%3Avirtualkey%3Akeydown%3A)
- Apple: [Core Graphics CGEvent](https://developer.apple.com/documentation/coregraphics/cgevent)
