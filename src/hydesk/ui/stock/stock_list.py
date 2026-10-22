"""Stock item listing: search, filter, sort, paginate; create/edit/move."""

from __future__ import annotations

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
from ...repositories import PageRequest, StockQuery
from ...repositories.stock_repo import StockSort
from ...services import StockService
from ..common.format import fmt_datetime, fmt_text
from ..common.pagination import PaginationBar
from ..common.table import Column, ObjectTableModel
from .item_dialog import StockItemDialog
from .movement_dialog import MovementDialog

_SORT_OPTIONS = [
    ("Name", StockSort.NAME),
    ("Category", StockSort.CATEGORY),
    ("Quantity", StockSort.QUANTITY),
    ("Last updated", StockSort.LAST_UPDATED),
]


class StockListView(QWidget):
    def __init__(self, service: StockService, session, config: Config | None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._session = session
        page_sizes = config.ui.page_size_options if config else (25, 50, 100, 200)
        default_size = config.ui.default_page_size if config else 50

        self._page = 1
        self._build(page_sizes, default_size)
        self.refresh()

    def _build(self, page_sizes, default_size) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Stock Items")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search item name")
        self._search.returnPressed.connect(self._reset_and_refresh)
        self._category = QLineEdit()
        self._category.setPlaceholderText("Category filter")
        self._category.returnPressed.connect(self._reset_and_refresh)
        self._location = QLineEdit()
        self._location.setPlaceholderText("Location filter")
        self._location.returnPressed.connect(self._reset_and_refresh)

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
        toolbar.addWidget(self._category)
        toolbar.addWidget(self._location)
        toolbar.addWidget(QLabel("Sort:"))
        toolbar.addWidget(self._sort)
        toolbar.addWidget(self._direction)
        toolbar.addWidget(search_btn)
        layout.addLayout(toolbar)

        self._model = ObjectTableModel([
            Column("Name", lambda i: i.name),
            Column("Category", lambda i: i.category),
            Column("Location", lambda i: fmt_text(i.location)),
            Column("Quantity", lambda i: str(i.quantity)),
            Column("Threshold", lambda i: str(i.low_stock_threshold)),
            Column("Last updated", lambda i: fmt_datetime(i.last_updated)),
        ])
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self._table)

        footer = QHBoxLayout()
        new_btn = QPushButton("New item")
        new_btn.setObjectName("Primary")
        new_btn.clicked.connect(self._create)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_selected)
        move_btn = QPushButton("Movements")
        move_btn.clicked.connect(self._movements_selected)
        footer.addWidget(new_btn)
        footer.addWidget(edit_btn)
        footer.addWidget(move_btn)
        footer.addStretch(1)
        self._pager = PaginationBar(tuple(page_sizes), default_size)
        self._pager.page_changed.connect(self._go_to_page)
        self._pager.page_size_changed.connect(self._reset_and_refresh)
        footer.addWidget(self._pager)
        layout.addLayout(footer)

    def _current_query(self) -> StockQuery:
        return StockQuery(
            search=self._search.text().strip() or None,
            category=self._category.text().strip() or None,
            location=self._location.text().strip() or None,
            sort=self._sort.currentData(),
            descending=bool(self._direction.currentData()),
        )

    def refresh(self) -> None:
        request = PageRequest(page=self._page, page_size=self._pager.page_size)
        page = self._service.search_items(self._current_query(), request)
        self._model.set_rows(page.items)
        self._pager.update_from_page(page)

    def _reset_and_refresh(self) -> None:
        self._page = 1
        self._pager.reset_to_first_page()
        self.refresh()

    def _go_to_page(self, page: int) -> None:
        self._page = page
        self.refresh()

    def _selected_item(self):
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        return self._model.row_at(index.row())

    def _create(self) -> None:
        dialog = StockItemDialog(self._service, self._session, None, self)
        dialog.exec()
        if dialog.saved:
            self.refresh()

    def _edit_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        dialog = StockItemDialog(self._service, self._session, item, self)
        dialog.exec()
        if dialog.saved:
            self.refresh()

    def _movements_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        dialog = MovementDialog(self._service, self._session, item.id, self)
        dialog.exec()
        if dialog.changed:
            self.refresh()
