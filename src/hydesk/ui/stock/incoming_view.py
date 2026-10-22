"""Incoming deliveries: record expected, receive (partial/full), cancel.

Receiving is the atomic operation that moves expected stock into available
stock; the view just collects input and calls IncomingService, then
refreshes.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...config import Config
from ...models import DeliveryStatus
from ...repositories import PageRequest
from ...services import IncomingService, StockService
from ..common.errors import FAILED, confirm, run_guarded
from ..common.format import fmt_datetime, fmt_text
from ..common.table import Column, ObjectTableModel
from ..common.widgets import prompt_engineer


class _ExpectedDialog(QDialog):
    """Collects a new expected delivery (item + quantity + note)."""

    def __init__(self, stock: StockService, parent=None) -> None:
        super().__init__(parent)
        self._stock = stock
        self.setWindowTitle("Record Expected Delivery")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._item = QComboBox()
        # Load items (unpaginated) for selection.
        from ...repositories import StockQuery
        page = stock.search_items(StockQuery(), PageRequest(page_size=0))
        for it in page.items:
            self._item.addItem(f"{it.name} ({it.category})", it.id)
        self._qty = QSpinBox()
        self._qty.setRange(1, 1_000_000)
        self._note = QLineEdit()
        form.addRow("Item:", self._item)
        form.addRow("Expected quantity:", self._qty)
        form.addRow("Note:", self._note)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("Record")
        ok.setObjectName("Primary")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    @property
    def item_id(self):
        return self._item.currentData()

    @property
    def quantity(self) -> int:
        return self._qty.value()

    @property
    def note(self) -> str | None:
        return self._note.text().strip() or None

    @property
    def has_items(self) -> bool:
        return self._item.count() > 0


class IncomingView(QWidget):
    def __init__(
        self,
        incoming: IncomingService,
        stock: StockService,
        session,
        config: Config | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._incoming = incoming
        self._stock = stock
        self._session = session
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Incoming Deliveries")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self._filter = QComboBox()
        self._filter.addItem("All", None)
        for st in DeliveryStatus:
            self._filter.addItem(st.label, st)
        self._filter.currentIndexChanged.connect(self.refresh)
        header.addWidget(QLabel("Status:"))
        header.addWidget(self._filter)
        layout.addLayout(header)

        self._model = ObjectTableModel([
            Column("Item", lambda d: self._item_name(d.stock_item_id)),
            Column("Expected", lambda d: str(d.expected_qty)),
            Column("Received", lambda d: str(d.received_qty)),
            Column("Outstanding", lambda d: str(d.outstanding_qty)),
            Column("Status", lambda d: d.status.label),
            Column("Recorded", lambda d: fmt_datetime(d.date_recorded)),
            Column("Received on", lambda d: fmt_datetime(d.actual_receipt_date)),
            Column("Notes", lambda d: fmt_text(d.notes)),
        ])
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        footer = QHBoxLayout()
        new_btn = QPushButton("Record expected")
        new_btn.setObjectName("Primary")
        new_btn.clicked.connect(self._record_expected)
        receive_btn = QPushButton("Receive")
        receive_btn.clicked.connect(self._receive)
        cancel_btn = QPushButton("Cancel delivery")
        cancel_btn.clicked.connect(self._cancel)
        footer.addWidget(new_btn)
        footer.addWidget(receive_btn)
        footer.addWidget(cancel_btn)
        footer.addStretch(1)
        layout.addLayout(footer)

        # Cache item names so the table can show them without per-row queries.
        self._item_names: dict[int, str] = {}

    def _item_name(self, item_id: int) -> str:
        if item_id not in self._item_names:
            try:
                self._item_names[item_id] = self._stock.get_item(item_id).name
            except Exception:  # noqa: BLE001
                self._item_names[item_id] = f"#{item_id}"
        return self._item_names[item_id]

    def refresh(self) -> None:
        self._item_names.clear()
        status = self._filter.currentData()
        page = self._incoming.list_deliveries(PageRequest(page_size=0), status=status)
        self._model.set_rows(page.items)

    def _selected(self):
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        return self._model.row_at(index.row())

    def _record_expected(self) -> None:
        dialog = _ExpectedDialog(self._stock, self)
        if not dialog.has_items:
            QMessageBox.information(
                self, "No items", "Create a stock item before recording a delivery."
            )
            return
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return
        result = run_guarded(
            self,
            lambda: self._incoming.record_expected(
                dialog.item_id, dialog.quantity, engineer, notes=dialog.note
            ),
            title="Could not record delivery",
        )
        if result is not FAILED:
            self.refresh()

    def _receive(self) -> None:
        delivery = self._selected()
        if delivery is None:
            return
        remaining = delivery.outstanding_qty
        if remaining <= 0:
            return
        qty, ok = QInputDialog.getInt(
            self, "Receive stock",
            f"Quantity to receive (outstanding {remaining}):",
            value=remaining, minValue=1, maxValue=remaining,
        )
        if not ok:
            return
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return
        result = run_guarded(
            self,
            lambda: self._incoming.receive_delivery(delivery.id, qty, engineer),
            title="Could not receive stock",
        )
        if result is not FAILED:
            self.refresh()

    def _cancel(self) -> None:
        delivery = self._selected()
        if delivery is None:
            return
        if not confirm(
            self, "Cancel delivery",
            "Cancel this delivery? Stock already received is unaffected.",
        ):
            return
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return
        result = run_guarded(
            self,
            lambda: self._incoming.cancel_delivery(delivery.id, engineer),
            title="Could not cancel delivery",
        )
        if result is not FAILED:
            self.refresh()
