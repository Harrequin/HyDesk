"""Stock dashboard: live aggregate figures.

Every figure is computed from the database on demand. Low-stock uses each
item's own ``low_stock_threshold`` (configurable per item) rather than a
global constant. Incoming figures count only open deliveries, and incoming
quantities are never mixed into the available-stock total.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine, func, select

from ..db.schema import incoming_deliveries, stock_items
from ..models import DeliveryStatus, StockItem
from ..repositories.stock_repo import _row_to_item

_OPEN_STATUSES = (DeliveryStatus.EXPECTED.value, DeliveryStatus.PARTIAL.value)


@dataclass(frozen=True)
class StockDashboard:
    """Snapshot of stock state for the dashboard view."""

    total_items: int
    total_quantity: int
    low_stock: list[StockItem] = field(default_factory=list)
    out_of_stock: list[StockItem] = field(default_factory=list)
    incoming_deliveries: int = 0
    outstanding_incoming_qty: int = 0
    recently_updated: list[StockItem] = field(default_factory=list)
    category_breakdown: dict[str, int] = field(default_factory=dict)
    location_breakdown: dict[str, int] = field(default_factory=dict)

    @property
    def low_stock_count(self) -> int:
        return len(self.low_stock)

    @property
    def out_of_stock_count(self) -> int:
        return len(self.out_of_stock)


class StockDashboardService:
    """Builds a StockDashboard from current database state."""

    def __init__(self, engine: Engine, *, recent_limit: int = 10) -> None:
        self._engine = engine
        self._recent_limit = recent_limit

    def build(self) -> StockDashboard:
        with self._engine.connect() as conn:
            total_items = conn.execute(
                select(func.count()).select_from(stock_items)
            ).scalar_one()

            total_quantity = int(
                conn.execute(
                    select(func.coalesce(func.sum(stock_items.c.quantity), 0))
                ).scalar_one()
            )

            # Out of stock: quantity == 0.
            out_rows = conn.execute(
                select(stock_items)
                .where(stock_items.c.quantity == 0)
                .order_by(stock_items.c.name)
            ).all()
            out_of_stock = [_row_to_item(r) for r in out_rows]

            # Low stock: quantity > 0 and quantity <= per-item threshold.
            low_rows = conn.execute(
                select(stock_items)
                .where(stock_items.c.quantity > 0)
                .where(stock_items.c.quantity <= stock_items.c.low_stock_threshold)
                .order_by(stock_items.c.name)
            ).all()
            low_stock = [_row_to_item(r) for r in low_rows]

            # Open incoming deliveries and outstanding quantity.
            incoming_count = conn.execute(
                select(func.count())
                .select_from(incoming_deliveries)
                .where(incoming_deliveries.c.status.in_(_OPEN_STATUSES))
            ).scalar_one()

            outstanding = int(
                conn.execute(
                    select(
                        func.coalesce(
                            func.sum(
                                incoming_deliveries.c.expected_qty
                                - incoming_deliveries.c.received_qty
                            ),
                            0,
                        )
                    ).where(incoming_deliveries.c.status.in_(_OPEN_STATUSES))
                ).scalar_one()
            )

            # Recently updated items.
            recent_rows = conn.execute(
                select(stock_items)
                .where(stock_items.c.last_updated.is_not(None))
                .order_by(stock_items.c.last_updated.desc())
                .limit(self._recent_limit)
            ).all()
            recently_updated = [_row_to_item(r) for r in recent_rows]

            # Breakdowns: available quantity by category and by location.
            category_breakdown = {
                row[0]: int(row[1])
                for row in conn.execute(
                    select(stock_items.c.category, func.sum(stock_items.c.quantity))
                    .group_by(stock_items.c.category)
                ).all()
            }
            location_breakdown = {
                (row[0] if row[0] is not None else "(unassigned)"): int(row[1])
                for row in conn.execute(
                    select(stock_items.c.location, func.sum(stock_items.c.quantity))
                    .group_by(stock_items.c.location)
                ).all()
            }

        return StockDashboard(
            total_items=total_items,
            total_quantity=total_quantity,
            low_stock=low_stock,
            out_of_stock=out_of_stock,
            incoming_deliveries=incoming_count,
            outstanding_incoming_qty=outstanding,
            recently_updated=recently_updated,
            category_breakdown=category_breakdown,
            location_breakdown=location_breakdown,
        )
