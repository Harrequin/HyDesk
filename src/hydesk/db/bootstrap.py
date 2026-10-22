"""Database bootstrap: schema creation and initial desk seeding.

``create_schema`` builds the tables from the Core metadata (idempotent).
``seed_desks`` populates the 280 initial Park Street desks exactly once.
``initialise_database`` runs both and is what the application calls on
first launch. Tests use the individual functions against an in-memory DB.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, func, select

from .schema import desks, metadata

logger = logging.getLogger(__name__)

# Park Street desk layout, per the specification.
FLOOR_LAYOUT = {
    4: 150,  # 4-001 .. 4-150
    5: 130,  # 5-001 .. 5-130
}
TOTAL_DESKS = sum(FLOOR_LAYOUT.values())


def create_schema(engine: Engine) -> None:
    """Create all tables if they do not already exist."""
    metadata.create_all(engine)
    logger.info("Schema ensured (%d tables)", len(metadata.tables))


def desk_identifiers() -> list[tuple[str, int]]:
    """Return the full ordered list of (identifier, floor) for all desks.

    Identifiers are consistently formatted as ``<floor>-<NNN>`` with a
    three-digit, zero-padded sequence number.
    """
    rows: list[tuple[str, int]] = []
    for floor, quantity in FLOOR_LAYOUT.items():
        for seq in range(1, quantity + 1):
            rows.append((f"{floor}-{seq:03d}", floor))
    return rows


def seed_desks(engine: Engine) -> int:
    """Insert the initial desk records if the table is empty.

    Returns the number of desks inserted (0 if seeding was skipped because
    desks already exist, making this safe to call on every startup).
    """
    with engine.begin() as conn:
        existing = conn.execute(select(func.count()).select_from(desks)).scalar_one()
        if existing:
            logger.info("Desks already present (%d); skipping seed", existing)
            return 0

        payload = [
            {"identifier": identifier, "floor": floor, "status": "ACTIVE"}
            for identifier, floor in desk_identifiers()
        ]
        conn.execute(desks.insert(), payload)
        logger.info("Seeded %d desks", len(payload))
        return len(payload)


def initialise_database(engine: Engine) -> None:
    """Create the schema and seed initial data. Safe to call repeatedly."""
    create_schema(engine)
    seed_desks(engine)
