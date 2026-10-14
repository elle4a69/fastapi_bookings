"""Add media_items table for durable tenant media persistence

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'y0z1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'x9y0z1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "media_items" not in existing_tables:
        op.create_table(
            "media_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "provider_id",
                sa.Integer(),
                sa.ForeignKey("providers.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("file_path", sa.String(length=500), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("description", sa.String(length=1000), nullable=True),
            sa.Column("alt_text", sa.String(length=255), nullable=True),
            sa.Column("media_type", sa.String(length=32), nullable=False, server_default="image"),
            sa.Column(
                "is_public_website_eligible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                index=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "media_items" in existing_tables:
        op.drop_table("media_items")
