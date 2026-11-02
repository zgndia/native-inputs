"""Native keyboard inputs: cross-platform keyboard and mouse event injection."""

from __future__ import annotations
import atexit
import threading
from typing import Any

from .controller import InputController
from .exceptions import (
    BackendPermissionError,
    BackendUnavailableError,
    InputInjectionError,
    InvalidInputError,
    NativeInputError,
    UnsupportedInputError,
    UnsupportedPlatformError,
)
from .keys import KEY_CATEGORIES, KEY_NAMES, MOUSE_BUTTONS

__version__ = "0.1.0"

_default_lock = threading.RLock()
_default_controller: InputController | None = None


def get_default_controller() -> InputController:
    """Return the lazily-created process-wide controller."""
    global _default_controller
    with _default_lock:
        if _default_controller is None:
            _default_controller = InputController()
        return _default_controller


def configure(backend=None, **backend_options) -> InputController:
    """Replace the default controller/backend.

    Example: ``configure('fake')`` or ``configure('linux', screen_size=(1920, 1080))``.
    """
    global _default_controller
    with _default_lock:
        old = _default_controller
        if old is not None:
            old.close()
        _default_controller = InputController(backend, **backend_options)
        return _default_controller


def release_all() -> None:
    """Release all inputs held through the default controller, if initialized."""
    with _default_lock:
        if _default_controller is not None:
            _default_controller.release_all()


def close() -> None:
    """Release inputs and close the default controller's native resources."""
    global _default_controller
    with _default_lock:
        if _default_controller is not None:
            _default_controller.close()
            _default_controller = None


class _DefaultFacade:
    def __init__(self, attribute: str) -> None:
        self._attribute = attribute

    def __getattr__(self, name: str) -> Any:
        return getattr(getattr(get_default_controller(), self._attribute), name)


keyboard = _DefaultFacade("keyboard")
mouse = _DefaultFacade("mouse")

# Best-effort cleanup for the process-wide default controller at interpreter exit.
atexit.register(close)

__all__ = [
    "InputController", "keyboard", "mouse", "configure", "close", "release_all",
    "get_default_controller", "KEY_CATEGORIES", "KEY_NAMES", "MOUSE_BUTTONS",
    "NativeInputError", "InvalidInputError", "UnsupportedInputError",
    "UnsupportedPlatformError", "BackendUnavailableError", "BackendPermissionError",
    "InputInjectionError", "__version__",
]
