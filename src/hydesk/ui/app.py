"""GUI application launcher.

Builds the QApplication, applies the theme and brand font, and shows the
main window for a given AppContext.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..app_context import AppContext
from .main_window import MainWindow
from .theme import apply_brand_font, stylesheet


def run(context: AppContext) -> int:
    """Launch the GUI event loop. Returns the process exit code."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("HyDesk")
    apply_brand_font(app)
    app.setStyleSheet(stylesheet())

    window = MainWindow(context)
    window.show()
    return app.exec()
