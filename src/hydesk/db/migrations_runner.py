"""Programmatic Alembic migration runner.

Lets the application bring its database up to the latest schema on startup
by running Alembic migrations in-process, rather than requiring the
operator to run the ``alembic`` CLI by hand. Tests continue to build the
schema directly from the Core metadata for speed; real deployments use
this migration path so the schema is always versioned.
"""

from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config as AlembicConfig

from ..resources import resource_path

logger = logging.getLogger(__name__)


def _alembic_config(database_url: str) -> AlembicConfig:
    # Resolve the Alembic config and migrations tree for both the dev tree
    # and a frozen PyInstaller bundle.
    cfg = AlembicConfig(str(resource_path("alembic.ini")))
    cfg.set_main_option("script_location", str(resource_path("migrations")))
    # Pass the resolved URL via the same -x mechanism env.py understands.
    cfg.cmd_opts = None
    cfg.attributes["db_url"] = database_url
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_to_head(database_url: str) -> None:
    """Upgrade the database at ``database_url`` to the latest revision."""
    logger.info("Running database migrations to head")
    cfg = _alembic_config(database_url)
    command.upgrade(cfg, "head")
    logger.info("Database migrations complete")
