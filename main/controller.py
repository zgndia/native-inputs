"""Platform-independent keyboard and mouse API."""

from __future__ import annotations

import math
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from .backends import InputBackend, create_backend
from .exceptions import InvalidInputError
from .keys import KEY_ALIASES, KEY_NAMES, MOUSE_ALIASES, MOUSE_BUTTONS, NameRegistry
from .scheduler import InputTask


class InputController:
    """Own one backend and coordinate key/button state across API calls.

    A controller is thread-safe. Repeated direct ``press`` calls are idempotent.
    Timed holds use independent leases, so one overlapping hold cannot release
    a key/button still owned by another hold.
    """

    def __init__(self, backend: str | InputBackend | None = None, **backend_options) -> None:
        self.backend = create_backend(backend, **backend_options) if not isinstance(backend, InputBackend) else backend
        self.key_registry = NameRegistry(KEY_NAMES, KEY_ALIASES)
        self.mouse_registry = NameRegistry(MOUSE_BUTTONS, MOUSE_ALIASES)
        self._lock = threading.RLock()
        self._direct_held: set[tuple[str, str]] = set()
        self._lease_counts: dict[tuple[str, str], int] = {}
        self._leases: dict[int, tuple[str, str]] = {}
        self._next_lease = 1
        self._tasks: dict[InputTask, tuple[str, str]] = {}
        self.keyboard = Keyboard(self)
        self.mouse = Mouse(self)
        self._closed = False

    @property
    def backend_name(self) -> str:
        return getattr(self.backend, "name", self.backend.__class__.__name__)

    def _resolve(self, kind: str, name: str) -> str:
        registry = self.key_registry if kind == "key" else self.mouse_registry
        try:
            return registry.resolve(name)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(str(exc)) from exc

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("This InputController is closed. Create a new controller to send input.")

    def _backend_down(self, control: tuple[str, str]) -> None:
        kind, name = control
        if kind == "key":
            self.backend.key_down(name)
        else:
            self.backend.mouse_down(name)

    def _backend_up(self, control: tuple[str, str]) -> None:
        kind, name = control
        if kind == "key":
            self.backend.key_up(name)
        else:
            self.backend.mouse_up(name)

    def _is_active(self, control: tuple[str, str]) -> bool:
        return control in self._direct_held or self._lease_counts.get(control, 0) > 0

    def _press_direct(self, control: tuple[str, str]) -> None:
        with self._lock:
            self._ensure_open()
            if control in self._direct_held:
                return
            if not self._is_active(control):
                self._backend_down(control)
            self._direct_held.add(control)

    def _release_direct(self, control: tuple[str, str]) -> None:
        with self._lock:
            if control not in self._direct_held:
                return
            if self._lease_counts.get(control, 0) == 0:
                self._backend_up(control)
            self._direct_held.discard(control)

    def _acquire_lease(self, control: tuple[str, str]) -> int:
        with self._lock:
            self._ensure_open()
            if not self._is_active(control):
                self._backend_down(control)
            token = self._next_lease
            self._next_lease += 1
            self._leases[token] = control
            self._lease_counts[control] = self._lease_counts.get(control, 0) + 1
            return token

    def _release_lease(self, token: int) -> None:
        with self._lock:
            control = self._leases.get(token)
            if control is None:
                return
            remaining = self._lease_counts.get(control, 0) - 1
            if remaining <= 0:
                if control not in self._direct_held:
                    self._backend_up(control)
                self._lease_counts.pop(control, None)
            else:
                self._lease_counts[control] = remaining
            self._leases.pop(token, None)

    @staticmethod
    def _validate_duration(duration: float) -> float:
        try:
            value = float(duration)
        except (TypeError, ValueError) as exc:
            raise ValueError("duration must be a finite non-negative number.") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError("duration must be a finite non-negative number.")
        return value

    def _hold(self, control: tuple[str, str], duration: float, blocking: bool = True):
        delay = self._validate_duration(duration)
        token = self._acquire_lease(control)
        if blocking:
            try:
                if delay:
                    time.sleep(delay)
            finally:
                self._release_lease(token)
            return None

        task = None
        def finish_hold() -> None:
            try:
                self._release_lease(token)
            finally:
                with self._lock:
                    if task is not None:
                        self._tasks.pop(task, None)
        task = InputTask(delay, finish_hold, autostart=False)
        with self._lock:
            self._tasks[task] = control
        task.start()
        return task

    def _hold_context(self, control: tuple[str, str]):
        @contextmanager
        def manager() -> Iterator[None]:
            token = self._acquire_lease(control)
            try:
                yield
            finally:
                self._release_lease(token)
        return manager()

    def _release_kind(self, kind: str) -> None:
        with self._lock:
            tasks = [task for task, control in self._tasks.items() if control[0] == kind]
        for task in tasks:
            task.cancel()
        with self._lock:
            controls = {
                control for control in self._direct_held | set(self._lease_counts)
                if control[0] == kind
            }
            errors = []
            for control in controls:
                try:
                    self._backend_up(control)
                except Exception as exc:
                    errors.append(exc)
            self._direct_held = {item for item in self._direct_held if item[0] != kind}
            for token, control in tuple(self._leases.items()):
                if control[0] == kind:
                    self._leases.pop(token, None)
            self._lease_counts = {control: count for control, count in self._lease_counts.items() if control[0] != kind}
            for task in tasks:
                self._tasks.pop(task, None)
            if errors:
                raise errors[0]

    def release_all(self) -> None:
        """Release all inputs owned by this controller (best effort)."""
        errors = []
        for kind in ("key", "mouse"):
            try:
                self._release_kind(kind)
            except Exception as exc:
                errors.append(exc)
        # Backend-level cleanup also clears state not tracked by this controller,
        # and is attempted even if one individual key/button release failed.
        try:
            self.backend.release_all()
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise errors[0]

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.release_all()
        finally:
            self.backend.close()
            self._closed = True

    def __enter__(self) -> "InputController":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class Keyboard:
    def __init__(self, controller: InputController) -> None:
        self._controller = controller

    def press(self, key: str) -> None:
        name = self._controller._resolve("key", key)
        self._controller._press_direct(("key", name))

    def release(self, key: str) -> None:
        name = self._controller._resolve("key", key)
        self._controller._release_direct(("key", name))

    def tap(self, key: str, duration: float = 0.05, *, blocking: bool = True):
        name = self._controller._resolve("key", key)
        return self._controller._hold(("key", name), duration, blocking)

    def hold(self, key: str, duration: float = 1.0, *, blocking: bool = True):
        return self.tap(key, duration, blocking=blocking)

    def press_many(self, *keys: str) -> None:
        names = [self._controller._resolve("key", key) for key in keys]
        acquired = []
        try:
            for name in names:
                control = ("key", name)
                was_direct = control in self._controller._direct_held
                self._controller._press_direct(control)
                if not was_direct:
                    acquired.append(name)
        except Exception:
            for name in reversed(acquired):
                try:
                    self.release(name)
                except Exception:
                    pass
            raise

    def release_many(self, *keys: str) -> None:
        names = [self._controller._resolve("key", key) for key in keys]
        for name in reversed(names):
            self._controller._release_direct(("key", name))

    def hotkey(self, *keys: str, interval: float = 0.03) -> None:
        """Press a chord, wait briefly, then release in reverse order."""
        names = [self._controller._resolve("key", key) for key in keys]
        if not names:
            raise ValueError("hotkey() requires at least one key.")
        delay = self._controller._validate_duration(interval)
        tokens = []
        try:
            for name in names:
                tokens.append(self._controller._acquire_lease(("key", name)))
            if delay:
                time.sleep(delay)
        finally:
            for token in reversed(tokens):
                self._controller._release_lease(token)

    def held(self, key: str):
        name = self._controller._resolve("key", key)
        return self._controller._hold_context(("key", name))

    def release_all(self) -> None:
        self._controller._release_kind("key")

    def register_alias(self, alias: str, target: str) -> None:
        try:
            self._controller.key_registry.register_alias(alias, target)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(str(exc)) from exc

    def unregister_alias(self, alias: str) -> None:
        self._controller.key_registry.unregister_alias(alias)

    @property
    def names(self) -> tuple[str, ...]:
        return KEY_NAMES


