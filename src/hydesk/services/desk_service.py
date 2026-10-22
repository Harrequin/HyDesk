"""Desk management business logic.

This service is the single place desk business rules live:

* Halo ticket validation (exactly seven numeric digits).
* The qualifying-update unit of work: updating a desk also stamps the
  acting engineer and timestamp, appends an immutable history row, and
  writes an audit entry -- all inside one transaction so a failure leaves
  nothing partially applied.

The service depends on an ``Engine`` and opens one transaction per
operation via ``engine.begin()``. Repositories receive that connection so
every write in an operation shares the transaction.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import Engine

from ..errors import NotFoundError, ValidationError
from ..models import Desk, DeskHistory, DeskStatus, AuditEntry
from ..repositories import DeskQuery, DeskRepository, Page, PageRequest
from ..repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)

_HALO_PATTERN = re.compile(r"^\d{7}$")
_ENTITY_TYPE = "desk"


def validate_halo_ticket(ticket: str | None) -> str | None:
    """Validate and normalise a Halo ticket reference.

    Returns the cleaned ticket, or None if no ticket was supplied. Raises
    ValidationError if a non-empty value is not exactly seven digits.
    """
    if ticket is None:
        return None
    cleaned = ticket.strip()
    if cleaned == "":
        return None
    if not _HALO_PATTERN.match(cleaned):
        raise ValidationError(
            "Halo ticket reference must be exactly seven numeric digits."
        )
    return cleaned


class DeskService:
    """Use cases for viewing and updating desks."""

    def __init__(
        self,
        engine: Engine,
        desk_repo: DeskRepository | None = None,
        audit_repo: AuditRepository | None = None,
        *,
        clock=None,
    ) -> None:
        self._engine = engine
        self._desks = desk_repo or DeskRepository()
        self._audit = audit_repo or AuditRepository()
        # Injectable clock keeps timestamps deterministic in tests.
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ---- reads -----------------------------------------------------------

    def get_desk(self, desk_id: int) -> Desk:
        with self._engine.connect() as conn:
            desk = self._desks.get(conn, desk_id)
        if desk is None:
            raise NotFoundError(f"Desk {desk_id} not found.")
        return desk

    def get_desk_by_identifier(self, identifier: str) -> Desk:
        with self._engine.connect() as conn:
            desk = self._desks.get_by_identifier(conn, identifier)
        if desk is None:
            raise NotFoundError(f"Desk '{identifier}' not found.")
        return desk

    def search_desks(self, query: DeskQuery, request: PageRequest) -> Page[Desk]:
        with self._engine.connect() as conn:
            return self._desks.search(conn, query, request)

    def view_history(self, desk_id: int) -> list[DeskHistory]:
        with self._engine.connect() as conn:
            return self._desks.history_for(conn, desk_id)

    # ---- writes ----------------------------------------------------------

    def update_desk(
        self,
        desk_id: int,
        engineer: str,
        *,
        status: DeskStatus | None = None,
        notes: str | None = None,
        halo_ticket: str | None = None,
        update_notes: bool = False,
        update_halo: bool = False,
        history_note: str | None = None,
    ) -> Desk:
        """Apply a qualifying desk update as a single transaction.

        Only the aspects explicitly requested change:

        * ``status`` updates the status when provided.
        * ``notes`` updates notes only when ``update_notes`` is True (so a
          caller can deliberately clear notes to None).
        * ``halo_ticket`` updates the ticket only when ``update_halo`` is
          True, after validation.

        The acting ``engineer`` and the current timestamp are always
        stamped. A history row and an audit entry are written in the same
        transaction. Raises ValidationError if nothing would change or the
        engineer is blank.
        """
        if not engineer or not engineer.strip():
            raise ValidationError("An engineer name is required for a desk update.")
        engineer = engineer.strip()

        if status is None and not update_notes and not update_halo:
            raise ValidationError("No changes were supplied for the desk update.")

        validated_halo = validate_halo_ticket(halo_ticket) if update_halo else None
        now = self._now()

        with self._engine.begin() as conn:
            desk = self._desks.get(conn, desk_id)
            if desk is None:
                raise NotFoundError(f"Desk {desk_id} not found.")

            previous_status = desk.status
            changes: dict = {"last_engineer": engineer, "last_updated": now}
            audit_entries: list[AuditEntry] = []

            if status is not None and status is not previous_status:
                changes["status"] = status
                audit_entries.append(
                    self._audit_entry(
                        desk_id, engineer, now, "status",
                        previous_status.value, status.value,
                    )
                )

            if update_notes and notes != desk.notes:
                changes["notes"] = notes
                audit_entries.append(
                    self._audit_entry(
                        desk_id, engineer, now, "notes", desk.notes, notes
                    )
                )

            if update_halo and validated_halo != desk.halo_ticket:
                changes["halo_ticket"] = validated_halo
                audit_entries.append(
                    self._audit_entry(
                        desk_id, engineer, now, "halo_ticket",
                        desk.halo_ticket, validated_halo,
                    )
                )

            self._desks.update_fields(conn, desk_id, **changes)

            new_status = status if "status" in changes else previous_status
            self._desks.add_history(
                conn,
                DeskHistory(
                    desk_id=desk_id,
                    previous_status=previous_status,
                    new_status=new_status,
                    engineer=engineer,
                    changed_at=now,
                    halo_ticket=changes.get("halo_ticket", desk.halo_ticket),
                    notes=history_note,
                ),
            )

            for entry in audit_entries:
                self._audit.add(conn, entry)

            updated = self._desks.get(conn, desk_id)

        logger.info(
            "Desk %s updated by %s (%d field change(s))",
            updated.identifier, engineer, len(audit_entries),
        )
        return updated

    def change_status(
        self,
        desk_id: int,
        status: DeskStatus,
        engineer: str,
        *,
        halo_ticket: str | None = None,
        history_note: str | None = None,
    ) -> Desk:
        """Convenience wrapper: change status (optionally with a ticket)."""
        return self.update_desk(
            desk_id,
            engineer,
            status=status,
            halo_ticket=halo_ticket,
            update_halo=halo_ticket is not None,
            history_note=history_note,
        )

    @staticmethod
    def _audit_entry(
        desk_id: int,
        engineer: str,
        when: datetime,
        field: str,
        previous,
        new,
    ) -> AuditEntry:
        return AuditEntry(
            entity_type=_ENTITY_TYPE,
            entity_id=desk_id,
            field_changed=field,
            previous_value=None if previous is None else str(previous),
            new_value=None if new is None else str(new),
            engineer=engineer,
            changed_at=when,
        )
