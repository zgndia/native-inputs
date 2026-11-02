"""Demonstrate a non-blocking timed key hold."""

import time
from native_keyboard_inputs import InputController

# Replace "fake" with the current native backend when testing actual input.
with InputController("fake") as controller:
    task = controller.keyboard.hold("space", duration=2, blocking=False)
    print("The rest of the program continues while the key is held.")
    time.sleep(0.5)
    print("Cancelling the hold early.")
    task.cancel()
    task.wait()
    print(controller.backend.events)
