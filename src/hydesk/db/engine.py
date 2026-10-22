"""SQLAlchemy engine creation.

Centralises engine construction so the rest of the app never builds a
connection by hand. For SQLite we enable ``PRAGMA foreign_keys=ON`` on every
connection (SQLite leaves foreign-key enforcement off by default), which is
essential for the referential integrity the brief requires.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, create_engine, event

logger = logging.getLogger(__name__)


def create_db_engine(url: str, *, echo: bool = False) -> Engine:
    """Create a configured SQLAlchemy engine for the given URL."""
    engine = create_engine(url, echo=echo, future=True)

    if engine.dialect.name == "sqlite":
        _enable_sqlite_foreign_keys(engine)

    logger.debug("Created engine for %s", engine.url)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Ensure every SQLite connection enforces foreign keys."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
