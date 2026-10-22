"""Desk domain model and related enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DeskStatus(Enum):
    """Operational status of a desk.

    The value is the canonical string persisted in the database. ``label``
    is the human-readable form and ``colour`` is the accessible status
    colour (text is always shown alongside the colour in the UI).
    """

    ACTIVE = "ACTIVE"
    DOWN = "DOWN"
    IN_REPAIR = "IN_REPAIR"
    AWAITING_EQUIPMENT = "AWAITING_EQUIPMENT"

    @property
    def label(self) -> str:
        return {
            DeskStatus.ACTIVE: "Active",
            DeskStatus.DOWN: "Down",
            DeskStatus.IN_REPAIR: "In Repair",
            DeskStatus.AWAITING_EQUIPMENT: "Awaiting Equipment",
        }[self]

    @property
    def colour(self) -> str:
        """Hex colour for status indicators (accessible contrast on light bg)."""
        return {
            DeskStatus.ACTIVE: "#1B8A3A",            # green
            DeskStatus.DOWN: "#C62828",              # red
            DeskStatus.IN_REPAIR: "#D98200",         # amber / orange
            DeskStatus.AWAITING_EQUIPMENT: "#1565C0",  # blue
        }[self]


@dataclass
class Desk:
    """A single desk record."""

    identifier: str
    floor: int
    status: DeskStatus = DeskStatus.ACTIVE
    last_engineer: str | None = None
    last_updated: datetime | None = None
    notes: str | None = None
    halo_ticket: str | None = None
    id: int | None = None


@dataclass
class DeskHistory:
    """An immutable record of a change to a desk.

    History entries are appended, never overwritten.
    """

    desk_id: int
    engineer: str
    changed_at: datetime
    previous_status: DeskStatus | None = None
    new_status: DeskStatus | None = None
    halo_ticket: str | None = None
    notes: str | None = None
    id: int | None = None
