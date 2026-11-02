"""Native input backend implementations."""

from __future__ import annotations
import platform

from .base import InputBackend
from .fake import FakeBackend
from ..exceptions import UnsupportedPlatformError


def create_backend(name: str | None = None, **options) -> InputBackend:
    """Create a backend without importing platform-specific modules eagerly."""
    selected = (name or platform.system()).strip().lower()
    aliases = {"win32": "windows", "win": "windows", "darwin": "macos", "osx": "macos"}
    selected = aliases.get(selected, selected)
    if selected == "fake":
        return FakeBackend()
    if selected == "windows":
        from .windows import WindowsBackend
        return WindowsBackend(**options)
    if selected in {"windows_vhf", "vhf"}:
        if options:
            unexpected = ", ".join(sorted(options))
            raise TypeError(f"windows_vhf does not accept backend options: {unexpected}")
        from .windows_vhf import WindowsVHFBackend
        return WindowsVHFBackend()
    if selected == "linux":
        from .linux import LinuxBackend
        return LinuxBackend(**options)
    if selected in {"macos", "mac"}:
        from .macos import MacOSBackend
        return MacOSBackend(**options)
    raise UnsupportedPlatformError(
        f"Unsupported backend {name!r}. Supported values: windows, windows_vhf, linux, macos, fake."
    )


__all__ = ["InputBackend", "FakeBackend", "create_backend"]
