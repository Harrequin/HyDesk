"""Desk dashboard: live aggregate figures.

Every figure is computed from the database on demand; nothing is cached or
denormalised, so the dashboard can never drift from the underlying data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine, func, select

from ..db.schema import desks
from ..models import Desk, DeskStatus
from ..repositories.desk_repo import _row_to_desk

# Statuses that represent a desk needing attention (anything not Active).
_ATTENTION_STATUSES = (
    DeskStatus.DOWN,
    DeskStatus.IN_REPAIR,
    DeskStatus.AWAITING_EQUIPMENT,
)


@dataclass(frozen=True)
class DeskDashboard:
    """Snapshot of desk infrastructure for the dashboard view."""

    total: int
    status_counts: dict[DeskStatus, int]
    status_by_floor: dict[int, dict[DeskStatus, int]]
    recently_updated: list[Desk] = field(default_factory=list)
    requiring_attention: list[Desk] = field(default_factory=list)

    @property
    def active(self) -> int:
        return self.status_counts.get(DeskStatus.ACTIVE, 0)

    @property
    def down(self) -> int:
        return self.status_counts.get(DeskStatus.DOWN, 0)

    @property
    def in_repair(self) -> int:
        return self.status_counts.get(DeskStatus.IN_REPAIR, 0)

    @property
    def awaiting_equipment(self) -> int:
        return self.status_counts.get(DeskStatus.AWAITING_EQUIPMENT, 0)

    @property
    def attention_total(self) -> int:
        return sum(self.status_counts.get(s, 0) for s in _ATTENTION_STATUSES)


class DeskDashboardService:
    """Builds a DeskDashboard from current database state."""

    def __init__(self, engine: Engine, *, recent_limit: int = 10) -> None:
        self._engine = engine
        self._recent_limit = recent_limit

    def build(self) -> DeskDashboard:
        with self._engine.connect() as conn:
            total = conn.execute(
                select(func.count()).select_from(desks)
            ).scalar_one()

            # Counts per status (all statuses represented, even if zero).
            status_counts = {status: 0 for status in DeskStatus}
            for row in conn.execute(
                select(desks.c.status, func.count())
                .group_by(desks.c.status)
            ).all():
                status_counts[DeskStatus(row[0])] = row[1]

            # Counts per status per floor.
            status_by_floor: dict[int, dict[DeskStatus, int]] = {}
            for row in conn.execute(
                select(desks.c.floor, desks.c.status, func.count())
                .group_by(desks.c.floor, desks.c.status)
            ).all():
                floor_map = status_by_floor.setdefault(
                    row[0], {status: 0 for status in DeskStatus}
                )
                floor_map[DeskStatus(row[1])] = row[2]

            # Recently updated desks (those with a timestamp, newest first).
            recent_rows = conn.execute(
                select(desks)
                .where(desks.c.last_updated.is_not(None))
                .order_by(desks.c.last_updated.desc())
                .limit(self._recent_limit)
            ).all()
            recently_updated = [_row_to_desk(r) for r in recent_rows]

            # Desks requiring attention (any non-Active status).
            attention_rows = conn.execute(
                select(desks)
                .where(desks.c.status != DeskStatus.ACTIVE.value)
                .order_by(desks.c.identifier)
            ).all()
            requiring_attention = [_row_to_desk(r) for r in attention_rows]

        return DeskDashboard(
            total=total,
            status_counts=status_counts,
            status_by_floor=status_by_floor,
            recently_updated=recently_updated,
            requiring_attention=requiring_attention,
        )
