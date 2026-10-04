"""Add business assistant knowledge fields, versioning, and provenance

Revision ID: p1q2r3s4t5u6
Revises: 063f7f96be8d
Create Date: 2026-10-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'p1q2r3s4t5u6'
down_revision: Union[str, Sequence[str], None] = '063f7f96be8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = "business_assistant_memories"


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    if _TABLE_NAME not in _existing_tables():
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns(_TABLE_NAME)}

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if "interpretation" not in existing_columns:
            batch_op.add_column(sa.Column("interpretation", sa.Text(), nullable=True))
        if "category" not in existing_columns:
            batch_op.add_column(sa.Column("category", sa.String(length=64), nullable=False, server_default="policy"))
        if "version" not in existing_columns:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "payload_hash" not in existing_columns:
            batch_op.add_column(sa.Column("payload_hash", sa.String(length=64), nullable=True))
        if "provenance" not in existing_columns:
            batch_op.add_column(sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))
        if "curator_item_id" not in existing_columns:
            batch_op.add_column(sa.Column("curator_item_id", sa.Integer(), nullable=True))
        if "activated_at" not in existing_columns:
            batch_op.add_column(sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
        if "activated_by_user_id" not in existing_columns:
            batch_op.add_column(sa.Column("activated_by_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    if _TABLE_NAME not in _existing_tables():
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns(_TABLE_NAME)}

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        for col_name in (
            "activated_by_user_id",
            "activated_at",
            "curator_item_id",
            "provenance",
            "payload_hash",
            "version",
            "category",
            "interpretation",
        ):
            if col_name in existing_columns:
                batch_op.drop_column(col_name)
