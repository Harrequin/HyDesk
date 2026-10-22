"""Stock dashboard view: live figures, low/out-of-stock lists, breakdowns."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services import StockDashboardService
from ..common.widgets import SummaryCard


class StockDashboardView(QWidget):
    def __init__(self, service: StockDashboardService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._cards: dict[str, SummaryCard] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Stock Dashboard")
        title.setObjectName("PageTitle")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(refresh)
        layout.addLayout(header)

        grid = QGridLayout()
        defs = [
            ("items", "Distinct items"),
            ("quantity", "Available quantity"),
            ("low", "Low stock"),
            ("out", "Out of stock"),
            ("incoming", "Incoming deliveries"),
            ("outstanding", "Outstanding incoming"),
        ]
        for col, (key, label) in enumerate(defs):
            card = SummaryCard(label, "0")
            self._cards[key] = card
            grid.addWidget(card, 0, col)
        layout.addLayout(grid)

        layout.addWidget(QLabel("Attention"))
        self._attention = QLabel()
        self._attention.setWordWrap(True)
        layout.addWidget(self._attention)

        layout.addWidget(QLabel("By category"))
        self._category = QLabel()
        self._category.setWordWrap(True)
        layout.addWidget(self._category)

        layout.addWidget(QLabel("By location"))
        self._location = QLabel()
        self._location.setWordWrap(True)
        layout.addWidget(self._location)

        layout.addStretch(1)

    def refresh(self) -> None:
        d = self._service.build()
        self._cards["items"].set_value(str(d.total_items))
        self._cards["quantity"].set_value(str(d.total_quantity))
        self._cards["low"].set_value(str(d.low_stock_count))
        self._cards["out"].set_value(str(d.out_of_stock_count))
        self._cards["incoming"].set_value(str(d.incoming_deliveries))
        self._cards["outstanding"].set_value(str(d.outstanding_incoming_qty))

        low = ", ".join(i.name for i in d.low_stock) or "none"
        out = ", ".join(i.name for i in d.out_of_stock) or "none"
        self._attention.setText(f"Low stock: {low}\nOut of stock: {out}")

        self._category.setText(
            "   ".join(f"{k}: {v}" for k, v in sorted(d.category_breakdown.items()))
            or "—"
        )
        self._location.setText(
            "   ".join(f"{k}: {v}" for k, v in sorted(d.location_breakdown.items()))
            or "—"
        )
