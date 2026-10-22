"""Tests for schema creation, database initialisation and integrity."""

from __future__ import annotations

import pytest
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError

from hydesk.db.bootstrap import (
    TOTAL_DESKS,
    create_schema,
    initialise_database,
)
from hydesk.db.schema import desk_history, desks


EXPECTED_TABLES = {
    "desks",
    "desk_history",
    "stock_items",
    "stock_movements",
    "incoming_deliveries",
    "audit_log",
}


def test_create_schema_creates_all_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def test_create_schema_is_idempotent(engine):
    # Fixture already created the schema; a second call must not raise.
    create_schema(engine)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def test_initialise_database_seeds_desks(engine):
    initialise_database(engine)
    with engine.connect() as conn:
        count = len(conn.execute(select(desks.c.id)).all())
    assert count == TOTAL_DESKS


def test_foreign_key_enforced_on_history(engine):
    # Inserting history for a non-existent desk must fail (FKs are ON).
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                insert(desk_history).values(
                    desk_id=999999,
                    engineer="eng",
                    changed_at="2026-01-01T00:00:00",
                )
            )


def test_desk_status_check_constraint(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                insert(desks).values(
                    identifier="X-001", floor=4, status="NONSENSE"
                )
            )


def test_desk_identifier_unique(engine):
    with engine.begin() as conn:
        conn.execute(insert(desks).values(identifier="4-001", floor=4, status="ACTIVE"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                insert(desks).values(identifier="4-001", floor=4, status="ACTIVE")
            )


def test_transaction_rollback_discards_partial_writes(engine):
    """A failure mid-transaction must leave nothing persisted."""
    try:
        with engine.begin() as conn:
            conn.execute(insert(desks).values(identifier="9-001", floor=9, status="ACTIVE"))
            # Force a failure after a valid insert within the same transaction.
            conn.execute(insert(desks).values(identifier="9-001", floor=9, status="ACTIVE"))
    except IntegrityError:
        pass

    with engine.connect() as conn:
        rows = conn.execute(
            select(desks).where(desks.c.identifier == "9-001")
        ).all()
    assert rows == []  # the first insert was rolled back too
