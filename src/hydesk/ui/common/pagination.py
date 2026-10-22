"""Pagination control bar.

Emits a signal when the user moves pages or changes the page size, leaving
the owning view to re-query. Page sizes come from configuration so they are
not hardcoded in the UI.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ...repositories import Page


class PaginationBar(QWidget):
    """Previous/Next controls, a page indicator and a page-size selector."""

    page_changed = Signal(int)       # emits the requested 1-based page
    page_size_changed = Signal(int)  # emits the new page size

    def __init__(self, page_sizes: tuple[int, ...], default_size: int) -> None:
        super().__init__()
        self._page = 1
        self._total_pages = 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._prev = QPushButton("Previous")
        self._next = QPushButton("Next")
        self._prev.clicked.connect(self._go_prev)
        self._next.clicked.connect(self._go_next)

        self._indicator = QLabel("Page 1 of 1")

        self._size = QComboBox()
        for size in page_sizes:
            self._size.addItem(f"{size} / page", size)
        default_index = self._size.findData(default_size)
        if default_index >= 0:
            self._size.setCurrentIndex(default_index)
        self._size.currentIndexChanged.connect(self._size_changed)

        layout.addWidget(self._prev)
        layout.addWidget(self._indicator)
        layout.addWidget(self._next)
        layout.addStretch(1)
        layout.addWidget(QLabel("Rows:"))
        layout.addWidget(self._size)

    @property
    def page_size(self) -> int:
        return int(self._size.currentData())

    def update_from_page(self, page: Page) -> None:
        """Refresh the indicator and button states from a results page."""
        self._page = page.page
        self._total_pages = page.total_pages
        self._indicator.setText(
            f"Page {page.page} of {page.total_pages}  ({page.total} rows)"
        )
        self._prev.setEnabled(page.has_previous)
        self._next.setEnabled(page.has_next)

    def reset_to_first_page(self) -> None:
        self._page = 1

    def _go_prev(self) -> None:
        if self._page > 1:
            self._page -= 1
            self.page_changed.emit(self._page)

    def _go_next(self) -> None:
        if self._page < self._total_pages:
            self._page += 1
            self.page_changed.emit(self._page)

    def _size_changed(self) -> None:
        self._page = 1
        self.page_size_changed.emit(self.page_size)
