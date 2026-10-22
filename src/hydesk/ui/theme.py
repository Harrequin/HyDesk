"""Centralised theming: colours, spacing, fonts and the app stylesheet.

Everything visual that is shared lives here so the look can be adjusted in
one place. In particular the brand font is applied through
``apply_brand_font``: when a font file is dropped into ``ui/assets`` later,
only this module changes -- no view needs touching.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# --- palette --------------------------------------------------------------
# Neutral, professional surface colours. Status colours are defined on the
# domain enums (DeskStatus.colour) and reused by the status badge so there
# is a single source of truth for them.
COLOR_BG = "#F5F6F8"
COLOR_SURFACE = "#FFFFFF"
COLOR_BORDER = "#D5D9DF"
COLOR_TEXT = "#1F2328"
COLOR_TEXT_MUTED = "#5A6472"
COLOR_NAV_BG = "#1F2730"
COLOR_NAV_TEXT = "#E8EBEF"
COLOR_NAV_SELECTED = "#324050"
COLOR_ACCENT = "#1565C0"

# --- spacing scale --------------------------------------------------------
SPACE_S = 6
SPACE_M = 12
SPACE_L = 20

# Fallback font family used until a brand font is supplied.
DEFAULT_FONT_FAMILY = "Segoe UI"
BASE_FONT_POINT_SIZE = 10


def apply_brand_font(app: QApplication) -> str:
    """Apply the application font.

    If a font file exists in ``ui/assets`` (``*.ttf``/``*.otf``), it is
    registered and used; otherwise the default system family is used. This
    is the single hook for the brand font to be added post-MVP.

    Returns the resolved font family name (for logging/diagnostics).
    """
    family = DEFAULT_FONT_FAMILY
    if ASSETS_DIR.is_dir():
        font_files = sorted(
            [p for p in ASSETS_DIR.iterdir() if p.suffix.lower() in (".ttf", ".otf")]
        )
        for font_file in font_files:
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id == -1:
                logger.warning("Failed to load font: %s", font_file.name)
                continue
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
                logger.info("Loaded brand font: %s", family)
                break

    app.setFont(QFont(family, BASE_FONT_POINT_SIZE))
    return family


def stylesheet() -> str:
    """Return the application-wide Qt stylesheet."""
    return f"""
    QMainWindow, QWidget {{
        background: {COLOR_BG};
        color: {COLOR_TEXT};
    }}
    QFrame#Card {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
    }}
    QLabel#CardTitle {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
    }}
    QLabel#CardValue {{
        font-size: 26px;
        font-weight: 600;
    }}
    QLabel#PageTitle {{
        font-size: 20px;
        font-weight: 600;
    }}
    /* Left navigation */
    QListWidget#NavList {{
        background: {COLOR_NAV_BG};
        color: {COLOR_NAV_TEXT};
        border: none;
        outline: none;
        padding-top: {SPACE_M}px;
    }}
    QListWidget#NavList::item {{
        padding: {SPACE_M}px {SPACE_L}px;
    }}
    QListWidget#NavList::item:selected {{
        background: {COLOR_NAV_SELECTED};
        border-left: 3px solid {COLOR_ACCENT};
    }}
    QPushButton {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: {SPACE_S}px {SPACE_M}px;
    }}
    QPushButton:hover {{
        border-color: {COLOR_ACCENT};
    }}
    QPushButton#Primary {{
        background: {COLOR_ACCENT};
        color: #FFFFFF;
        border: none;
    }}
    QTableView {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        gridline-color: {COLOR_BORDER};
        selection-background-color: #D6E4F5;
        selection-color: {COLOR_TEXT};
    }}
    QHeaderView::section {{
        background: {COLOR_BG};
        padding: {SPACE_S}px;
        border: none;
        border-bottom: 1px solid {COLOR_BORDER};
        font-weight: 600;
    }}
    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: {SPACE_S}px;
    }}
    """
