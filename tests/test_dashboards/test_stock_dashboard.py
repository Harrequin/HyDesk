"""Tests for the stock dashboard aggregate calculations."""

from __future__ import annotations

import pytest

from hydesk.services.incoming_service import IncomingService
from hydesk.services.stock_dashboard_service import StockDashboardService
from hydesk.services.stock_service import StockService


@pytest.fixture()
def built(engine, fixed_clock):
    stock = StockService(engine, clock=fixed_clock)
    incoming = IncomingService(engine, clock=fixed_clock)

    # Known data:
    #  - Mouse: qty 100, threshold 10 (healthy), location A, Peripherals
    #  - Keyboard: qty 5, threshold 10 (LOW), location A, Peripherals
    #  - Dock: qty 0, threshold 2 (OUT), location B, Peripherals
    #  - HDMI: qty 50, threshold 0 (healthy), location B, Cables
    mouse = stock.create_item("Peripherals", "Mouse", "Eng", location="A",
                              initial_quantity=100, low_stock_threshold=10)
    stock.create_item("Peripherals", "Keyboard", "Eng", location="A",
                      initial_quantity=5, low_stock_threshold=10)
    stock.create_item("Peripherals", "Dock", "Eng", location="B",
                      initial_quantity=0, low_stock_threshold=2)
    stock.create_item("Cables", "HDMI", "Eng", location="B",
                      initial_quantity=50, low_stock_threshold=0)

    # Incoming: 30 expected for Mouse, 10 already received (outstanding 20).
    delivery = incoming.record_expected(mouse.id, 30, "Eng")
    incoming.receive_delivery(delivery.id, 10, "Eng")

    return StockDashboardService(engine).build(), mouse


def test_total_distinct_items(built):
    dashboard, _ = built
    assert dashboard.total_items == 4


def test_total_available_quantity(built):
    dashboard, _ = built
    # 100 + 10 (received) + 5 + 0 + 50 = 165
    assert dashboard.total_quantity == 165


def test_low_stock_items(built):
    dashboard, _ = built
    names = {i.name for i in dashboard.low_stock}
    assert names == {"Keyboard"}  # qty 5 <= threshold 10, and > 0


def test_out_of_stock_items(built):
    dashboard, _ = built
    names = {i.name for i in dashboard.out_of_stock}
    assert names == {"Dock"}


def test_incoming_figures(built):
    dashboard, _ = built
    assert dashboard.incoming_deliveries == 1   # still PARTIAL => open
    assert dashboard.outstanding_incoming_qty == 20  # 30 expected - 10 received


def test_category_breakdown(built):
    dashboard, _ = built
    # Peripherals: 110 (mouse incl. received) + 5 + 0 = 115; Cables: 50
    assert dashboard.category_breakdown["Peripherals"] == 115
    assert dashboard.category_breakdown["Cables"] == 50


def test_location_breakdown(built):
    dashboard, _ = built
    # A: 110 + 5 = 115; B: 0 + 50 = 50
    assert dashboard.location_breakdown["A"] == 115
    assert dashboard.location_breakdown["B"] == 50


def test_recently_updated_populated(built):
    dashboard, _ = built
    assert len(dashboard.recently_updated) == 4


def test_empty_dashboard(engine):
    dashboard = StockDashboardService(engine).build()
    assert dashboard.total_items == 0
    assert dashboard.total_quantity == 0
    assert dashboard.low_stock == []
    assert dashboard.out_of_stock == []
    assert dashboard.incoming_deliveries == 0
    assert dashboard.outstanding_incoming_qty == 0
