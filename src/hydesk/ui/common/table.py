"""A simple, generic table model driving QTableView from a list of rows.

Each column is defined by a header and a callable that extracts a display
string from a row object. This keeps the listing views declarative and
free of per-cell boilerplate. Sorting is handled by the service/repository
layer (not the model), so the model stays a thin display adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Sequence, TypeVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

R = TypeVar("R")


@dataclass(frozen=True)
class Column(Generic[R]):
    header: str
    extract: Callable[[R], str]


class ObjectTableModel(QAbstractTableModel, Generic[R]):
    """Displays a list of row objects using a fixed set of Columns."""

    def __init__(self, columns: Sequence[Column[R]]) -> None:
        super().__init__()
        self._columns = list(columns)
        self._rows: list[R] = []

    def set_rows(self, rows: Sequence[R]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row_index: int) -> R | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    # --- Qt model interface ---------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        return self._columns[index.column()].extract(row)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section].header
        return section + 1
