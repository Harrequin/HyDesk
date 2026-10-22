"""Initial HyDesk schema (baseline).

Creates the six core tables: desks, desk_history, stock_items,
stock_movements, incoming_deliveries and audit_log, with their foreign-key
and check constraints. This baseline mirrors the application's SQLAlchemy
Core metadata so a fresh database (SQLite or PostgreSQL) can be built
entirely from migrations.

Revision ID: 0001
Revises:
Create Date: 2026-10-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "desks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
        sa.Column("last_engineer", sa.String(), nullable=True),
        sa.Column("last_updated", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("halo_ticket", sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DOWN', 'IN_REPAIR', 'AWAITING_EQUIPMENT')",
            name="ck_desks_status",
        ),
        sa.CheckConstraint(
            "halo_ticket IS NULL OR "
            "halo_ticket GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9]'",
            name="ck_desks_halo_ticket",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier"),
    )

    op.create_table(
        "stock_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "low_stock_threshold", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("last_updated", sa.String(), nullable=True),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_items_quantity_nonneg"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "desk_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("desk_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=True),
        sa.Column("new_status", sa.String(), nullable=True),
        sa.Column("engineer", sa.String(), nullable=False),
        sa.Column("changed_at", sa.String(), nullable=False),
        sa.Column("halo_ticket", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["desk_id"], ["desks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "incoming_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_item_id", sa.Integer(), nullable=False),
        sa.Column("expected_qty", sa.Integer(), nullable=False),
        sa.Column("received_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("date_recorded", sa.String(), nullable=False),
        sa.Column("expected_date", sa.String(), nullable=True),
        sa.Column("actual_receipt_date", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="EXPECTED", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('EXPECTED', 'PARTIAL', 'RECEIVED', 'CANCELLED')",
            name="ck_incoming_status",
        ),
        sa.CheckConstraint("expected_qty >= 0", name="ck_incoming_expected_nonneg"),
        sa.CheckConstraint("received_qty >= 0", name="ck_incoming_received_nonneg"),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_item_id", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("previous_qty", sa.Integer(), nullable=False),
        sa.Column("resulting_qty", sa.Integer(), nullable=False),
        sa.Column("engineer", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "movement_type IN ('RECEIVED', 'ISSUED', 'ADJUSTMENT', 'CORRECTION')",
            name="ck_movements_type",
        ),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_items.id"]),
        sa.ForeignKeyConstraint(["delivery_id"], ["incoming_deliveries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_changed", sa.String(), nullable=True),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("engineer", sa.String(), nullable=False),
        sa.Column("changed_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("stock_movements")
    op.drop_table("incoming_deliveries")
    op.drop_table("desk_history")
    op.drop_table("stock_items")
    op.drop_table("desks")
