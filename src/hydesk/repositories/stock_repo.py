"""Stock repository: SQL for stock items and their movements.

The only layer that emits stock SQL. Methods take a ``Connection`` so the
service layer can compose item updates, movement inserts and audit writes
inside a single transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import Connection, func, select

from ..db.schema import stock_items, stock_movements
from ..models import MovementType, StockItem, StockMovement
from .base import Page, PageRequest


class StockSort(Enum):
    """Supported sort columns for stock item listings."""

    NAME = "name"
    CATEGORY = "category"
    QUANTITY = "quantity"
    LAST_UPDATED = "last_updated"


@dataclass(frozen=True)
class StockQuery:
    """Search/filter/sort specification for stock item listings."""

    search: str | None = None          # matched against item name
    category: str | None = None        # exact filter
    location: str | None = None        # exact filter
    sort: StockSort = StockSort.NAME
    descending: bool = False


def _row_to_item(row) -> StockItem:  # noqa: ANN001
    return StockItem(
        id=row.id,
        category=row.category,
        name=row.name,
        location=row.location,
        quantity=row.quantity,
        low_stock_threshold=row.low_stock_threshold,
        last_updated=datetime.fromisoformat(row.last_updated) if row.last_updated else None,
    )


def _row_to_movement(row) -> StockMovement:  # noqa: ANN001
    return StockMovement(
        id=row.id,
        stock_item_id=row.stock_item_id,
        movement_type=MovementType(row.movement_type),
        quantity=row.quantity,
        previous_qty=row.previous_qty,
        resulting_qty=row.resulting_qty,
        engineer=row.engineer,
        occurred_at=datetime.fromisoformat(row.occurred_at),
        delivery_id=row.delivery_id,
        notes=row.notes,
    )


class StockRepository:
    """Persistence for stock items and stock movements."""

    # ---- items -----------------------------------------------------------

    def count(self, conn: Connection) -> int:
        return conn.execute(select(func.count()).select_from(stock_items)).scalar_one()

    def get(self, conn: Connection, item_id: int) -> StockItem | None:
        row = conn.execute(
            select(stock_items).where(stock_items.c.id == item_id)
        ).first()
        return _row_to_item(row) if row else None

    def insert_item(self, conn: Connection, item: StockItem) -> int:
        """Insert a stock item and return its new id."""
        result = conn.execute(
            stock_items.insert().values(
                category=item.category,
                name=item.name,
                location=item.location,
                quantity=item.quantity,
                low_stock_threshold=item.low_stock_threshold,
                last_updated=item.last_updated.isoformat() if item.last_updated else None,
            )
        )
        return int(result.inserted_primary_key[0])

    def update_item_fields(self, conn: Connection, item_id: int, **fields) -> None:
        if "last_updated" in fields and isinstance(fields["last_updated"], datetime):
            fields["last_updated"] = fields["last_updated"].isoformat()
        conn.execute(
            stock_items.update().where(stock_items.c.id == item_id).values(**fields)
        )

    def search(
        self, conn: Connection, query: StockQuery, request: PageRequest
    ) -> Page[StockItem]:
        conditions = self._conditions(query)

        count_stmt = select(func.count()).select_from(stock_items)
        data_stmt = select(stock_items)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            data_stmt = data_stmt.where(condition)

        total = conn.execute(count_stmt).scalar_one()
        data_stmt = data_stmt.order_by(*self._order_by(query))
        if request.paginated:
            data_stmt = data_stmt.limit(request.limit).offset(request.offset)

        rows = conn.execute(data_stmt).all()
        items = [_row_to_item(r) for r in rows]
        return Page(items=items, total=total, page=request.page, page_size=request.page_size)

    @staticmethod
    def _conditions(query: StockQuery) -> list:
        conditions = []
        if query.search:
            conditions.append(stock_items.c.name.like(f"%{query.search.strip()}%"))
        if query.category is not None:
            conditions.append(stock_items.c.category == query.category)
        if query.location is not None:
            conditions.append(stock_items.c.location == query.location)
        return conditions

    @staticmethod
    def _order_by(query: StockQuery) -> list:
        column_map = {
            StockSort.NAME: stock_items.c.name,
            StockSort.CATEGORY: stock_items.c.category,
            StockSort.QUANTITY: stock_items.c.quantity,
            StockSort.LAST_UPDATED: stock_items.c.last_updated,
        }
        primary = column_map[query.sort]
        primary = primary.desc() if query.descending else primary.asc()
        # Name is a stable, human-meaningful tiebreaker for non-unique sorts.
        if query.sort is StockSort.NAME:
            return [primary]
        return [primary, stock_items.c.name.asc()]

    # ---- movements -------------------------------------------------------

    def insert_movement(self, conn: Connection, movement: StockMovement) -> None:
        conn.execute(
            stock_movements.insert().values(
                stock_item_id=movement.stock_item_id,
                movement_type=movement.movement_type.value,
                quantity=movement.quantity,
                previous_qty=movement.previous_qty,
                resulting_qty=movement.resulting_qty,
                engineer=movement.engineer,
                occurred_at=movement.occurred_at.isoformat(),
                delivery_id=movement.delivery_id,
                notes=movement.notes,
            )
        )

    def movements_for(self, conn: Connection, item_id: int) -> list[StockMovement]:
        rows = conn.execute(
            select(stock_movements)
            .where(stock_movements.c.stock_item_id == item_id)
            .order_by(stock_movements.c.occurred_at.desc(), stock_movements.c.id.desc())
        ).all()
        return [_row_to_movement(r) for r in rows]

    def movement_sum(self, conn: Connection, item_id: int) -> int:
        """Sum of signed movement quantities for an item (for reconciliation)."""
        total = conn.execute(
            select(func.coalesce(func.sum(stock_movements.c.quantity), 0))
            .where(stock_movements.c.stock_item_id == item_id)
        ).scalar_one()
        return int(total)
