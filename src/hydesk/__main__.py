"""Application entry point.

Wires the foundation together in the correct order: configuration, then
logging, then the database engine, then schema/seed initialisation. The
GUI is introduced in a later phase; for now this verifies the foundation
boots cleanly and the database is ready.

Run with:  python -m hydesk
"""

from __future__ import annotations

import logging
import sys

from .app_context import AppContext
from .config import load_config
from .db.bootstrap import TOTAL_DESKS, seed_desks
from .db.engine import create_db_engine
from .db.migrations_runner import upgrade_to_head
from .logging_setup import configure_logging


def bootstrap() -> AppContext:
    """Load config, configure logging, initialise the DB and wire services.

    Returns a fully-constructed ``AppContext`` so the GUI layer can reuse
    the same engine and services.
    """
    config = load_config()
    configure_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("Starting HyDesk")
    logger.info("Database: %s", config.database_path)

    # Bring the schema up to the latest revision via Alembic, then seed.
    upgrade_to_head(config.database_url)

    engine = create_db_engine(config.database_url)
    seed_desks(engine)
    logger.info("Database initialised (expected %d desks)", TOTAL_DESKS)

    return AppContext(engine, config)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    no_gui = "--no-gui" in argv

    try:
        context = bootstrap()
    except Exception:  # noqa: BLE001 - top-level guard logs then exits
        logging.getLogger(__name__).exception("Fatal error during startup")
        return 1

    if no_gui:
        # Headless startup check: initialise everything but don't open the UI.
        print("HyDesk initialised successfully (no GUI).")
        print(f"Database location: {context.config.database_path}")
        return 0

    from .ui.app import run
    return run(context)


if __name__ == "__main__":
    sys.exit(main())
