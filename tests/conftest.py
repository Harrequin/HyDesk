"""Shared pytest fixtures.

Tests run against an in-memory SQLite database with foreign keys enforced,
so they are fast and fully isolated. A ``StaticPool`` keeps the single
in-memory database alive across connections within one engine.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from hydesk.db.bootstrap import create_schema, seed_desks


@pytest.fixture()
def engine() -> Engine:
    """An in-memory SQLite engine with the schema created and FKs enabled."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def seeded_engine(engine: Engine) -> Engine:
    """An engine with the 280 initial desks seeded."""
    seed_desks(engine)
    return engine


@pytest.fixture()
def fixed_clock():
    """A deterministic clock returning a fixed UTC timestamp."""
    from datetime import datetime, timezone

    moment = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    return lambda: moment


@pytest.fixture()
def context(seeded_engine, fixed_clock):
    """A fully-wired AppContext over the seeded in-memory engine.

    This exercises the real composition root, so integration tests drive
    the application exactly as the entry point wires it.
    """
    from hydesk.app_context import AppContext

    return AppContext(seeded_engine, config=None, clock=fixed_clock)
