"""Add tenant_translations table for dynamic wording and localization.

Revision ID: e5g7i9k1m3o5
Revises: d4f6h8j0l2n4
Create Date: 2026-10-01 21:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e5g7i9k1m3o5'
down_revision: Union[str, Sequence[str], None] = 'd4f6h8j0l2n4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "tenant_translations" not in existing_tables:
        op.create_table(
            "tenant_translations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"),
            sa.Column("terminology", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_tenant_translations_id", "tenant_translations", ["id"], unique=False)
        op.create_index("ix_tenant_translations_tenant_id", "tenant_translations", ["tenant_id"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "tenant_translations" in existing_tables:
        op.drop_index("ix_tenant_translations_tenant_id", table_name="tenant_translations")
        op.drop_index("ix_tenant_translations_id", table_name="tenant_translations")
        op.drop_table("tenant_translations")
