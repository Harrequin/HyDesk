"""Domain models: pure-Python dataclasses and enums.

This package has no dependency on SQLAlchemy, SQLite or PySide6. It defines
the vocabulary the whole application shares.
"""

from .desk import Desk, DeskHistory, DeskStatus
from .stock import MovementType, StockItem, StockMovement
from .incoming import DeliveryStatus, IncomingDelivery
from .audit import AuditEntry

__all__ = [
    "Desk",
    "DeskHistory",
    "DeskStatus",
    "StockItem",
    "StockMovement",
    "MovementType",
    "IncomingDelivery",
    "DeliveryStatus",
    "AuditEntry",
]
