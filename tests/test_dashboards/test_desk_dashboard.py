"""Tests for the desk dashboard aggregate calculations."""

from __future__ import annotations

import pytest

from hydesk.models import DeskStatus
from hydesk.services.dashboard_service import DeskDashboardService
from hydesk.services.desk_service import DeskService


@pytest.fixture()
def dashboard_service(seeded_engine, fixed_clock):
    # Apply a known spread of statuses.
    svc = DeskService(seeded_engine, clock=fixed_clock)
    svc.change_status(svc.get_desk_by_identifier("4-001").id, DeskStatus.DOWN, "Eng")
    svc.change_status(svc.get_desk_by_identifier("4-002").id, DeskStatus.DOWN, "Eng")
    svc.change_status(svc.get_desk_by_identifier("4-003").id, DeskStatus.IN_REPAIR, "Eng")
    svc.change_status(
        svc.get_desk_by_identifier("5-001").id, DeskStatus.AWAITING_EQUIPMENT, "Eng"
    )
    return DeskDashboardService(seeded_engine)


def test_total_is_280(dashboard_service):
    assert dashboard_service.build().total == 280


def test_status_totals(dashboard_service):
    d = dashboard_service.build()
    assert d.down == 2
    assert d.in_repair == 1
    assert d.awaiting_equipment == 1
    assert d.active == 280 - 4


def test_status_counts_sum_to_total(dashboard_service):
    d = dashboard_service.build()
    assert sum(d.status_counts.values()) == d.total


def test_attention_total(dashboard_service):
    d = dashboard_service.build()
    assert d.attention_total == 4  # 2 down + 1 repair + 1 awaiting


def test_status_by_floor(dashboard_service):
    d = dashboard_service.build()
    # Floor 4: 2 down, 1 in repair, rest active (150 total).
    assert d.status_by_floor[4][DeskStatus.DOWN] == 2
    assert d.status_by_floor[4][DeskStatus.IN_REPAIR] == 1
    assert d.status_by_floor[4][DeskStatus.ACTIVE] == 150 - 3
    # Floor 5: 1 awaiting equipment, rest active (130 total).
    assert d.status_by_floor[5][DeskStatus.AWAITING_EQUIPMENT] == 1
    assert d.status_by_floor[5][DeskStatus.ACTIVE] == 130 - 1


def test_requiring_attention_lists_non_active(dashboard_service):
    d = dashboard_service.build()
    identifiers = {desk.identifier for desk in d.requiring_attention}
    assert identifiers == {"4-001", "4-002", "4-003", "5-001"}
    assert all(desk.status is not DeskStatus.ACTIVE for desk in d.requiring_attention)


def test_recently_updated_populated(dashboard_service):
    d = dashboard_service.build()
    # Four desks were updated; all should appear (limit default 10).
    assert len(d.recently_updated) == 4
    assert all(desk.last_updated is not None for desk in d.recently_updated)


def test_dashboard_on_fresh_seed_all_active(seeded_engine):
    d = DeskDashboardService(seeded_engine).build()
    assert d.active == 280
    assert d.attention_total == 0
    assert d.recently_updated == []
    assert d.requiring_attention == []
