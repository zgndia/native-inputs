"""In-memory backend for tests, dry runs, and API examples."""

from __future__ import annotations
from typing import Optional
from .base import InputBackend


class FakeBackend(InputBackend):
    name = "fake"

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.held_keys: set[str] = set()
        self.held_buttons: set[str] = set()
        self.closed = False

    def key_down(self, key: str) -> None:
        self.events.append(("key_down", key))
        self.held_keys.add(key)

    def key_up(self, key: str) -> None:
        self.events.append(("key_up", key))
        self.held_keys.discard(key)

    def type_text(self, text: str) -> None:
        self.events.append(("type_text", text))

    def mouse_down(self, button: str) -> None:
        self.events.append(("mouse_down", button))
        self.held_buttons.add(button)

    def mouse_up(self, button: str) -> None:
        self.events.append(("mouse_up", button))
        self.held_buttons.discard(button)

    def move_relative(self, dx: int, dy: int) -> None:
        self.events.append(("move_relative", int(dx), int(dy)))

    def move_to(self, x: int, y: int, screen_size: Optional[tuple[int, int]] = None) -> None:
        self.events.append(("move_to", int(x), int(y), screen_size))

    def scroll(self, horizontal: int, vertical: int) -> None:
        self.events.append(("scroll", int(horizontal), int(vertical)))

    def release_all(self) -> None:
        for key in sorted(self.held_keys):
            self.key_up(key)
        for button in sorted(self.held_buttons):
            self.mouse_up(button)
        self.events.append(("release_all",))

    def close(self) -> None:
        if not self.closed:
            self.release_all()
            self.closed = True
