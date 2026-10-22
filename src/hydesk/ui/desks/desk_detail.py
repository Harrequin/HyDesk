"""Desk detail / edit dialog.

Shows all information for one desk, lets an engineer change status, notes
and the Halo ticket, and displays the desk's change history. Edits go
through DeskService (one transaction: desk + history + audit); the dialog
only gathers input and reports outcomes.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...models import Desk, DeskStatus
from ...services import DeskService
from ..common.errors import FAILED, run_guarded
from ..common.format import fmt_datetime, fmt_text
from ..common.widgets import prompt_engineer, status_badge


class DeskDetailDialog(QDialog):
    def __init__(self, service: DeskService, session, desk_id: int, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._session = session
        self._desk_id = desk_id
        self.changed = False  # set True when a successful edit occurs

        self.setWindowTitle("Desk")
        self.setMinimumWidth(520)
        self._build()
        self._load()

    # --- construction ----------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        form = QFormLayout()
        self._floor_label = QLabel()
        self._badge_holder = QHBoxLayout()
        badge_row = QLabel()  # placeholder replaced in _load
        self._badge_widget = badge_row
        self._last_engineer = QLabel()
        self._last_updated = QLabel()

        self._status = QComboBox()
        for st in DeskStatus:
            self._status.addItem(st.label, st)
        self._halo = QLineEdit()
        self._halo.setPlaceholderText("7 digits, e.g. 1234567")
        self._notes = QPlainTextEdit()
        self._notes.setFixedHeight(80)

        form.addRow("Desk:", self._floor_label)
        form.addRow("Current status:", self._badge_widget)
        form.addRow("Last engineer:", self._last_engineer)
        form.addRow("Last updated:", self._last_updated)
        form.addRow("Set status:", self._status)
        form.addRow("Halo ticket:", self._halo)
        form.addRow("Notes:", self._notes)
        layout.addLayout(form)

        # History table.
        layout.addWidget(QLabel("History"))
        self._history = QTableWidget(0, 5)
        self._history.setHorizontalHeaderLabels(
            ["When", "From", "To", "Engineer", "Notes"]
        )
        self._history.horizontalHeader().setStretchLastSection(True)
        self._history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._history)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save changes")
        save.setObjectName("Primary")
        close = QPushButton("Close")
        save.clicked.connect(self._save)
        close.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # --- data ------------------------------------------------------------
    def _load(self) -> None:
        desk = self._service.get_desk(self._desk_id)
        self._render(desk)
        self._render_history()

    def _render(self, desk: Desk) -> None:
        self.setWindowTitle(f"Desk {desk.identifier}")
        self._title.setText(f"Desk {desk.identifier}")
        self._floor_label.setText(f"{desk.identifier}  (Floor {desk.floor})")

        # Replace the status badge widget in the form.
        new_badge = status_badge(desk.status)
        self._badge_widget.parentWidget().layout().replaceWidget(
            self._badge_widget, new_badge
        )
        self._badge_widget.deleteLater()
        self._badge_widget = new_badge

        self._last_engineer.setText(fmt_text(desk.last_engineer))
        self._last_updated.setText(fmt_datetime(desk.last_updated))

        index = self._status.findData(desk.status)
        if index >= 0:
            self._status.setCurrentIndex(index)
        self._halo.setText(desk.halo_ticket or "")
        self._notes.setPlainText(desk.notes or "")

    def _render_history(self) -> None:
        history = self._service.view_history(self._desk_id)
        self._history.setRowCount(len(history))
        for row, entry in enumerate(history):
            prev = entry.previous_status.label if entry.previous_status else "—"
            new = entry.new_status.label if entry.new_status else "—"
            cells = [
                fmt_datetime(entry.changed_at),
                prev,
                new,
                entry.engineer,
                fmt_text(entry.notes),
            ]
            for col, text in enumerate(cells):
                self._history.setItem(row, col, QTableWidgetItem(text))

    # --- actions ---------------------------------------------------------
    def _save(self) -> None:
        engineer = prompt_engineer(self, self._session)
        if engineer is None:
            return

        status = self._status.currentData()
        halo_text = self._halo.text().strip()
        notes_text = self._notes.toPlainText()

        result = run_guarded(
            self,
            lambda: self._service.update_desk(
                self._desk_id,
                engineer,
                status=status,
                notes=notes_text if notes_text else None,
                update_notes=True,
                halo_ticket=halo_text if halo_text else None,
                update_halo=True,
            ),
            title="Could not update desk",
        )
        if result is FAILED:
            return

        self.changed = True
        self._load()
