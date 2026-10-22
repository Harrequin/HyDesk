"""Cross-cutting audit trail integrity tests.

Auditability is a core requirement: every significant change must be
traceable (what changed, previous/new value, engineer, when, record id),
history must never be overwritten, and normal operations must not silently
delete historical information. These tests assert that across both domains.
"""

from __future__ import annotations

from hydesk.app_context import AppContext
from hydesk.models import DeskStatus, MovementType


def _audit(context, entity_type, entity_id):
    with context.engine.connect() as conn:
        return context.audit.for_entity(conn, entity_type, entity_id)


# ---- desks ---------------------------------------------------------------

def test_desk_status_change_is_audited(context: AppContext):
    desk = context.desks.get_desk_by_identifier("4-001")
    context.desks.change_status(desk.id, DeskStatus.DOWN, "Alice")

    entries = _audit(context, "desk", desk.id)
    assert len(entries) == 1
    e = entries[0]
    assert e.field_changed == "status"
    assert e.previous_value == "ACTIVE"
    assert e.new_value == "DOWN"
    assert e.engineer == "Alice"
    assert e.changed_at is not None
    assert e.entity_id == desk.id


def test_multi_field_desk_update_audits_each_field(context: AppContext):
    desk = context.desks.get_desk_by_identifier("4-002")
    context.desks.update_desk(
        desk.id,
        "Bob",
        status=DeskStatus.IN_REPAIR,
        notes="screen flicker",
        update_notes=True,
        halo_ticket="1234567",
        update_halo=True,
    )
    fields = {e.field_changed for e in _audit(context, "desk", desk.id)}
    assert fields == {"status", "notes", "halo_ticket"}


def test_desk_history_is_never_overwritten(context: AppContext):
    desk = context.desks.get_desk_by_identifier("4-003")
    context.desks.change_status(desk.id, DeskStatus.DOWN, "Eng")
    context.desks.change_status(desk.id, DeskStatus.IN_REPAIR, "Eng")
    context.desks.change_status(desk.id, DeskStatus.ACTIVE, "Eng")

    history = context.desks.view_history(desk.id)
    assert len(history) == 3
    # Audit trail likewise accumulates, never replaced.
    assert len(_audit(context, "desk", desk.id)) == 3


# ---- stock ---------------------------------------------------------------

def test_stock_movement_is_audited(context: AppContext):
    item = context.stock.create_item("Cables", "HDMI", "Eng", initial_quantity=0)
    context.stock.receive(item.id, 10, "Carol")

    entries = _audit(context, "stock_item", item.id)
    # One 'created' entry plus one 'quantity' entry for the receive.
    quantity_entries = [e for e in entries if e.field_changed == "quantity"]
    assert len(quantity_entries) == 1
    assert quantity_entries[0].previous_value == "0"
    assert quantity_entries[0].new_value == "10"
    assert quantity_entries[0].engineer == "Carol"


def test_stock_history_accumulates(context: AppContext):
    item = context.stock.create_item("Cables", "Cat6", "Eng", initial_quantity=100)
    context.stock.issue(item.id, 10, "Eng")
    context.stock.receive(item.id, 5, "Eng")

    movements = context.stock.movements_for(item.id)
    # opening adjustment + issue + receive
    assert len(movements) == 3
    types = {m.movement_type for m in movements}
    assert MovementType.ADJUSTMENT in types
    assert MovementType.ISSUED in types
    assert MovementType.RECEIVED in types


def test_incoming_receipt_audited_on_both_entities(context: AppContext):
    item = context.stock.create_item("Peripherals", "Monitor", "Eng")
    delivery = context.incoming.record_expected(item.id, 20, "Eng")
    context.incoming.receive_delivery(delivery.id, 20, "Dave")

    # Delivery audited (created + received_qty) and stock item audited (quantity).
    delivery_fields = {e.field_changed for e in _audit(context, "incoming_delivery", delivery.id)}
    assert "created" in delivery_fields
    assert "received_qty" in delivery_fields

    item_quantity_entries = [
        e for e in _audit(context, "stock_item", item.id) if e.field_changed == "quantity"
    ]
    assert len(item_quantity_entries) == 1
    assert item_quantity_entries[0].new_value == "20"
