"""Audit log repository.

Writes entries to the single polymorphic audit trail. Like the other
repositories it takes a ``Connection`` so audit writes join the same
transaction as the change they record.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Connection, select

from ..db.schema import audit_log
from ..models import AuditEntry


def _row_to_entry(row) -> AuditEntry:  # noqa: ANN001
    return AuditEntry(
        id=row.id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        field_changed=row.field_changed,
        previous_value=row.previous_value,
        new_value=row.new_value,
        engineer=row.engineer,
        changed_at=datetime.fromisoformat(row.changed_at),
    )


class AuditRepository:
    """Persistence for audit entries."""

    def add(self, conn: Connection, entry: AuditEntry) -> None:
        conn.execute(
            audit_log.insert().values(
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                field_changed=entry.field_changed,
                previous_value=entry.previous_value,
                new_value=entry.new_value,
                engineer=entry.engineer,
                changed_at=entry.changed_at.isoformat(),
            )
        )

    def for_entity(
        self, conn: Connection, entity_type: str, entity_id: int
    ) -> list[AuditEntry]:
        rows = conn.execute(
            select(audit_log)
            .where(audit_log.c.entity_type == entity_type)
            .where(audit_log.c.entity_id == entity_id)
            .order_by(audit_log.c.changed_at.desc())
        ).all()
        return [_row_to_entry(r) for r in rows]
