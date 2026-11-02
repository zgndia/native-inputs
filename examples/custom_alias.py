"""Register project-specific names for keys and mouse buttons."""

from native_keyboard_inputs import InputController

with InputController("fake") as controller:
    controller.keyboard.register_alias("jump", "space")
    controller.mouse.register_alias("fire", "left")

    controller.keyboard.tap("jump")
    controller.mouse.click("fire")
    print(controller.backend.events)
