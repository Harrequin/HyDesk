"""Stock management business logic.

Central rules enforced here:

* A stock item's quantity is **never silently overwritten**. Every change
  goes through ``record_movement``, which captures the previous and
  resulting balance and writes an immutable movement row.
* Quantity can never go negative (enforced here and by a DB CHECK).
* Item creation, each movement and each edit run inside one transaction
  together with an audit entry.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Engine

from ..errors import NotFoundError, ValidationError
from ..models import AuditEntry, MovementType, StockItem, StockMovement
from ..repositories import Page, PageRequest, StockQuery, StockRepository
from ..repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)

_ENTITY_TYPE = "stock_item"


class StockService:
    """Use cases for stock items and their movements."""

    def __init__(
        self,
        engine: Engine,
        stock_repo: StockRepository | None = None,
        audit_repo: AuditRepository | None = None,
        *,
        clock=None,
    ) -> None:
        self._engine = engine
        self._stock = stock_repo or StockRepository()
        self._audit = audit_repo or AuditRepository()
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ---- reads -----------------------------------------------------------

    def get_item(self, item_id: int) -> StockItem:
        with self._engine.connect() as conn:
            item = self._stock.get(conn, item_id)
        if item is None:
            raise NotFoundError(f"Stock item {item_id} not found.")
        return item

    def search_items(self, query: StockQuery, request: PageRequest) -> Page[StockItem]:
        with self._engine.connect() as conn:
            return self._stock.search(conn, query, request)

    def movements_for(self, item_id: int) -> list[StockMovement]:
        with self._engine.connect() as conn:
            return self._stock.movements_for(conn, item_id)

    def reconcile(self, item_id: int) -> bool:
        """Return True if the stored balance equals the sum of movements."""
        with self._engine.connect() as conn:
            item = self._stock.get(conn, item_id)
            if item is None:
                raise NotFoundError(f"Stock item {item_id} not found.")
            movement_total = self._stock.movement_sum(conn, item_id)
        return item.quantity == movement_total

    # ---- item lifecycle --------------------------------------------------

    def create_item(
        self,
        category: str,
        name: str,
        engineer: str,
        *,
        location: str | None = None,
        initial_quantity: int = 0,
        low_stock_threshold: int = 0,
    ) -> StockItem:
        """Create a stock item.

        If ``initial_quantity`` is positive, an opening ADJUSTMENT movement
        is recorded so the balance is always backed by the movement ledger.
        """
        self._require(category, "category")
        self._require(name, "name")
        self._require(engineer, "engineer")
        if initial_quantity < 0:
            raise ValidationError("Initial quantity cannot be negative.")
        if low_stock_threshold < 0:
            raise ValidationError("Low-stock threshold cannot be negative.")

        now = self._now()
        engineer = engineer.strip()

        with self._engine.begin() as conn:
            item_id = self._stock.insert_item(
                conn,
                StockItem(
                    category=category.strip(),
                    name=name.strip(),
                    location=location.strip() if location else None,
                    quantity=0,
                    low_stock_threshold=low_stock_threshold,
                    last_updated=now,
                ),
            )
            self._audit.add(
                conn,
                AuditEntry(
                    entity_type=_ENTITY_TYPE,
                    entity_id=item_id,
                    field_changed="created",
                    previous_value=None,
                    new_value=name.strip(),
                    engineer=engineer,
                    changed_at=now,
                ),
            )
            if initial_quantity > 0:
                self._apply_movement(
                    conn,
                    item_id=item_id,
                    previous_qty=0,
                    delta=initial_quantity,
                    movement_type=MovementType.ADJUSTMENT,
                    engineer=engineer,
                    when=now,
                    notes="Opening balance",
                )
            item = self._stock.get(conn, item_id)

        logger.info("Stock item created: %s (id=%d)", item.name, item.id)
        return item

    def edit_item(
        self,
        item_id: int,
        engineer: str,
        *,
        name: str | None = None,
        category: str | None = None,
        location: str | None = None,
        update_location: bool = False,
        low_stock_threshold: int | None = None,
    ) -> StockItem:
        """Edit item details (not quantity -- quantity changes via movements)."""
        self._require(engineer, "engineer")
        engineer = engineer.strip()
        now = self._now()

        with self._engine.begin() as conn:
            item = self._stock.get(conn, item_id)
            if item is None:
                raise NotFoundError(f"Stock item {item_id} not found.")

            changes: dict = {}
            audit: list[AuditEntry] = []

            if name is not None and name.strip() != item.name:
                changes["name"] = name.strip()
                audit.append(self._audit_entry(item_id, engineer, now, "name", item.name, name.strip()))
            if category is not None and category.strip() != item.category:
                changes["category"] = category.strip()
                audit.append(self._audit_entry(item_id, engineer, now, "category", item.category, category.strip()))
            if update_location:
                new_loc = location.strip() if location else None
                if new_loc != item.location:
                    changes["location"] = new_loc
                    audit.append(self._audit_entry(item_id, engineer, now, "location", item.location, new_loc))
            if low_stock_threshold is not None and low_stock_threshold != item.low_stock_threshold:
                if low_stock_threshold < 0:
                    raise ValidationError("Low-stock threshold cannot be negative.")
                changes["low_stock_threshold"] = low_stock_threshold
                audit.append(
                    self._audit_entry(
                        item_id, engineer, now, "low_stock_threshold",
                        item.low_stock_threshold, low_stock_threshold,
                    )
                )

            if not changes:
                raise ValidationError("No changes were supplied for the stock item.")

            changes["last_updated"] = now
            self._stock.update_item_fields(conn, item_id, **changes)
            for entry in audit:
                self._audit.add(conn, entry)
            updated = self._stock.get(conn, item_id)

        logger.info("Stock item %d edited by %s", item_id, engineer)
        return updated

    # ---- movements -------------------------------------------------------

    def record_movement(
        self,
        item_id: int,
        movement_type: MovementType,
        delta: int,
        engineer: str,
        *,
        notes: str | None = None,
        delivery_id: int | None = None,
    ) -> StockItem:
        """Apply a signed quantity change as an atomic, audited movement.

        ``delta`` is the signed change (positive to add, negative to
        remove). The resulting balance must not be negative. The item
        balance, the movement row and an audit entry are written together.
        """
        self._require(engineer, "engineer")
        engineer = engineer.strip()
        if delta == 0:
            raise ValidationError("A stock movement must change the quantity.")

        now = self._now()
        with self._engine.begin() as conn:
            item = self._stock.get(conn, item_id)
            if item is None:
                raise NotFoundError(f"Stock item {item_id} not found.")
            updated = self._apply_movement(
                conn,
                item_id=item_id,
                previous_qty=item.quantity,
                delta=delta,
                movement_type=movement_type,
                engineer=engineer,
                when=now,
                notes=notes,
                delivery_id=delivery_id,
            )
        return updated

    def receive(self, item_id: int, qty: int, engineer: str, **kw) -> StockItem:
        return self.record_movement(item_id, MovementType.RECEIVED, abs(qty), engineer, **kw)

    def issue(self, item_id: int, qty: int, engineer: str, **kw) -> StockItem:
        return self.record_movement(item_id, MovementType.ISSUED, -abs(qty), engineer, **kw)

    def adjust(self, item_id: int, delta: int, engineer: str, **kw) -> StockItem:
        return self.record_movement(item_id, MovementType.ADJUSTMENT, delta, engineer, **kw)

    def correct(self, item_id: int, delta: int, engineer: str, **kw) -> StockItem:
        return self.record_movement(item_id, MovementType.CORRECTION, delta, engineer, **kw)

    # ---- internals -------------------------------------------------------

    def _apply_movement(
        self,
        conn,
        *,
        item_id: int,
        previous_qty: int,
        delta: int,
        movement_type: MovementType,
        engineer: str,
        when: datetime,
        notes: str | None = None,
        delivery_id: int | None = None,
    ) -> StockItem:
        """Write the balance update, movement row and audit entry.

        Must be called inside an open transaction (``conn`` from
        ``engine.begin()``). Shared by create/receive/issue/adjust/correct
        and by the incoming receive flow.
        """
        resulting = previous_qty + delta
        if resulting < 0:
            raise ValidationError(
                f"Movement would reduce quantity below zero "
                f"(have {previous_qty}, change {delta})."
            )

        self._stock.update_item_fields(
            conn, item_id, quantity=resulting, last_updated=when
        )
        self._stock.insert_movement(
            conn,
            StockMovement(
                stock_item_id=item_id,
                movement_type=movement_type,
                quantity=delta,
                previous_qty=previous_qty,
                resulting_qty=resulting,
                engineer=engineer,
                occurred_at=when,
                delivery_id=delivery_id,
                notes=notes,
            ),
        )
        self._audit.add(
            conn,
            AuditEntry(
                entity_type=_ENTITY_TYPE,
                entity_id=item_id,
                field_changed="quantity",
                previous_value=str(previous_qty),
                new_value=str(resulting),
                engineer=engineer,
                changed_at=when,
            ),
        )
        return self._stock.get(conn, item_id)

    @staticmethod
    def _require(value: str | None, field: str) -> None:
        if not value or not value.strip():
            raise ValidationError(f"A {field} is required.")

    @staticmethod
    def _audit_entry(item_id, engineer, when, field, previous, new) -> AuditEntry:
        return AuditEntry(
            entity_type=_ENTITY_TYPE,
            entity_id=item_id,
            field_changed=field,
            previous_value=None if previous is None else str(previous),
            new_value=None if new is None else str(new),
            engineer=engineer,
            changed_at=when,
        )
