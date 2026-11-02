"""Demonstrate asynchronous text entry."""

import asyncio
from native_keyboard_inputs import keyboard as kb


async def main() -> None:
    # Open Notepad on Windows, then type a string with a 50 ms character delay.
    # On Linux, text entry currently assumes a US QWERTY physical layout.
    await kb.type("Hello ;)", interval=0.05)


if __name__ == "__main__":
    asyncio.run(main())
