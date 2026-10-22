"""Tests for the 280-desk initial seed."""

from __future__ import annotations

from sqlalchemy import func, select

from hydesk.db.bootstrap import (
    FLOOR_LAYOUT,
    TOTAL_DESKS,
    desk_identifiers,
    seed_desks,
)
from hydesk.db.schema import desks


def test_total_is_280():
    assert TOTAL_DESKS == 280


def test_identifier_list_shape():
    ids = desk_identifiers()
    assert len(ids) == 280
    assert ids[0] == ("4-001", 4)
    assert ids[149] == ("4-150", 4)
    assert ids[150] == ("5-001", 5)
    assert ids[-1] == ("5-130", 5)


def test_all_identifiers_unique():
    ids = [identifier for identifier, _floor in desk_identifiers()]
    assert len(set(ids)) == len(ids)


def test_identifiers_zero_padded_three_digits():
    for identifier, floor in desk_identifiers():
        prefix, seq = identifier.split("-")
        assert prefix == str(floor)
        assert len(seq) == 3
        assert seq.isdigit()


def test_seed_inserts_all_desks(engine):
    inserted = seed_desks(engine)
    assert inserted == 280
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(desks)).scalar_one()
    assert count == 280


def test_seed_sets_default_active_status(engine):
    seed_desks(engine)
    with engine.connect() as conn:
        statuses = {
            row.status
            for row in conn.execute(select(desks.c.status)).all()
        }
    assert statuses == {"ACTIVE"}


def test_seed_counts_per_floor(engine):
    seed_desks(engine)
    with engine.connect() as conn:
        for floor, expected in FLOOR_LAYOUT.items():
            count = conn.execute(
                select(func.count()).select_from(desks).where(desks.c.floor == floor)
            ).scalar_one()
            assert count == expected


def test_seed_is_idempotent(engine):
    assert seed_desks(engine) == 280
    # Second call must insert nothing and not duplicate desks.
    assert seed_desks(engine) == 0
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(desks)).scalar_one()
    assert count == 280
