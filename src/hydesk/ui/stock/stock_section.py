"""Stock section: Dashboard + Items + Incoming tabs."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ...app_context import AppContext
from .incoming_view import IncomingView
from .stock_dashboard import StockDashboardView
from .stock_list import StockListView


class StockSection(QWidget):
    def __init__(self, context: AppContext, session, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._dashboard = StockDashboardView(context.stock_dashboard)
        self._items = StockListView(context.stock, session, context.config)
        self._incoming = IncomingView(
            context.incoming, context.stock, session, context.config
        )

        self._tabs.addTab(self._dashboard, "Dashboard")
        self._tabs.addTab(self._items, "Items")
        self._tabs.addTab(self._incoming, "Incoming")
        layout.addWidget(self._tabs)

        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget is self._dashboard:
            self._dashboard.refresh()
        elif widget is self._items:
            self._items.refresh()
        elif widget is self._incoming:
            self._incoming.refresh()
