"""Cross-service data integrity and transaction regression tests.

These exercise whole operations end to end through the composition root and
assert that related records stay consistent, that failures roll back
completely, and that referential integrity holds.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from hydesk.app_context import AppContext
from hydesk.db.schema import stock_movements
from hydesk.errors import ConflictError, ValidationError
from hydesk.models import DeliveryStatus, DeskStatus


# ---- receive flow consistency -------------------------------------------

def test_receive_keeps_delivery_stock_movement_consistent(context: AppContext):
    item = context.stock.create_item("Peripherals", "Dock", "Eng")
    delivery = context.incoming.record_expected(item.id, 30, "Eng")

    context.incoming.receive_delivery(delivery.id, 12, "Eng")

    # Delivery reflects partial receipt.
    d = context.incoming.get(delivery.id)
    assert d.status is DeliveryStatus.PARTIAL
    assert d.received_qty == 12

    # Stock balance matches, and the movement is linked to the delivery.
    assert context.stock.get_item(item.id).quantity == 12
    movements = context.stock.movements_for(item.id)
    assert len(movements) == 1
    assert movements[0].delivery_id == delivery.id

    # Ledger reconciles with the stored balance.
    assert context.stock.reconcile(item.id) is True


def test_over_receipt_rolls_back_entirely(context: AppContext):
    """A rejected receipt must leave delivery, stock and ledger untouched."""
    item = context.stock.create_item("Peripherals", "Hub", "Eng")
    delivery = context.incoming.record_expected(item.id, 10, "Eng")

    with pytest.raises(ValidationError):
        context.incoming.receive_delivery(delivery.id, 999, "Eng")

    # Nothing changed anywhere.
    assert context.incoming.get(delivery.id).status is DeliveryStatus.EXPECTED
    assert context.incoming.get(delivery.id).received_qty == 0
    assert context.stock.get_item(item.id).quantity == 0
    with context.engine.connect() as conn:
        movement_count = conn.execute(
            select(func.count()).select_from(stock_movements)
            .where(stock_movements.c.stock_item_id == item.id)
        ).scalar_one()
    assert movement_count == 0


def test_issue_below_zero_rolls_back(context: AppContext):
    item = context.stock.create_item("Cables", "USB", "Eng", initial_quantity=3)
    before = context.stock.get_item(item.id).quantity
    before_movements = len(context.stock.movements_for(item.id))

    with pytest.raises(ValidationError):
        context.stock.issue(item.id, 10, "Eng")

    assert context.stock.get_item(item.id).quantity == before
    assert len(context.stock.movements_for(item.id)) == before_movements


def test_desk_update_rollback_leaves_no_history(context: AppContext):
    desk = context.desks.get_desk_by_identifier("5-001")
    with pytest.raises(ValidationError):
        context.desks.update_desk(
            desk.id, "Eng", status=DeskStatus.DOWN,
            halo_ticket="bad", update_halo=True,
        )
    assert context.desks.get_desk(desk.id).status is DeskStatus.ACTIVE
    assert context.desks.view_history(desk.id) == []


# ---- availability semantics ---------------------------------------------

def test_expected_stock_excluded_until_received(context: AppContext):
    item = context.stock.create_item("Cables", "Fibre", "Eng", initial_quantity=5)
    context.incoming.record_expected(item.id, 100, "Eng")

    # Dashboard available total must not include the 100 expected units.
    dashboard = context.stock_dashboard.build()
    assert dashboard.total_quantity == 5
    assert dashboard.outstanding_incoming_qty == 100


def test_cancelled_delivery_not_counted_as_outstanding(context: AppContext):
    item = context.stock.create_item("Cables", "Coax", "Eng")
    delivery = context.incoming.record_expected(item.id, 40, "Eng")
    context.incoming.cancel_delivery(delivery.id, "Eng")

    dashboard = context.stock_dashboard.build()
    assert dashboard.incoming_deliveries == 0
    assert dashboard.outstanding_incoming_qty == 0


def test_receiving_closed_delivery_is_conflict(context: AppContext):
    item = context.stock.create_item("Cables", "Ribbon", "Eng")
    delivery = context.incoming.record_expected(item.id, 5, "Eng")
    context.incoming.receive_delivery(delivery.id, 5, "Eng")
    with pytest.raises(ConflictError):
        context.incoming.receive_delivery(delivery.id, 1, "Eng")
