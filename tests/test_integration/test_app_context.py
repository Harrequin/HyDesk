"""Integration tests for the AppContext composition root.

These confirm the application is wired so that services share one engine,
one audit repository and one clock, and that the same context drives desks
and stock consistently.
"""

from __future__ import annotations

from hydesk.app_context import AppContext
from hydesk.models import DeskStatus


def test_context_exposes_all_services(context: AppContext):
    assert context.desks is not None
    assert context.desk_dashboard is not None
    assert context.stock is not None
    assert context.incoming is not None
    assert context.stock_dashboard is not None


def test_services_share_one_engine(context: AppContext):
    # All services must act on the same database connection source.
    assert context.desks._engine is context.engine
    assert context.stock._engine is context.engine
    assert context.incoming._engine is context.engine


def test_services_share_one_audit_repo(context: AppContext):
    assert context.desks._audit is context.audit
    assert context.stock._audit is context.audit
    assert context.incoming._audit is context.audit


def test_stock_service_and_incoming_share_stock_repo(context: AppContext):
    # The incoming receive flow and the stock service must read/write the
    # same stock repository so balances stay consistent.
    assert context.incoming._stock is context.stock._stock


def test_context_drives_desk_and_dashboard_together(context: AppContext):
    desk = context.desks.get_desk_by_identifier("4-001")
    context.desks.change_status(desk.id, DeskStatus.DOWN, "Eng")

    dashboard = context.desk_dashboard.build()
    assert dashboard.down == 1
    assert dashboard.total == 280
