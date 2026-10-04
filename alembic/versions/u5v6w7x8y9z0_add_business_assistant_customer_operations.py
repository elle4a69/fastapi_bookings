"""Add business assistant customer operations, message drafts, and campaign proposals

Revision ID: u5v6w7x8y9z0
Revises: p1q2r3s4t5u6
Create Date: 2026-10-04 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'u5v6w7x8y9z0'
down_revision: Union[str, Sequence[str], None] = 'p1q2r3s4t5u6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Update clients table with consent & opt-out fields
    if "clients" in existing_tables:
        existing_client_cols = {col["name"] for col in inspector.get_columns("clients")}
        with op.batch_alter_table("clients") as batch_op:
            if "opted_out" not in existing_client_cols:
                batch_op.add_column(
                    sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false())
                )
            if "sms_consent" not in existing_client_cols:
                batch_op.add_column(
                    sa.Column("sms_consent", sa.Boolean(), nullable=False, server_default=sa.true())
                )

    # 2. Create business_assistant_message_drafts
    if "business_assistant_message_drafts" not in existing_tables:
        op.create_table(
            "business_assistant_message_drafts",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("recipient_preview", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("request_key", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('draft', 'approved', 'cancelled')", name="ck_business_assistant_draft_status"),
            sa.UniqueConstraint("tenant_id", "user_id", "request_key", name="uq_business_assistant_draft_request_key"),
        )
        op.create_index(
            "ix_business_assistant_message_drafts_scope_status",
            "business_assistant_message_drafts",
            ["tenant_id", "status", "created_at"],
        )
        op.create_index(
            "ix_business_assistant_message_drafts_conversation",
            "business_assistant_message_drafts",
            ["tenant_id", "conversation_id", "created_at"],
        )

    # 3. Create business_assistant_campaign_proposals
    if "business_assistant_campaign_proposals" not in existing_tables:
        op.create_table(
            "business_assistant_campaign_proposals",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("target_audience_criteria", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("audience_snapshot", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("request_key", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('proposed', 'approved', 'cancelled')", name="ck_business_assistant_campaign_status"),
            sa.UniqueConstraint("tenant_id", "user_id", "request_key", name="uq_business_assistant_campaign_request_key"),
        )
        op.create_index(
            "ix_business_assistant_campaign_proposals_scope_status",
            "business_assistant_campaign_proposals",
            ["tenant_id", "status", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_assistant_campaign_proposals" in existing_tables:
        op.drop_table("business_assistant_campaign_proposals")

    if "business_assistant_message_drafts" in existing_tables:
        op.drop_table("business_assistant_message_drafts")

    if "clients" in existing_tables:
        existing_client_cols = {col["name"] for col in inspector.get_columns("clients")}
        with op.batch_alter_table("clients") as batch_op:
            if "sms_consent" in existing_client_cols:
                batch_op.drop_column("sms_consent")
            if "opted_out" in existing_client_cols:
                batch_op.drop_column("opted_out")
