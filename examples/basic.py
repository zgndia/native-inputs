"""Basic real-input example. Run only when you intend to send input."""

from native_keyboard_inputs import keyboard, mouse, close

try:
    keyboard.tap("space")
    keyboard.hotkey("ctrl", "c")
    mouse.click("left")
finally:
    # Best-effort cleanup if an example is interrupted.
    close()
