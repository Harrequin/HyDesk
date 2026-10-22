"""Tests for the desk repository and pagination primitives."""

from __future__ import annotations

from datetime import datetime

from hydesk.models import DeskHistory, DeskStatus
from hydesk.repositories import PageRequest
from hydesk.repositories.desk_repo import DeskRepository

repo = DeskRepository()


def test_count_matches_seed(seeded_engine):
    with seeded_engine.connect() as conn:
        assert repo.count(conn) == 280


def test_get_by_identifier(seeded_engine):
    with seeded_engine.connect() as conn:
        desk = repo.get_by_identifier(conn, "5-001")
    assert desk is not None
    assert desk.floor == 5
    assert desk.status is DeskStatus.ACTIVE


def test_get_missing_returns_none(seeded_engine):
    with seeded_engine.connect() as conn:
        assert repo.get(conn, 999999) is None


def test_paginated_listing(seeded_engine):
    with seeded_engine.connect() as conn:
        page = repo.list(conn, PageRequest(page=1, page_size=50))
    assert page.total == 280
    assert len(page.items) == 50
    assert page.total_pages == 6
    assert page.has_next is True
    assert page.has_previous is False
    # Ordered by identifier -> first desk is 4-001.
    assert page.items[0].identifier == "4-001"


def test_last_page(seeded_engine):
    with seeded_engine.connect() as conn:
        page = repo.list(conn, PageRequest(page=6, page_size=50))
    assert len(page.items) == 30  # 280 - 5*50
    assert page.has_next is False
    assert page.has_previous is True


def test_unpaginated_returns_all(seeded_engine):
    with seeded_engine.connect() as conn:
        page = repo.list(conn, PageRequest(page=1, page_size=0))
    assert len(page.items) == 280
    assert page.total_pages == 1


def test_update_fields_and_history_roundtrip(seeded_engine):
    with seeded_engine.begin() as conn:
        desk = repo.get_by_identifier(conn, "4-010")
        now = datetime(2026, 1, 2, 9, 30, 0)
        repo.update_fields(
            conn,
            desk.id,
            status=DeskStatus.DOWN,
            last_engineer="A. Engineer",
            last_updated=now,
            halo_ticket="1234567",
        )
        repo.add_history(
            conn,
            DeskHistory(
                desk_id=desk.id,
                previous_status=DeskStatus.ACTIVE,
                new_status=DeskStatus.DOWN,
                engineer="A. Engineer",
                changed_at=now,
                halo_ticket="1234567",
                notes="Monitor failure",
            ),
        )

    with seeded_engine.connect() as conn:
        updated = repo.get_by_identifier(conn, "4-010")
        history = repo.history_for(conn, updated.id)

    assert updated.status is DeskStatus.DOWN
    assert updated.last_engineer == "A. Engineer"
    assert updated.halo_ticket == "1234567"
    assert updated.last_updated == datetime(2026, 1, 2, 9, 30, 0)
    assert len(history) == 1
    assert history[0].new_status is DeskStatus.DOWN
    assert history[0].notes == "Monitor failure"
