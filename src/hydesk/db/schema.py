"""Database schema defined with SQLAlchemy Core.

Using Core (not the ORM) keeps the SQL explicit and database-agnostic so the
same definitions work against SQLite now and PostgreSQL later. Enum values
are stored as TEXT with CHECK constraints; the authoritative validation
lives in the service layer, the CHECKs are a defence-in-depth safety net.

Timestamps are stored as TEXT in ISO-8601 form for portability across
database backends.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

# Canonical enum value lists, referenced by CHECK constraints.
_DESK_STATUSES = ("ACTIVE", "DOWN", "IN_REPAIR", "AWAITING_EQUIPMENT")
_MOVEMENT_TYPES = ("RECEIVED", "ISSUED", "ADJUSTMENT", "CORRECTION")
_DELIVERY_STATUSES = ("EXPECTED", "PARTIAL", "RECEIVED", "CANCELLED")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


desks = Table(
    "desks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("identifier", String, nullable=False, unique=True),
    Column("floor", Integer, nullable=False),
    Column("status", String, nullable=False, server_default="ACTIVE"),
    Column("last_engineer", String),
    Column("last_updated", String),
    Column("notes", Text),
    Column("halo_ticket", String),
    CheckConstraint(_in_list("status", _DESK_STATUSES), name="ck_desks_status"),
    CheckConstraint(
        "halo_ticket IS NULL OR "
        "halo_ticket GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9]'",
        name="ck_desks_halo_ticket",
    ),
)

desk_history = Table(
    "desk_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("desk_id", Integer, ForeignKey("desks.id"), nullable=False),
    Column("previous_status", String),
    Column("new_status", String),
    Column("engineer", String, nullable=False),
    Column("changed_at", String, nullable=False),
    Column("halo_ticket", String),
    Column("notes", Text),
)

stock_items = Table(
    "stock_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("category", String, nullable=False),
    Column("name", String, nullable=False),
    Column("location", String),
    Column("quantity", Integer, nullable=False, server_default="0"),
    Column("low_stock_threshold", Integer, nullable=False, server_default="0"),
    Column("last_updated", String),
    CheckConstraint("quantity >= 0", name="ck_stock_items_quantity_nonneg"),
)

incoming_deliveries = Table(
    "incoming_deliveries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("stock_item_id", Integer, ForeignKey("stock_items.id"), nullable=False),
    Column("expected_qty", Integer, nullable=False),
    Column("received_qty", Integer, nullable=False, server_default="0"),
    Column("date_recorded", String, nullable=False),
    Column("expected_date", String),
    Column("actual_receipt_date", String),
    Column("status", String, nullable=False, server_default="EXPECTED"),
    Column("notes", Text),
    CheckConstraint(_in_list("status", _DELIVERY_STATUSES), name="ck_incoming_status"),
    CheckConstraint("expected_qty >= 0", name="ck_incoming_expected_nonneg"),
    CheckConstraint("received_qty >= 0", name="ck_incoming_received_nonneg"),
)

stock_movements = Table(
    "stock_movements",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("stock_item_id", Integer, ForeignKey("stock_items.id"), nullable=False),
    Column("movement_type", String, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("previous_qty", Integer, nullable=False),
    Column("resulting_qty", Integer, nullable=False),
    Column("engineer", String, nullable=False),
    Column("occurred_at", String, nullable=False),
    Column("delivery_id", Integer, ForeignKey("incoming_deliveries.id")),
    Column("notes", Text),
    CheckConstraint(
        _in_list("movement_type", _MOVEMENT_TYPES), name="ck_movements_type"
    ),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("entity_type", String, nullable=False),
    Column("entity_id", Integer, nullable=False),
    Column("field_changed", String),
    Column("previous_value", Text),
    Column("new_value", Text),
    Column("engineer", String, nullable=False),
    Column("changed_at", String, nullable=False),
)
