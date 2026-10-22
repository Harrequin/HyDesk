"""Incoming delivery business logic.

Incoming quantities never count toward available stock until physically
received. Receiving a delivery is the brief's key atomic operation: in one
transaction it updates the delivery (received quantity, status, actual
receipt date), creates a RECEIVED stock movement, increments the item
balance, and writes audit entries. A failure anywhere rolls back all of it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Engine

from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    AuditEntry,
    DeliveryStatus,
    IncomingDelivery,
    MovementType,
)
from ..models import StockMovement
from ..repositories import IncomingRepository, Page, PageRequest, StockRepository
from ..repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)

_ENTITY_TYPE = "incoming_delivery"


class IncomingService:
    """Use cases for expected deliveries and their receipt."""

    def __init__(
        self,
        engine: Engine,
        incoming_repo: IncomingRepository | None = None,
        stock_repo: StockRepository | None = None,
        audit_repo: AuditRepository | None = None,
        *,
        clock=None,
    ) -> None:
        self._engine = engine
        self._incoming = incoming_repo or IncomingRepository()
        self._stock = stock_repo or StockRepository()
        self._audit = audit_repo or AuditRepository()
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ---- reads -----------------------------------------------------------

    def get(self, delivery_id: int) -> IncomingDelivery:
        with self._engine.connect() as conn:
            delivery = self._incoming.get(conn, delivery_id)
        if delivery is None:
            raise NotFoundError(f"Delivery {delivery_id} not found.")
        return delivery

    def list_deliveries(
        self, request: PageRequest, *, status: DeliveryStatus | None = None
    ) -> Page[IncomingDelivery]:
        with self._engine.connect() as conn:
            return self._incoming.list(conn, request, status=status)

    # ---- lifecycle -------------------------------------------------------

    def record_expected(
        self,
        stock_item_id: int,
        expected_qty: int,
        engineer: str,
        *,
        expected_date: datetime | None = None,
        notes: str | None = None,
    ) -> IncomingDelivery:
        """Record a new expected delivery (status EXPECTED)."""
        if not engineer or not engineer.strip():
            raise ValidationError("An engineer name is required.")
        if expected_qty <= 0:
            raise ValidationError("Expected quantity must be greater than zero.")

        now = self._now()
        engineer = engineer.strip()

        with self._engine.begin() as conn:
            item = self._stock.get(conn, stock_item_id)
            if item is None:
                raise NotFoundError(f"Stock item {stock_item_id} not found.")

            delivery_id = self._incoming.insert(
                conn,
                IncomingDelivery(
                    stock_item_id=stock_item_id,
                    expected_qty=expected_qty,
                    received_qty=0,
                    date_recorded=now,
                    expected_date=expected_date,
                    status=DeliveryStatus.EXPECTED,
                    notes=notes,
                ),
            )
            self._audit.add(
                conn,
                AuditEntry(
                    entity_type=_ENTITY_TYPE,
                    entity_id=delivery_id,
                    field_changed="created",
                    previous_value=None,
                    new_value=f"expected {expected_qty}",
                    engineer=engineer,
                    changed_at=now,
                ),
            )
            delivery = self._incoming.get(conn, delivery_id)

        logger.info(
            "Expected delivery recorded: item=%d qty=%d (id=%d)",
            stock_item_id, expected_qty, delivery_id,
        )
        return delivery

    def receive_delivery(
        self,
        delivery_id: int,
        qty: int,
        engineer: str,
        *,
        notes: str | None = None,
    ) -> IncomingDelivery:
        """Receive ``qty`` units against a delivery, atomically.

        Updates the delivery (received quantity, status, actual receipt
        date), creates a RECEIVED stock movement and increments the item
        balance, plus audit -- all in one transaction. Status becomes
        PARTIAL if more is still expected, RECEIVED once fully received.
        """
        if not engineer or not engineer.strip():
            raise ValidationError("An engineer name is required.")
        if qty <= 0:
            raise ValidationError("Received quantity must be greater than zero.")

        now = self._now()
        engineer = engineer.strip()

        with self._engine.begin() as conn:
            delivery = self._incoming.get(conn, delivery_id)
            if delivery is None:
                raise NotFoundError(f"Delivery {delivery_id} not found.")
            if not delivery.status.is_open:
                raise ConflictError(
                    f"Delivery {delivery_id} is {delivery.status.label} and "
                    "cannot receive more stock."
                )

            new_received = delivery.received_qty + qty
            if new_received > delivery.expected_qty:
                raise ValidationError(
                    f"Receiving {qty} would exceed the expected quantity "
                    f"({delivery.received_qty}/{delivery.expected_qty} already received)."
                )

            new_status = (
                DeliveryStatus.RECEIVED
                if new_received == delivery.expected_qty
                else DeliveryStatus.PARTIAL
            )

            # 1. Update the delivery.
            self._incoming.update_fields(
                conn,
                delivery_id,
                received_qty=new_received,
                status=new_status,
                actual_receipt_date=now,
            )

            # 2 & 3. Movement + item balance increment, backed by audit.
            item = self._stock.get(conn, delivery.stock_item_id)
            self._apply_receipt_movement(
                conn,
                item_id=item.id,
                previous_qty=item.quantity,
                qty=qty,
                engineer=engineer,
                when=now,
                delivery_id=delivery_id,
                notes=notes,
            )

            # 4. Audit the delivery status transition.
            self._audit.add(
                conn,
                AuditEntry(
                    entity_type=_ENTITY_TYPE,
                    entity_id=delivery_id,
                    field_changed="received_qty",
                    previous_value=str(delivery.received_qty),
                    new_value=str(new_received),
                    engineer=engineer,
                    changed_at=now,
                ),
            )

            updated = self._incoming.get(conn, delivery_id)

        logger.info(
            "Received %d against delivery %d -> %s",
            qty, delivery_id, new_status.label,
        )
        return updated

    def cancel_delivery(
        self, delivery_id: int, engineer: str, *, reason: str | None = None
    ) -> IncomingDelivery:
        """Cancel an open delivery. Already-received stock is unaffected."""
        if not engineer or not engineer.strip():
            raise ValidationError("An engineer name is required.")
        now = self._now()
        engineer = engineer.strip()

        with self._engine.begin() as conn:
            delivery = self._incoming.get(conn, delivery_id)
            if delivery is None:
                raise NotFoundError(f"Delivery {delivery_id} not found.")
            if not delivery.status.is_open:
                raise ConflictError(
                    f"Delivery {delivery_id} is {delivery.status.label} and "
                    "cannot be cancelled."
                )

            self._incoming.update_fields(conn, delivery_id, status=DeliveryStatus.CANCELLED)
            self._audit.add(
                conn,
                AuditEntry(
                    entity_type=_ENTITY_TYPE,
                    entity_id=delivery_id,
                    field_changed="status",
                    previous_value=delivery.status.value,
                    new_value=DeliveryStatus.CANCELLED.value,
                    engineer=engineer,
                    changed_at=now,
                ),
            )
            updated = self._incoming.get(conn, delivery_id)

        logger.info("Delivery %d cancelled by %s", delivery_id, engineer)
        return updated

    # ---- internals -------------------------------------------------------

    def _apply_receipt_movement(
        self,
        conn,
        *,
        item_id: int,
        previous_qty: int,
        qty: int,
        engineer: str,
        when: datetime,
        delivery_id: int,
        notes: str | None,
    ) -> None:
        """Increment the item balance and record a RECEIVED movement + audit."""
        resulting = previous_qty + qty
        self._stock.update_item_fields(
            conn, item_id, quantity=resulting, last_updated=when
        )
        self._stock.insert_movement(
            conn,
            StockMovement(
                stock_item_id=item_id,
                movement_type=MovementType.RECEIVED,
                quantity=qty,
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
                entity_type="stock_item",
                entity_id=item_id,
                field_changed="quantity",
                previous_value=str(previous_qty),
                new_value=str(resulting),
                engineer=engineer,
                changed_at=when,
            ),
        )
