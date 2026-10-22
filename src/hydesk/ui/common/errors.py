"""Helpers for turning service calls into user-friendly UI outcomes.

``run_guarded`` wraps a service call so that an expected HyDeskError is
shown as a clear message box (the message the service already wrote) while
an unexpected error is logged in full and shown as a generic failure. This
keeps every view's error handling consistent and stops business-rule
failures from ever crashing the UI.
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

from PySide6.QtWidgets import QMessageBox, QWidget

from ...errors import HyDeskError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Sentinel so callers can distinguish "operation failed" from a falsy result.
FAILED = object()


def run_guarded(parent: QWidget, action: Callable[[], T], *, title: str = "Error"):
    """Run ``action`` and handle errors uniformly.

    Returns the action's result on success, or ``FAILED`` if an error was
    handled (so the caller can skip any follow-up like closing a dialog).
    """
    try:
        return action()
    except HyDeskError as exc:
        QMessageBox.warning(parent, title, str(exc))
        return FAILED
    except Exception:  # noqa: BLE001 - last-resort guard, logged in full
        logger.exception("Unexpected error during UI action")
        QMessageBox.critical(
            parent,
            title,
            "An unexpected error occurred. The details have been logged.",
        )
        return FAILED


def confirm(parent: QWidget, title: str, message: str) -> bool:
    """Show a Yes/No confirmation. Returns True if the user confirmed."""
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
