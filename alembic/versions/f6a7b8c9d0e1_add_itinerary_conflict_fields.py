"""Add itinerary conflict fields to bookings.

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-09-27 17:55:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "bookings" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("bookings")}
        with op.batch_alter_table("bookings") as batch_op:
            if "has_itinerary_conflict" not in cols:
                batch_op.add_column(sa.Column("has_itinerary_conflict", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "itinerary_conflict" not in cols:
                batch_op.add_column(sa.Column("itinerary_conflict", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "bookings" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("bookings")}
        with op.batch_alter_table("bookings") as batch_op:
            if "itinerary_conflict" in cols:
                batch_op.drop_column("itinerary_conflict")
            if "has_itinerary_conflict" in cols:
                batch_op.drop_column("has_itinerary_conflict")
