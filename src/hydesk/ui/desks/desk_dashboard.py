"""Desk dashboard view.

Shows live figures as summary cards and a per-floor breakdown. Clicking a
status card asks the parent section to open the desk listing filtered to
that status (navigate-from-figure-to-list, per the brief).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...models import DeskStatus
from ...services import DeskDashboardService
from ..common.widgets import SummaryCard


class _ClickableCard(SummaryCard):
    """A summary card that emits a status when clicked."""

    clicked = Signal(object)

    def __init__(self, title, value, status, accent=None) -> None:
        super().__init__(title, value, accent)
        self._status = status
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._status)
        super().mouseReleaseEvent(event)


class DeskDashboardView(QWidget):
    open_filtered = Signal(object)  # emits a DeskStatus (or None for all)

    def __init__(self, service: DeskDashboardService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._cards: dict[str, SummaryCard] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Desk Dashboard")
        title.setObjectName("PageTitle")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(refresh)
        layout.addLayout(header)

        # Summary cards.
        grid = QGridLayout()
        self._total_card = SummaryCard("Total desks", "0")
        grid.addWidget(self._total_card, 0, 0)

        card_defs = [
            ("active", "Active", DeskStatus.ACTIVE),
            ("down", "Down", DeskStatus.DOWN),
            ("in_repair", "In Repair", DeskStatus.IN_REPAIR),
            ("awaiting", "Awaiting Equipment", DeskStatus.AWAITING_EQUIPMENT),
        ]
        for col, (key, label, status) in enumerate(card_defs, start=1):
            card = _ClickableCard(label, "0", status, accent=status.colour)
            card.clicked.connect(self.open_filtered.emit)
            self._cards[key] = card
            grid.addWidget(card, 0, col)
        layout.addLayout(grid)

        # Per-floor breakdown.
        layout.addWidget(QLabel("Status by floor"))
        self._floor_box = QVBoxLayout()
        layout.addLayout(self._floor_box)

        layout.addStretch(1)

    def refresh(self) -> None:
        data = self._service.build()
        self._total_card.set_value(str(data.total))
        self._cards["active"].set_value(str(data.active))
        self._cards["down"].set_value(str(data.down))
        self._cards["in_repair"].set_value(str(data.in_repair))
        self._cards["awaiting"].set_value(str(data.awaiting_equipment))

        # Rebuild floor rows.
        while self._floor_box.count():
            item = self._floor_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for floor in sorted(data.status_by_floor):
            counts = data.status_by_floor[floor]
            parts = [f"{st.label}: {counts.get(st, 0)}" for st in DeskStatus]
            row = QLabel(f"Floor {floor}   " + "    ".join(parts))
            self._floor_box.addWidget(row)
