"""Backend interface shared by native and simulated implementations."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class InputBackend(ABC):
    name = "abstract"

    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def mouse_down(self, button: str) -> None: ...

    @abstractmethod
    def mouse_up(self, button: str) -> None: ...

    @abstractmethod
    def move_relative(self, dx: int, dy: int) -> None: ...

    @abstractmethod
    def move_to(self, x: int, y: int, screen_size: Optional[tuple[int, int]] = None) -> None: ...

    @abstractmethod
    def scroll(self, horizontal: int, vertical: int) -> None: ...

    @abstractmethod
    def release_all(self) -> None: ...

    def close(self) -> None:
        """Release native resources. Backends without resources may do nothing."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
