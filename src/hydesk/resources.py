"""Resolve bundled resource paths in both development and frozen builds.

In development, data files (``config/``, ``migrations/``, ``alembic.ini``)
live at the project root, two levels above the package. When packaged with
PyInstaller, they are extracted under ``sys._MEIPASS``. ``resource_root``
returns the correct base directory for either case, so the rest of the code
never needs to know whether it is frozen.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Base directory containing bundled data files.

    * Frozen: the PyInstaller extraction directory (``sys._MEIPASS``).
    * Development: the project root (two levels up from ``src/hydesk``).
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    # src/hydesk/resources.py -> project root is three parents up.
    return Path(__file__).resolve().parent.parent.parent


def resource_path(*parts: str) -> Path:
    """Return the path to a bundled resource under the resource root."""
    return resource_root().joinpath(*parts)
