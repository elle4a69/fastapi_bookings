"""Add the disabled-by-default Assistant UI decision bridge ledger.

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
"""

from alembic import context, op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _bind():
    if context.is_offline_mode():
        raise RuntimeError("Assistant UI bridge migration is online-only")
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Assistant UI bridge migration requires PostgreSQL")
    return bind


def upgrade() -> None:
    bind = _bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("sms_chatwoot_bindings")}
    if "assistant_ui_policy_scope" in columns or "assistant_ui_bridge_jobs" in set(sa.inspect(bind).get_table_names()):
        raise RuntimeError("Assistant UI bridge migration found an unexpected table shape")
    op.execute(sa.text("LOCK TABLE sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE"))
    op.add_column("sms_chatwoot_bindings", sa.Column("assistant_ui_policy_scope", sa.String(length=128), nullable=True))
    op.create_table(
        "assistant_ui_bridge_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("policy_scope", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["binding_id"], ["sms_chatwoot_bindings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["conversation_id"], ["sms_conversations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_message_id"], ["sms_messages.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("request_id", name="uq_assistant_ui_bridge_jobs_request_id"),
        sa.UniqueConstraint("source_message_id", name="uq_assistant_ui_bridge_jobs_source_message"),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'CANCELLED', 'HANDOFF', 'COMPLETED')", name="ck_assistant_ui_bridge_jobs_status"),
    )
    for column in ("tenant_id", "binding_id", "conversation_id", "status"):
        op.create_index(f"ix_assistant_ui_bridge_jobs_{column}", "assistant_ui_bridge_jobs", [column])


def downgrade() -> None:
    bind = _bind()
    if bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM assistant_ui_bridge_jobs) OR EXISTS (SELECT 1 FROM sms_chatwoot_bindings WHERE assistant_ui_policy_scope IS NOT NULL) ")).scalar_one():
        raise RuntimeError("Refusing downgrade because Assistant UI bridge configuration or jobs exist")
    for column in ("tenant_id", "binding_id", "conversation_id", "status"):
        op.drop_index(f"ix_assistant_ui_bridge_jobs_{column}", table_name="assistant_ui_bridge_jobs")
    op.drop_table("assistant_ui_bridge_jobs")
    op.drop_column("sms_chatwoot_bindings", "assistant_ui_policy_scope")
