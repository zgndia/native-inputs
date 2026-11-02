"""Exceptions exposed by Native keyboard inputs."""


class NativeInputError(Exception):
    """Base class for package errors."""


class InvalidInputError(NativeInputError, ValueError):
    """An unknown or malformed key/button name was supplied."""


class UnsupportedPlatformError(NativeInputError, RuntimeError):
    """The current operating system has no supported backend."""


class BackendUnavailableError(NativeInputError, RuntimeError):
    """A native backend could not be initialized or is unavailable."""


class BackendPermissionError(BackendUnavailableError, PermissionError):
    """The process lacks permission to create or inject native input."""


class UnsupportedInputError(NativeInputError, NotImplementedError):
    """A valid portable input has no implementation on this backend."""


class InputInjectionError(NativeInputError, OSError):
    """The operating system rejected an input event."""
