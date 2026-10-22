"""Record a stock movement and view an item's movement history.

Every quantity change is a movement (received / issued / adjustment /
correction). The dialog gathers the type, quantity and a note, then calls
the matching StockService method so the balance, movement row and audit are
written atomically.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...models import MovementType
from ...services import StockService
from ..common.errors import FAILED, run_guarded
from ..common.format import fmt_datetime, fmt_text
from ..common.widgets import prompt_engineer

# Movement types offered, with whether the quantity is added or removed.
_MOVEMENTS = [
    ("Receive (add)", MovementType.RECEIVED, +1),
    ("Issue (remove)", MovementType.ISSUED, -1),
    ("Adjustment (add)", MovementType.ADJUSTMENT, +1),
    ("Adjustment (remove)", MovementType.ADJUSTMENT, -1),
    ("Correction (add)", MovementType.CORRECTION, +1),
    ("Correction (remove)", MovementType.CORRECTION, -1),
]


class MovementDialog(QDialog):
    def __init__(self, service: StockService, session, item_id: int, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._session = session
        self._item_id = item_id
        self.changed = False

        self.setWindowTitle("Stock Movements")
        self.setMinimumWidth(560)
        self._build()
        self._load()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self._heading = QLabel()
        self._heading.setObjectName("PageTitle")
        layout.addWidget(self._heading)

        form = QFormLayout()
        self._type = QComboBox()
        for label, mtype, sign in _MOVEMENTS:
            self._type.addItem(label, (mtype, sign))
        self._qty = QSpinBox()
        self._qty.setRange(1, 1_000_000)
        self._note = QLineEdit()
        form.addRow("Movement:", self._type)
        form.addRow("Quantity:", self._qty)
        form.addRow("Note / reason:", self._note)
        layout.addLayout(form)

        record = QPushButton("Record movement")
        record.setObjectName("Primary")
        record.clicked.connect(self._record)
        layout.addWidget(record)

        layout.addWidget(QLabel("Movement history"))
        self._history = QTableWidget(0, 6)
        self._history.setHorizontalHeaderLabels(
            ["When", "Type", "Change", "Before", "After", "Note"]
        )
        self._history.horizontalHeader().setStretchLastSection(True)
        self._history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._history)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _load(self) -> None:
        item = self._service.get_item(self._item_id)
        self._heading.setText(f"{item.name}  —  on hand: {item.quantity}")
        movements = self._service.movements_for(self._item_id)
        self._history.setRowCount(len(movements))
        for row, m in enumerate(movements):
            change = f"{m.quantity:+d}"
            cells = [
                fmt_datetime(m.occurred_at),
                m.movement_type.label,
                change,
                str(m.previous_qty),
                str(m.resulting_qty),
                fmt_text(m.notes),
            ]
            for col, text in enumerate(cells):
                self._history.setItem(row, col, QTableWidgetItem(text))

    def _record(self) -> None:
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return
        mtype, sign = self._type.currentData()
        delta = sign * self._qty.value()
        note = self._note.text().strip() or None

        result = run_guarded(
            self,
            lambda: self._service.record_movement(
                self._item_id, mtype, delta, engineer, notes=note
            ),
            title="Could not record movement",
        )
        if result is FAILED:
            return
        self.changed = True
        self._note.clear()
        self._load()
