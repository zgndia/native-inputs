"""Example for the optional Windows VHF backend (requires installed driver/admin)."""
from native_keyboard_inputs import InputController


with InputController("windows_vhf") as inputs:
    inputs.keyboard.hotkey("ctrl", "shift", "esc")
    inputs.keyboard.tap("a")
    inputs.mouse.move_relative(40, 0)
    inputs.mouse.click("left")
    inputs.mouse.scroll(vertical=1)
