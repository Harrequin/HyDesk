"""Application exception hierarchy.

A small, explicit hierarchy so the presentation layer can distinguish
user-correctable problems (ValidationError, NotFoundError, ConflictError)
from genuine faults (everything else deriving from HyDeskError).
"""

from __future__ import annotations


class HyDeskError(Exception):
    """Base class for all application-specific errors."""


class ValidationError(HyDeskError):
    """Raised when input fails a business validation rule.

    These are expected, user-correctable conditions (e.g. a malformed
    Halo ticket reference) and should be surfaced to the user as a clear
    message rather than a crash.
    """


class NotFoundError(HyDeskError):
    """Raised when a requested record does not exist."""


class ConflictError(HyDeskError):
    """Raised when an operation would violate a uniqueness or state rule."""
