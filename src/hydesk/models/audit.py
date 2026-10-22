"""Audit log domain model.

A single, polymorphic audit trail across all entity types. Each entry
records what changed, the before/after values, who made the change and
when, plus the identifier of the affected record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuditEntry:
    entity_type: str
    entity_id: int
    engineer: str
    changed_at: datetime
    field_changed: str | None = None
    previous_value: str | None = None
    new_value: str | None = None
    id: int | None = None
