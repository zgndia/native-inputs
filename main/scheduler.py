"""Small cancellable timer task used for non-blocking input holds."""

from __future__ import annotations

import threading
from typing import Callable, Optional


class InputTask:
    """A daemon-timer task that runs its release callback exactly once."""

    def __init__(self, delay: float, callback: Callable[[], None], *, autostart: bool = True) -> None:
        self._callback = callback
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._completed = False
        self.error: Optional[BaseException] = None
        self._timer = threading.Timer(delay, self._finish)
        self._timer.daemon = True
        if autostart:
            self.start()

    def start(self) -> "InputTask":
        self._timer.start()
        return self

    def _finish(self) -> None:
        with self._lock:
            if self._completed:
                return
            self._completed = True
        try:
            self._callback()
        except BaseException as exc:  # Preserve timer-thread failures for wait().
            self.error = exc
        finally:
            self._done.set()

    def cancel(self) -> None:
        """Cancel the timer and release its input immediately."""
        self._timer.cancel()
        self._finish()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for completion; re-raise an exception from the release callback."""
        completed = self._done.wait(timeout)
        if completed and self.error is not None:
            raise self.error
        return completed

    @property
    def done(self) -> bool:
        return self._done.is_set()
