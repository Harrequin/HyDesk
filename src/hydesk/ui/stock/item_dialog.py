"""Create / edit a stock item.

Quantity is intentionally not editable here: all quantity changes go
through the movements dialog so they are recorded in the ledger. This
dialog handles item details only (name, category, location, threshold) and
the opening quantity on creation.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...models import StockItem
from ...services import StockService
from ..common.errors import FAILED, run_guarded
from ..common.widgets import prompt_engineer


class StockItemDialog(QDialog):
    def __init__(self, service: StockService, session, item: StockItem | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._session = session
        self._item = item
        self.saved = False

        self.setWindowTitle("Edit Stock Item" if item else "New Stock Item")
        self.setMinimumWidth(420)
        self._build()
        if item:
            self._populate(item)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit()
        self._category = QLineEdit()
        self._location = QLineEdit()
        self._threshold = QSpinBox()
        self._threshold.setRange(0, 1_000_000)

        form.addRow("Name:", self._name)
        form.addRow("Category:", self._category)
        form.addRow("Location:", self._location)
        form.addRow("Low-stock threshold:", self._threshold)

        # Opening quantity only shown when creating.
        self._opening = QSpinBox()
        self._opening.setRange(0, 1_000_000)
        if self._item is None:
            form.addRow("Opening quantity:", self._opening)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _populate(self, item: StockItem) -> None:
        self._name.setText(item.name)
        self._category.setText(item.category)
        self._location.setText(item.location or "")
        self._threshold.setValue(item.low_stock_threshold)

    def _save(self) -> None:
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return

        name = self._name.text().strip()
        category = self._category.text().strip()
        location = self._location.text().strip()
        threshold = self._threshold.value()

        if self._item is None:
            result = run_guarded(
                self,
                lambda: self._service.create_item(
                    category, name, engineer,
                    location=location or None,
                    initial_quantity=self._opening.value(),
                    low_stock_threshold=threshold,
                ),
                title="Could not create item",
            )
        else:
            result = run_guarded(
                self,
                lambda: self._service.edit_item(
                    self._item.id, engineer,
                    name=name, category=category,
                    location=location or None, update_location=True,
                    low_stock_threshold=threshold,
                ),
                title="Could not update item",
            )

        if result is FAILED:
            return
        self.saved = True
        self.accept()
