"""Add assistant_policy column to tenants table.

Revision ID: b2d3f4h5j6l7
Revises: a1c2e3g4i5k6
Create Date: 2026-09-29 21:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3f4h5j6l7'
down_revision: Union[str, Sequence[str], None] = 'a1c2e3g4i5k6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "assistant_policy" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column("assistant_policy", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "assistant_policy" in existing_columns:
        op.drop_column("tenants", "assistant_policy")
