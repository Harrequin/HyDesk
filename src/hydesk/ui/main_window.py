"""Main application window: left-hand navigation + stacked sections."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from ..app_context import AppContext
from .desks.desk_section import DesksSection
from .session import Session
from .stock.stock_section import StockSection


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self._context = context
        self._session = Session()

        self.setWindowTitle("HyDesk")
        self.resize(1100, 720)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left navigation.
        self._nav = QListWidget()
        self._nav.setObjectName("NavList")
        self._nav.setFixedWidth(200)
        for label in ("Desks", "Stock"):
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(0, 44))
            self._nav.addItem(item)

        # Stacked sections.
        self._stack = QStackedWidget()
        self._desks = DesksSection(context, self._session)
        self._stock = StockSection(context, self._session)
        self._stack.addWidget(self._desks)
        self._stack.addWidget(self._stock)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        layout.addWidget(self._nav)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)
