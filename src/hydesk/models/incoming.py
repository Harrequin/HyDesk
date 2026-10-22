"""Incoming delivery domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DeliveryStatus(Enum):
    """Lifecycle state of an expected delivery."""

    EXPECTED = "EXPECTED"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"

    @property
    def label(self) -> str:
        return {
            DeliveryStatus.EXPECTED: "Expected",
            DeliveryStatus.PARTIAL: "Partially Received",
            DeliveryStatus.RECEIVED: "Fully Received",
            DeliveryStatus.CANCELLED: "Cancelled",
        }[self]

    @property
    def is_open(self) -> bool:
        """True while the delivery can still contribute outstanding quantity."""
        return self in (DeliveryStatus.EXPECTED, DeliveryStatus.PARTIAL)


@dataclass
class IncomingDelivery:
    """An expected delivery of stock.

    Incoming quantities do NOT count towards available stock until received;
    receiving is handled atomically in the service layer, producing a stock
    movement and updating the item balance.
    """

    stock_item_id: int
    expected_qty: int
    date_recorded: datetime
    received_qty: int = 0
    expected_date: datetime | None = None
    actual_receipt_date: datetime | None = None
    status: DeliveryStatus = DeliveryStatus.EXPECTED
    notes: str | None = None
    id: int | None = None

    @property
    def outstanding_qty(self) -> int:
        """Quantity still expected but not yet received (never negative)."""
        if not self.status.is_open:
            return 0
        return max(0, self.expected_qty - self.received_qty)
