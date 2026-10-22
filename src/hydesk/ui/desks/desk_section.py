"""Desks section: an internal tab set of Dashboard + Listing.

Owns the dashboard and listing views and connects the dashboard's
"open filtered" signal so clicking a status figure switches to the listing
filtered to that status.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout

from ...app_context import AppContext
from .desk_dashboard import DeskDashboardView
from .desk_list import DeskListView


class DesksSection(QWidget):
    def __init__(self, context: AppContext, session, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._dashboard = DeskDashboardView(context.desk_dashboard)
        self._list = DeskListView(context.desks, session, context.config)

        self._tabs.addTab(self._dashboard, "Dashboard")
        self._tabs.addTab(self._list, "Listing")
        layout.addWidget(self._tabs)

        self._dashboard.open_filtered.connect(self._open_filtered)
        # Refresh the dashboard whenever the user returns to it.
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _open_filtered(self, status) -> None:
        self._list.apply_status_filter(status)
        self._tabs.setCurrentWidget(self._list)

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is self._dashboard:
            self._dashboard.refresh()
        elif self._tabs.widget(index) is self._list:
            self._list.refresh()
