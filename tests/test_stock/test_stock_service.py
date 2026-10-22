"""Tests for StockService: items, movements, reconciliation, integrity."""

from __future__ import annotations

import pytest

from hydesk.errors import NotFoundError, ValidationError
from hydesk.models import MovementType
from hydesk.repositories import PageRequest, StockQuery
from hydesk.repositories.stock_repo import StockSort
from hydesk.services.stock_service import StockService


@pytest.fixture()
def service(engine, fixed_clock) -> StockService:
    return StockService(engine, clock=fixed_clock)


# ---- item creation -------------------------------------------------------

def test_create_item(service):
    item = service.create_item("Cables", "HDMI 2m", "Eng", location="Store A")
    assert item.id is not None
    assert item.category == "Cables"
    assert item.name == "HDMI 2m"
    assert item.location == "Store A"
    assert item.quantity == 0


def test_create_item_with_opening_balance_records_movement(service):
    item = service.create_item("Cables", "USB-C", "Eng", initial_quantity=20)
    assert item.quantity == 20
    movements = service.movements_for(item.id)
    assert len(movements) == 1
    assert movements[0].movement_type is MovementType.ADJUSTMENT
    assert movements[0].previous_qty == 0
    assert movements[0].resulting_qty == 20


def test_create_item_requires_fields(service):
    with pytest.raises(ValidationError):
        service.create_item("", "Name", "Eng")
    with pytest.raises(ValidationError):
        service.create_item("Cat", "", "Eng")
    with pytest.raises(ValidationError):
        service.create_item("Cat", "Name", "  ")


def test_create_item_rejects_negative_quantity(service):
    with pytest.raises(ValidationError):
        service.create_item("Cat", "Name", "Eng", initial_quantity=-5)


# ---- movements -----------------------------------------------------------

def test_receive_increases_quantity_and_records_movement(service):
    item = service.create_item("Peripherals", "Mouse", "Eng")
    updated = service.receive(item.id, 10, "Eng")
    assert updated.quantity == 10
    m = service.movements_for(item.id)[0]
    assert m.movement_type is MovementType.RECEIVED
    assert m.previous_qty == 0
    assert m.resulting_qty == 10
    assert m.quantity == 10


def test_issue_decreases_quantity(service):
    item = service.create_item("Peripherals", "Keyboard", "Eng", initial_quantity=5)
    updated = service.issue(item.id, 3, "Eng")
    assert updated.quantity == 2
    m = service.movements_for(item.id)[0]
    assert m.movement_type is MovementType.ISSUED
    assert m.quantity == -3
    assert m.previous_qty == 5
    assert m.resulting_qty == 2


def test_issue_below_zero_rejected(service):
    item = service.create_item("Peripherals", "Dock", "Eng", initial_quantity=2)
    with pytest.raises(ValidationError):
        service.issue(item.id, 5, "Eng")
    # Balance unchanged, no issue movement recorded.
    assert service.get_item(item.id).quantity == 2
    assert all(m.movement_type is not MovementType.ISSUED
               for m in service.movements_for(item.id))


def test_adjustment_and_correction(service):
    item = service.create_item("Misc", "Adapters", "Eng", initial_quantity=10)
    service.adjust(item.id, 5, "Eng", notes="found extra")
    service.correct(item.id, -2, "Eng", notes="miscount")
    assert service.get_item(item.id).quantity == 13


def test_zero_delta_rejected(service):
    item = service.create_item("Misc", "Thing", "Eng")
    with pytest.raises(ValidationError):
        service.record_movement(item.id, MovementType.ADJUSTMENT, 0, "Eng")


def test_movement_requires_engineer(service):
    item = service.create_item("Misc", "Thing2", "Eng")
    with pytest.raises(ValidationError):
        service.receive(item.id, 5, "")


def test_movement_missing_item(service):
    with pytest.raises(NotFoundError):
        service.receive(999999, 5, "Eng")


# ---- reconciliation ------------------------------------------------------

def test_reconciliation_holds_after_many_movements(service):
    item = service.create_item("Cables", "Cat6", "Eng", initial_quantity=100)
    service.issue(item.id, 10, "Eng")
    service.receive(item.id, 25, "Eng")
    service.issue(item.id, 5, "Eng")
    service.adjust(item.id, -3, "Eng")
    assert service.get_item(item.id).quantity == 107
    assert service.reconcile(item.id) is True


# ---- editing -------------------------------------------------------------

def test_edit_item_fields(service):
    item = service.create_item("Cables", "Patch", "Eng")
    updated = service.edit_item(
        item.id, "Eng", name="Patch Lead", low_stock_threshold=5
    )
    assert updated.name == "Patch Lead"
    assert updated.low_stock_threshold == 5


def test_edit_requires_a_change(service):
    item = service.create_item("Cables", "Fibre", "Eng")
    with pytest.raises(ValidationError):
        service.edit_item(item.id, "Eng")


# ---- search / filter / sort ---------------------------------------------

def test_search_filter_sort(service):
    service.create_item("Cables", "HDMI", "Eng", location="A", initial_quantity=3)
    service.create_item("Cables", "DisplayPort", "Eng", location="B", initial_quantity=9)
    service.create_item("Power", "PSU", "Eng", location="A", initial_quantity=1)

    by_cat = service.search_items(StockQuery(category="Cables"), PageRequest(page_size=0))
    assert by_cat.total == 2

    by_loc = service.search_items(StockQuery(location="A"), PageRequest(page_size=0))
    assert by_loc.total == 2

    by_name = service.search_items(StockQuery(search="HDMI"), PageRequest(page_size=0))
    assert by_name.total == 1

    by_qty = service.search_items(
        StockQuery(sort=StockSort.QUANTITY, descending=True), PageRequest(page_size=1)
    )
    assert by_qty.items[0].name == "DisplayPort"
