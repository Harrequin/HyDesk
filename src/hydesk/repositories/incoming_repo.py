"""Incoming delivery repository: SQL for expected deliveries.

Takes a ``Connection`` so the receive operation (delivery update + stock
movement + item balance update + audit) runs as one transaction in the
service layer.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Connection, func, select

from ..db.schema import incoming_deliveries
from ..models import DeliveryStatus, IncomingDelivery
from .base import Page, PageRequest


def _row_to_delivery(row) -> IncomingDelivery:  # noqa: ANN001
    return IncomingDelivery(
        id=row.id,
        stock_item_id=row.stock_item_id,
        expected_qty=row.expected_qty,
        received_qty=row.received_qty,
        date_recorded=datetime.fromisoformat(row.date_recorded),
        expected_date=datetime.fromisoformat(row.expected_date) if row.expected_date else None,
        actual_receipt_date=(
            datetime.fromisoformat(row.actual_receipt_date)
            if row.actual_receipt_date
            else None
        ),
        status=DeliveryStatus(row.status),
        notes=row.notes,
    )


class IncomingRepository:
    """Persistence for incoming deliveries."""

    def get(self, conn: Connection, delivery_id: int) -> IncomingDelivery | None:
        row = conn.execute(
            select(incoming_deliveries).where(incoming_deliveries.c.id == delivery_id)
        ).first()
        return _row_to_delivery(row) if row else None

    def insert(self, conn: Connection, delivery: IncomingDelivery) -> int:
        result = conn.execute(
            incoming_deliveries.insert().values(
                stock_item_id=delivery.stock_item_id,
                expected_qty=delivery.expected_qty,
                received_qty=delivery.received_qty,
                date_recorded=delivery.date_recorded.isoformat(),
                expected_date=(
                    delivery.expected_date.isoformat() if delivery.expected_date else None
                ),
                actual_receipt_date=(
                    delivery.actual_receipt_date.isoformat()
                    if delivery.actual_receipt_date
                    else None
                ),
                status=delivery.status.value,
                notes=delivery.notes,
            )
        )
        return int(result.inserted_primary_key[0])

    def update_fields(self, conn: Connection, delivery_id: int, **fields) -> None:
        if "status" in fields and isinstance(fields["status"], DeliveryStatus):
            fields["status"] = fields["status"].value
        for key in ("actual_receipt_date", "expected_date"):
            if key in fields and isinstance(fields[key], datetime):
                fields[key] = fields[key].isoformat()
        conn.execute(
            incoming_deliveries.update()
            .where(incoming_deliveries.c.id == delivery_id)
            .values(**fields)
        )

    def list(
        self,
        conn: Connection,
        request: PageRequest,
        *,
        status: DeliveryStatus | None = None,
    ) -> Page[IncomingDelivery]:
        count_stmt = select(func.count()).select_from(incoming_deliveries)
        data_stmt = select(incoming_deliveries)
        if status is not None:
            count_stmt = count_stmt.where(incoming_deliveries.c.status == status.value)
            data_stmt = data_stmt.where(incoming_deliveries.c.status == status.value)

        total = conn.execute(count_stmt).scalar_one()
        data_stmt = data_stmt.order_by(incoming_deliveries.c.date_recorded.desc())
        if request.paginated:
            data_stmt = data_stmt.limit(request.limit).offset(request.offset)

        rows = conn.execute(data_stmt).all()
        items = [_row_to_delivery(r) for r in rows]
        return Page(items=items, total=total, page=request.page, page_size=request.page_size)

    def open_deliveries(self, conn: Connection) -> list[IncomingDelivery]:
        """All deliveries still open (EXPECTED or PARTIAL)."""
        rows = conn.execute(
            select(incoming_deliveries).where(
                incoming_deliveries.c.status.in_(
                    [DeliveryStatus.EXPECTED.value, DeliveryStatus.PARTIAL.value]
                )
            )
        ).all()
        return [_row_to_delivery(r) for r in rows]
