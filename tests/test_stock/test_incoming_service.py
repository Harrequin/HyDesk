"""Tests for IncomingService: expected deliveries, atomic receipt, cancel."""

from __future__ import annotations

import pytest

from hydesk.errors import ConflictError, NotFoundError, ValidationError
from hydesk.models import DeliveryStatus, MovementType
from hydesk.services.incoming_service import IncomingService
from hydesk.services.stock_service import StockService


@pytest.fixture()
def services(engine, fixed_clock):
    stock = StockService(engine, clock=fixed_clock)
    incoming = IncomingService(engine, clock=fixed_clock)
    return stock, incoming


@pytest.fixture()
def item(services):
    stock, _ = services
    return stock.create_item("Peripherals", "Monitor", "Eng")


def test_record_expected_delivery(services, item):
    _, incoming = services
    delivery = incoming.record_expected(item.id, 50, "Eng")
    assert delivery.status is DeliveryStatus.EXPECTED
    assert delivery.expected_qty == 50
    assert delivery.received_qty == 0


def test_expected_delivery_does_not_affect_available_stock(services, item):
    stock, incoming = services
    incoming.record_expected(item.id, 50, "Eng")
    # Available stock is unchanged until physically received.
    assert stock.get_item(item.id).quantity == 0


def test_record_expected_requires_positive_qty(services, item):
    _, incoming = services
    with pytest.raises(ValidationError):
        incoming.record_expected(item.id, 0, "Eng")


def test_record_expected_missing_item(services):
    _, incoming = services
    with pytest.raises(NotFoundError):
        incoming.record_expected(999999, 10, "Eng")


def test_full_receipt_atomic(services, item):
    stock, incoming = services
    delivery = incoming.record_expected(item.id, 20, "Eng")

    updated = incoming.receive_delivery(delivery.id, 20, "Eng")
    assert updated.status is DeliveryStatus.RECEIVED
    assert updated.received_qty == 20
    assert updated.actual_receipt_date is not None

    # Stock balance incremented and a RECEIVED movement exists.
    assert stock.get_item(item.id).quantity == 20
    movements = stock.movements_for(item.id)
    assert len(movements) == 1
    assert movements[0].movement_type is MovementType.RECEIVED
    assert movements[0].delivery_id == delivery.id


def test_partial_then_full_receipt(services, item):
    stock, incoming = services
    delivery = incoming.record_expected(item.id, 30, "Eng")

    after_first = incoming.receive_delivery(delivery.id, 10, "Eng")
    assert after_first.status is DeliveryStatus.PARTIAL
    assert after_first.received_qty == 10
    assert stock.get_item(item.id).quantity == 10

    after_second = incoming.receive_delivery(delivery.id, 20, "Eng")
    assert after_second.status is DeliveryStatus.RECEIVED
    assert after_second.received_qty == 30
    assert stock.get_item(item.id).quantity == 30

    # Two separate RECEIVED movements recorded.
    assert len(stock.movements_for(item.id)) == 2


def test_over_receipt_rejected(services, item):
    _, incoming = services
    delivery = incoming.record_expected(item.id, 10, "Eng")
    with pytest.raises(ValidationError):
        incoming.receive_delivery(delivery.id, 15, "Eng")


def test_cannot_receive_against_completed_delivery(services, item):
    _, incoming = services
    delivery = incoming.record_expected(item.id, 5, "Eng")
    incoming.receive_delivery(delivery.id, 5, "Eng")
    with pytest.raises(ConflictError):
        incoming.receive_delivery(delivery.id, 1, "Eng")


def test_receive_reconciles_with_stock_ledger(services, item):
    stock, incoming = services
    delivery = incoming.record_expected(item.id, 40, "Eng")
    incoming.receive_delivery(delivery.id, 15, "Eng")
    incoming.receive_delivery(delivery.id, 25, "Eng")
    assert stock.reconcile(item.id) is True


def test_cancel_delivery(services, item):
    stock, incoming = services
    delivery = incoming.record_expected(item.id, 10, "Eng")
    cancelled = incoming.cancel_delivery(delivery.id, "Eng", reason="supplier issue")
    assert cancelled.status is DeliveryStatus.CANCELLED
    # Cancelling an un-received delivery leaves stock untouched.
    assert stock.get_item(item.id).quantity == 0


def test_cannot_cancel_completed_delivery(services, item):
    _, incoming = services
    delivery = incoming.record_expected(item.id, 5, "Eng")
    incoming.receive_delivery(delivery.id, 5, "Eng")
    with pytest.raises(ConflictError):
        incoming.cancel_delivery(delivery.id, "Eng")


def test_partial_receipt_then_cancel_keeps_received_stock(services, item):
    stock, incoming = services
    delivery = incoming.record_expected(item.id, 20, "Eng")
    incoming.receive_delivery(delivery.id, 8, "Eng")
    incoming.cancel_delivery(delivery.id, "Eng")
    # The 8 already received remain in stock; the rest is cancelled.
    assert stock.get_item(item.id).quantity == 8
    assert incoming.get(delivery.id).status is DeliveryStatus.CANCELLED
