"""Small reusable widgets: status badge, summary card, engineer prompt."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QInputDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...models import DeskStatus


def status_badge(status: DeskStatus) -> QLabel:
    """A coloured pill that always shows the status text (accessibility).

    Colour comes from the domain enum so the dashboard, listing and detail
    views all use the same single source of truth.
    """
    label = QLabel(status.label)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background: {status.colour}; color: white; "
        f"border-radius: 9px; padding: 2px 10px; font-weight: 600;"
    )
    # Expose the text to assistive tech explicitly as well.
    label.setAccessibleName(f"Status: {status.label}")
    return label


class SummaryCard(QFrame):
    """A dashboard figure card: a title, a large value, optional colour bar."""

    def __init__(self, title: str, value: str, accent: str | None = None) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        self._value_label = QLabel(value)
        self._value_label.setObjectName("CardValue")
        if accent:
            self._value_label.setStyleSheet(f"color: {accent};")

        layout.addWidget(title_label)
        layout.addWidget(self._value_label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


def prompt_engineer(parent: QWidget, session) -> str | None:
    """Ask for the acting engineer's name, pre-filled from the session.

    Returns the trimmed name, or None if cancelled or left blank.
    """
    name, ok = QInputDialog.getText(
        parent,
        "Engineer",
        "Engineer performing this action:",
        text=session.engineer,
    )
    if not ok:
        return None
    name = name.strip()
    if not name:
        return None
    session.remember_engineer(name)
    return name
