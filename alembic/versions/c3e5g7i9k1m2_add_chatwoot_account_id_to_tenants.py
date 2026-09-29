"""Add chatwoot_account_id to tenants table.

Revision ID: c3e5g7i9k1m2
Revises: b2d3f4h5j6l7
Create Date: 2026-09-29 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5g7i9k1m2'
down_revision: Union[str, Sequence[str], None] = 'b2d3f4h5j6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "chatwoot_account_id" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column("chatwoot_account_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_tenants_chatwoot_account_id",
            "tenants",
            ["chatwoot_account_id"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "chatwoot_account_id" in existing_columns:
        op.drop_index("ix_tenants_chatwoot_account_id", table_name="tenants")
        op.drop_column("tenants", "chatwoot_account_id")
