"""Stock item and stock movement domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MovementType(Enum):
    """Type of a recorded stock quantity change."""

    RECEIVED = "RECEIVED"
    ISSUED = "ISSUED"
    ADJUSTMENT = "ADJUSTMENT"
    CORRECTION = "CORRECTION"

    @property
    def label(self) -> str:
        return {
            MovementType.RECEIVED: "Stock Received",
            MovementType.ISSUED: "Stock Issued",
            MovementType.ADJUSTMENT: "Stock Adjustment",
            MovementType.CORRECTION: "Stock Correction",
        }[self]


@dataclass
class StockItem:
    """A distinct stock item.

    SKU is deliberately omitted for the MVP; items are identified by their
    internal id plus name/category. A ``low_stock_threshold`` is stored per
    item so low-stock reporting is configurable rather than global.
    """

    category: str
    name: str
    location: str | None = None
    quantity: int = 0
    low_stock_threshold: int = 0
    last_updated: datetime | None = None
    id: int | None = None


@dataclass
class StockMovement:
    """An immutable record of a change to a stock item's quantity.

    ``quantity`` is the signed delta; ``previous_qty`` and ``resulting_qty``
    capture the balance either side of the movement so the ledger can be
    reconciled against the stored balance.
    """

    stock_item_id: int
    movement_type: MovementType
    quantity: int
    previous_qty: int
    resulting_qty: int
    engineer: str
    occurred_at: datetime
    delivery_id: int | None = None
    notes: str | None = None
    id: int | None = None
