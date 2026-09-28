"""Add model, role_description, training_notes, and learned_facts to sms_bootcamp_settings.

Revision ID: e4f5a6b7c8d9
Revises: c5e6f7a8b9c0
Create Date: 2026-09-27 15:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'c5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "sms_bootcamp_settings" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_bootcamp_settings")}
        with op.batch_alter_table("sms_bootcamp_settings") as batch_op:
            if "model" not in cols:
                batch_op.add_column(sa.Column("model", sa.String(length=64), nullable=False, server_default="gpt-4o-mini"))
            if "role_description" not in cols:
                batch_op.add_column(sa.Column("role_description", sa.Text(), nullable=True))
            if "training_notes" not in cols:
                batch_op.add_column(sa.Column("training_notes", sa.Text(), nullable=True))
            if "learned_facts" not in cols:
                batch_op.add_column(sa.Column("learned_facts", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "sms_bootcamp_settings" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_bootcamp_settings")}
        with op.batch_alter_table("sms_bootcamp_settings") as batch_op:
            if "learned_facts" in cols:
                batch_op.drop_column("learned_facts")
            if "training_notes" in cols:
                batch_op.drop_column("training_notes")
            if "role_description" in cols:
                batch_op.drop_column("role_description")
            if "model" in cols:
                batch_op.drop_column("model")
