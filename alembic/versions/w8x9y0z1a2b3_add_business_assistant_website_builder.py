"""Add business assistant website builder proposals table

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-10-04 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'w8x9y0z1a2b3'
down_revision: Union[str, Sequence[str], None] = 'v7w8x9y0z1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_assistant_website_proposals" not in existing_tables:
        op.create_table(
            "business_assistant_website_proposals",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content_payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "published_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("rollback_version", sa.Integer(), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("request_key", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'preview', 'published', 'rolled_back')",
                name="ck_business_assistant_website_proposal_status",
            ),
        )
        op.create_index(
            "ix_business_assistant_website_proposals_scope_status",
            "business_assistant_website_proposals",
            ["tenant_id", "status", "created_at"],
        )
        op.create_index(
            "ix_business_assistant_website_proposals_scope_version",
            "business_assistant_website_proposals",
            ["tenant_id", "version"],
        )
        op.create_index(
            "ix_business_assistant_website_proposals_request_key",
            "business_assistant_website_proposals",
            ["tenant_id", "created_by_user_id", "request_key"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_assistant_website_proposals" in existing_tables:
        op.drop_table("business_assistant_website_proposals")
