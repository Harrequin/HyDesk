"""Alembic migration environment for HyDesk.

The database URL is taken from the application configuration rather than
alembic.ini, so migrations always target the same database the application
uses (and switching to PostgreSQL later needs no change here). The target
metadata is the application's SQLAlchemy Core metadata, enabling
autogenerate to compare against the real schema.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from hydesk.config import load_config
from hydesk.db.engine import create_db_engine
from hydesk.db.schema import metadata

# Alembic Config object (values from alembic.ini).
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    """Resolve the database URL from application config.

    A URL supplied on the command line (``-x db_url=...``) takes
    precedence, which is handy for running migrations against a throwaway
    or test database.
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if "db_url" in x_args:
        return x_args["db_url"]
    # A URL set programmatically on the config (e.g. by the in-process
    # migration runner) takes precedence over the default app config.
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    return load_config().database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER support
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    engine = create_db_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-safe ALTER via batch mode
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
