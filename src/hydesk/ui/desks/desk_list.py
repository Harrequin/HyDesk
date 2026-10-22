"""Desk listing view: search, filter, sort, paginate, open detail.

The view holds the current DeskQuery and PageRequest and re-queries the
service whenever any control changes. Sorting and filtering are done by the
service/repository, so changing one control preserves the others (the view
rebuilds a full query each time rather than mutating hidden state).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...config import Config
from ...models import DeskStatus
from ...repositories import DeskQuery, PageRequest
from ...repositories.desk_repo import DeskSort
from ...services import DeskService
from ..common.format import fmt_datetime, fmt_text
from ..common.pagination import PaginationBar
from ..common.table import Column, ObjectTableModel
from .desk_detail import DeskDetailDialog

_SORT_OPTIONS = [
    ("Identifier", DeskSort.IDENTIFIER),
    ("Floor", DeskSort.FLOOR),
    ("Status", DeskSort.STATUS),
    ("Engineer", DeskSort.ENGINEER),
    ("Last updated", DeskSort.LAST_UPDATED),
]


class DeskListView(QWidget):
    def __init__(self, service: DeskService, session, config: Config | None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._session = session
        page_sizes = config.ui.page_size_options if config else (25, 50, 100, 200)
        default_size = config.ui.default_page_size if config else 50

        self._page = 1
        self._build(page_sizes, default_size)
        self.refresh()

    # --- construction ----------------------------------------------------
    def _build(self, page_sizes, default_size) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Desks")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Toolbar: search, floor filter, status filter, sort, direction.
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search identifier, engineer, ticket, notes")
        self._search.returnPressed.connect(self._reset_and_refresh)

        self._floor = QComboBox()
        self._floor.addItem("All floors", None)
        self._floor.addItem("Floor 4", 4)
        self._floor.addItem("Floor 5", 5)
        self._floor.currentIndexChanged.connect(self._reset_and_refresh)

        self._status = QComboBox()
        self._status.addItem("All statuses", None)
        for st in DeskStatus:
            self._status.addItem(st.label, st)
        self._status.currentIndexChanged.connect(self._reset_and_refresh)

        self._sort = QComboBox()
        for label, value in _SORT_OPTIONS:
            self._sort.addItem(label, value)
        self._sort.currentIndexChanged.connect(self._reset_and_refresh)

        self._direction = QComboBox()
        self._direction.addItem("Ascending", False)
        self._direction.addItem("Descending", True)
        self._direction.currentIndexChanged.connect(self._reset_and_refresh)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._reset_and_refresh)

        toolbar.addWidget(self._search, 2)
        toolbar.addWidget(self._floor)
        toolbar.addWidget(self._status)
        toolbar.addWidget(QLabel("Sort:"))
        toolbar.addWidget(self._sort)
        toolbar.addWidget(self._direction)
        toolbar.addWidget(search_btn)
        layout.addLayout(toolbar)

        # Table.
        self._model = ObjectTableModel([
            Column("Identifier", lambda d: d.identifier),
            Column("Floor", lambda d: str(d.floor)),
            Column("Status", lambda d: d.status.label),
            Column("Engineer", lambda d: fmt_text(d.last_engineer)),
            Column("Halo", lambda d: fmt_text(d.halo_ticket)),
            Column("Last updated", lambda d: fmt_datetime(d.last_updated)),
        ])
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self._table)

        # Footer: open button + pagination.
        footer = QHBoxLayout()
        open_btn = QPushButton("Open desk")
        open_btn.clicked.connect(self._open_selected)
        footer.addWidget(open_btn)
        footer.addStretch(1)
        self._pager = PaginationBar(tuple(page_sizes), default_size)
        self._pager.page_changed.connect(self._go_to_page)
        self._pager.page_size_changed.connect(self._reset_and_refresh)
        footer.addWidget(self._pager)
        layout.addLayout(footer)

    # --- querying --------------------------------------------------------
    def _current_query(self) -> DeskQuery:
        return DeskQuery(
            search=self._search.text().strip() or None,
            floor=self._floor.currentData(),
            status=self._status.currentData(),
            sort=self._sort.currentData(),
            descending=bool(self._direction.currentData()),
        )

    def refresh(self) -> None:
        request = PageRequest(page=self._page, page_size=self._pager.page_size)
        page = self._service.search_desks(self._current_query(), request)
        self._model.set_rows(page.items)
        self._pager.update_from_page(page)

    def _reset_and_refresh(self) -> None:
        self._page = 1
        self._pager.reset_to_first_page()
        self.refresh()

    def _go_to_page(self, page: int) -> None:
        self._page = page
        self.refresh()

    # --- actions ---------------------------------------------------------
    def apply_status_filter(self, status: DeskStatus | None) -> None:
        """Called from the dashboard to jump into a filtered listing."""
        index = self._status.findData(status) if status is not None else 0
        self._status.setCurrentIndex(max(0, index))
        self._reset_and_refresh()

    def _open_selected(self) -> None:
        index = self._table.currentIndex()
        if not index.isValid():
            return
        desk = self._model.row_at(index.row())
        if desk is None:
            return
        dialog = DeskDetailDialog(self._service, self._session, desk.id, self)
        dialog.exec()
        if dialog.changed:
            self.refresh()
