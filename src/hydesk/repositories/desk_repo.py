"""Desk repository: the only place desk SQL lives.

Phase 2 provides the core CRUD and a paginated listing so the data-access
layer can be exercised end-to-end. Rich search/filter/sort is added in
Phase 3 on top of these foundations.

All methods accept a SQLAlchemy ``Connection`` rather than opening their
own, so the service layer can compose several repository calls inside a
single transaction (unit of work).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import Connection, func, or_, select

from ..models import Desk, DeskHistory, DeskStatus
from ..db.schema import desk_history, desks
from .base import Page, PageRequest


class DeskSort(Enum):
    """Supported sort columns for desk listings."""

    IDENTIFIER = "identifier"
    FLOOR = "floor"
    STATUS = "status"
    ENGINEER = "engineer"
    LAST_UPDATED = "last_updated"


@dataclass(frozen=True)
class DeskQuery:
    """A combined search/filter/sort specification for desk listings.

    ``search`` is a free-text term matched across identifier, engineer,
    Halo ticket and notes. ``floor`` and ``status`` are optional exact
    filters. Sorting defaults to identifier ascending. All fields are
    optional so the same method serves the full listing and any
    filtered/searched view.
    """

    search: str | None = None
    floor: int | None = None
    status: DeskStatus | None = None
    sort: DeskSort = DeskSort.IDENTIFIER
    descending: bool = False


def _row_to_desk(row) -> Desk:  # noqa: ANN001 - SQLAlchemy Row
    return Desk(
        id=row.id,
        identifier=row.identifier,
        floor=row.floor,
        status=DeskStatus(row.status),
        last_engineer=row.last_engineer,
        last_updated=datetime.fromisoformat(row.last_updated) if row.last_updated else None,
        notes=row.notes,
        halo_ticket=row.halo_ticket,
    )


def _row_to_history(row) -> DeskHistory:  # noqa: ANN001
    return DeskHistory(
        id=row.id,
        desk_id=row.desk_id,
        previous_status=DeskStatus(row.previous_status) if row.previous_status else None,
        new_status=DeskStatus(row.new_status) if row.new_status else None,
        engineer=row.engineer,
        changed_at=datetime.fromisoformat(row.changed_at),
        halo_ticket=row.halo_ticket,
        notes=row.notes,
    )


class DeskRepository:
    """Persistence operations for desks and their history."""

    def count(self, conn: Connection) -> int:
        return conn.execute(select(func.count()).select_from(desks)).scalar_one()

    def get(self, conn: Connection, desk_id: int) -> Desk | None:
        row = conn.execute(select(desks).where(desks.c.id == desk_id)).first()
        return _row_to_desk(row) if row else None

    def get_by_identifier(self, conn: Connection, identifier: str) -> Desk | None:
        row = conn.execute(
            select(desks).where(desks.c.identifier == identifier)
        ).first()
        return _row_to_desk(row) if row else None

    def list(self, conn: Connection, request: PageRequest) -> Page[Desk]:
        """Return a page of desks ordered by identifier."""
        total = self.count(conn)

        stmt = select(desks).order_by(desks.c.identifier)
        if request.paginated:
            stmt = stmt.limit(request.limit).offset(request.offset)

        rows = conn.execute(stmt).all()
        items = [_row_to_desk(r) for r in rows]
        return Page(items=items, total=total, page=request.page, page_size=request.page_size)

    def search(
        self, conn: Connection, query: DeskQuery, request: PageRequest
    ) -> Page[Desk]:
        """Return a filtered, sorted, paginated page of desks.

        The filtered total is computed from the same WHERE clause as the
        page itself, so pagination metadata stays consistent when filters
        change (the user never sees a page count that doesn't match the
        rows they can actually reach).
        """
        conditions = self._conditions(query)

        count_stmt = select(func.count()).select_from(desks)
        data_stmt = select(desks)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            data_stmt = data_stmt.where(condition)

        total = conn.execute(count_stmt).scalar_one()

        data_stmt = data_stmt.order_by(*self._order_by(query))
        if request.paginated:
            data_stmt = data_stmt.limit(request.limit).offset(request.offset)

        rows = conn.execute(data_stmt).all()
        items = [_row_to_desk(r) for r in rows]
        return Page(items=items, total=total, page=request.page, page_size=request.page_size)

    @staticmethod
    def _conditions(query: DeskQuery) -> list:
        """Build the list of SQL WHERE conditions for a DeskQuery."""
        conditions = []
        if query.search:
            term = f"%{query.search.strip()}%"
            conditions.append(
                or_(
                    desks.c.identifier.like(term),
                    desks.c.last_engineer.like(term),
                    desks.c.halo_ticket.like(term),
                    desks.c.notes.like(term),
                )
            )
        if query.floor is not None:
            conditions.append(desks.c.floor == query.floor)
        if query.status is not None:
            conditions.append(desks.c.status == query.status.value)
        return conditions

    @staticmethod
    def _order_by(query: DeskQuery) -> list:
        """Build the ORDER BY clause for a DeskQuery.

        Identifier is appended as a stable tiebreaker so that sorting by a
        non-unique column (floor, status, engineer, date) yields a
        deterministic order across pages.
        """
        column_map = {
            DeskSort.IDENTIFIER: desks.c.identifier,
            DeskSort.FLOOR: desks.c.floor,
            DeskSort.STATUS: desks.c.status,
            DeskSort.ENGINEER: desks.c.last_engineer,
            DeskSort.LAST_UPDATED: desks.c.last_updated,
        }
        primary = column_map[query.sort]
        primary = primary.desc() if query.descending else primary.asc()
        if query.sort is DeskSort.IDENTIFIER:
            return [primary]
        return [primary, desks.c.identifier.asc()]

    def update_fields(self, conn: Connection, desk_id: int, **fields) -> None:
        """Update selected columns of a desk.

        ``status`` may be passed as a DeskStatus and is persisted as its
        canonical string value.
        """
        if "status" in fields and isinstance(fields["status"], DeskStatus):
            fields["status"] = fields["status"].value
        if "last_updated" in fields and isinstance(fields["last_updated"], datetime):
            fields["last_updated"] = fields["last_updated"].isoformat()
        conn.execute(desks.update().where(desks.c.id == desk_id).values(**fields))

    def add_history(self, conn: Connection, entry: DeskHistory) -> None:
        """Append an immutable history row for a desk."""
        conn.execute(
            desk_history.insert().values(
                desk_id=entry.desk_id,
                previous_status=entry.previous_status.value if entry.previous_status else None,
                new_status=entry.new_status.value if entry.new_status else None,
                engineer=entry.engineer,
                changed_at=entry.changed_at.isoformat(),
                halo_ticket=entry.halo_ticket,
                notes=entry.notes,
            )
        )

    def history_for(self, conn: Connection, desk_id: int) -> list[DeskHistory]:
        rows = conn.execute(
            select(desk_history)
            .where(desk_history.c.desk_id == desk_id)
            .order_by(desk_history.c.changed_at.desc())
        ).all()
        return [_row_to_history(r) for r in rows]