class Mouse:
    def __init__(self, controller: InputController) -> None:
        self._controller = controller

    def press(self, button: str = "left") -> None:
        name = self._controller._resolve("mouse", button)
        self._controller._press_direct(("mouse", name))

    def release(self, button: str = "left") -> None:
        name = self._controller._resolve("mouse", button)
        self._controller._release_direct(("mouse", name))

    def click(self, button: str = "left", duration: float = 0.05, *, blocking: bool = True):
        name = self._controller._resolve("mouse", button)
        return self._controller._hold(("mouse", name), duration, blocking)

    def double_click(self, button: str = "left", interval: float = 0.08) -> None:
        name = self._controller._resolve("mouse", button)
        delay = self._controller._validate_duration(interval)
        for index in range(2):
            self._controller._hold(("mouse", name), 0.04, blocking=True)
            if index == 0 and delay:
                time.sleep(delay)

    def held(self, button: str = "left"):
        name = self._controller._resolve("mouse", button)
        return self._controller._hold_context(("mouse", name))

    def move(self, x: int, y: int, *, screen_size: Optional[tuple[int, int]] = None) -> None:
        self._controller._ensure_open()
        self._controller.backend.move_to(int(x), int(y), screen_size)

    def move_to(self, x: int, y: int, *, screen_size: Optional[tuple[int, int]] = None) -> None:
        self.move(x, y, screen_size=screen_size)

    def move_relative(self, dx: int, dy: int) -> None:
        self._controller._ensure_open()
        self._controller.backend.move_relative(int(dx), int(dy))

    def scroll(self, vertical: int = 0, horizontal: int = 0) -> None:
        self._controller._ensure_open()
        self._controller.backend.scroll(int(horizontal), int(vertical))

    def release_all(self) -> None:
        self._controller._release_kind("mouse")

    def register_alias(self, alias: str, target: str) -> None:
        try:
            self._controller.mouse_registry.register_alias(alias, target)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(str(exc)) from exc

    def unregister_alias(self, alias: str) -> None:
        self._controller.mouse_registry.unregister_alias(alias)

    @property
    def buttons(self) -> tuple[str, ...]:
        return MOUSE_BUTTONS
