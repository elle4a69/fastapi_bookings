"""Add worker leasing and retry columns to learning_events.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-25 14:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if "learning_events" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("learning_events")}

        if "lease_owner" not in existing_cols:
            op.add_column("learning_events", sa.Column("lease_owner", sa.String(100), nullable=True))
        if "lease_expires_at" not in existing_cols:
            op.add_column("learning_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        if "attempt_count" not in existing_cols:
            op.add_column("learning_events", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        if "next_attempt_at" not in existing_cols:
            op.add_column("learning_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        if "last_error" not in existing_cols:
            op.add_column("learning_events", sa.Column("last_error", sa.Text(), nullable=True))
        if "processed_at" not in existing_cols:
            op.add_column("learning_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))

        existing_indices = {idx["name"] for idx in inspector.get_indexes("learning_events")}
        if "ix_learning_events_claim" not in existing_indices:
            op.create_index(
                "ix_learning_events_claim",
                "learning_events",
                ["status", "next_attempt_at", "tenant_id"],
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if "learning_events" in existing_tables:
        existing_indices = {idx["name"] for idx in inspector.get_indexes("learning_events")}
        if "ix_learning_events_claim" in existing_indices:
            op.drop_index("ix_learning_events_claim", table_name="learning_events")

        existing_cols = {c["name"] for c in inspector.get_columns("learning_events")}
        for col in ["processed_at", "last_error", "next_attempt_at", "attempt_count", "lease_expires_at", "lease_owner"]:
            if col in existing_cols:
                op.drop_column("learning_events", col)
