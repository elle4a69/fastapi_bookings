"""Add tenant-scoped Business Assistant foundation tables.

Revision ID: g7h9j1k3m5n7
Revises: f6h8j0l2n4p6
Create Date: 2026-10-02 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7h9j1k3m5n7"
down_revision: Union[str, Sequence[str], None] = "f6h8j0l2n4p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing_tables = _existing_tables()

    if "business_assistant_conversations" not in existing_tables:
        op.create_table(
            "business_assistant_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("creation_request_key", sa.String(length=128), nullable=True),
            sa.Column("creation_payload_hash", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "user_id", "creation_request_key", name="uq_business_assistant_conversation_creation_key"),
        )
        op.create_index("ix_business_assistant_conversations_tenant_id", "business_assistant_conversations", ["tenant_id"])
        op.create_index("ix_business_assistant_conversations_user_id", "business_assistant_conversations", ["user_id"])
        op.create_index("ix_business_assistant_conversations_status", "business_assistant_conversations", ["status"])
        op.create_index("ix_business_assistant_conversations_scope_updated", "business_assistant_conversations", ["tenant_id", "user_id", "updated_at"])

    if "business_assistant_messages" not in existing_tables:
        op.create_table(
            "business_assistant_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("request_key", sa.String(length=128), nullable=True),
            sa.Column("request_payload_hash", sa.String(length=64), nullable=True),
            sa.Column("channel", sa.String(length=32), nullable=False, server_default="text"),
            sa.Column("realtime_session_id", sa.String(length=36), nullable=True),
            sa.Column("realtime_item_id", sa.String(length=200), nullable=True),
            sa.Column("generation_status", sa.String(length=32), nullable=True),
            sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("in_reply_to_message_id", sa.Integer(), sa.ForeignKey("business_assistant_messages.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("role IN ('user', 'business_assistant', 'system')", name="ck_business_assistant_message_role"),
            sa.UniqueConstraint("tenant_id", "user_id", "conversation_id", "request_key", name="uq_business_assistant_message_request_key"),
            sa.UniqueConstraint(
                "tenant_id",
                "user_id",
                "conversation_id",
                "realtime_session_id",
                "realtime_item_id",
                name="uq_business_assistant_message_realtime_item",
            ),
        )
        op.create_index("ix_business_assistant_messages_conversation_id", "business_assistant_messages", ["conversation_id"])
        op.create_index("ix_business_assistant_messages_tenant_id", "business_assistant_messages", ["tenant_id"])
        op.create_index("ix_business_assistant_messages_user_id", "business_assistant_messages", ["user_id"])
        op.create_index("ix_business_assistant_messages_generation_status", "business_assistant_messages", ["generation_status"])
        op.create_index("ix_business_assistant_messages_channel", "business_assistant_messages", ["channel"])
        op.create_index("ix_business_assistant_messages_in_reply_to_message_id", "business_assistant_messages", ["in_reply_to_message_id"])
        op.create_index("ix_business_assistant_messages_scope_conversation", "business_assistant_messages", ["tenant_id", "conversation_id", "created_at"])

    if "business_assistant_tool_runs" not in existing_tables:
        op.create_table(
            "business_assistant_tool_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("business_assistant_messages.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tool_name", sa.String(length=96), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("request_id", sa.String(length=128), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("safe_metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name, columns in (
            ("ix_business_assistant_tool_runs_tenant_id", ["tenant_id"]),
            ("ix_business_assistant_tool_runs_user_id", ["user_id"]),
            ("ix_business_assistant_tool_runs_conversation_id", ["conversation_id"]),
            ("ix_business_assistant_tool_runs_message_id", ["message_id"]),
            ("ix_business_assistant_tool_runs_request_id", ["request_id"]),
            ("ix_business_assistant_tool_runs_scope_created", ["tenant_id", "user_id", "created_at"]),
            ("ix_business_assistant_tool_runs_conversation_created", ["conversation_id", "created_at"]),
        ):
            op.create_index(name, "business_assistant_tool_runs", columns)

    if "business_assistant_memories" not in existing_tables:
        op.create_table(
            "business_assistant_memories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("memory_key", sa.String(length=128), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "user_id", "memory_key", name="uq_business_assistant_memory_scope_key"),
        )
        op.create_index("ix_business_assistant_memories_tenant_id", "business_assistant_memories", ["tenant_id"])
        op.create_index("ix_business_assistant_memories_user_id", "business_assistant_memories", ["user_id"])
        op.create_index("ix_business_assistant_memories_status", "business_assistant_memories", ["status"])
        op.create_index("ix_business_assistant_memories_scope_status", "business_assistant_memories", ["tenant_id", "user_id", "status"])

    if "business_assistant_onboarding_progress" not in existing_tables:
        op.create_table(
            "business_assistant_onboarding_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="not_started"),
            sa.Column("completed_steps", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('not_started', 'in_progress', 'completed')",
                name="ck_business_assistant_onboarding_status",
            ),
            sa.UniqueConstraint("tenant_id", "user_id", name="uq_business_assistant_onboarding_scope"),
        )
        for name, columns in (
            ("ix_business_assistant_onboarding_progress_tenant_id", ["tenant_id"]),
            ("ix_business_assistant_onboarding_progress_user_id", ["user_id"]),
            ("ix_business_assistant_onboarding_progress_status", ["status"]),
        ):
            op.create_index(name, "business_assistant_onboarding_progress", columns)

    if "business_assistant_support_tickets" not in existing_tables:
        op.create_table(
            "business_assistant_support_tickets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("business_assistant_conversations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("category", sa.String(length=48), nullable=False),
            sa.Column("severity", sa.String(length=24), nullable=False, server_default="normal"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="awaiting_engineering"),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("request_key", sa.String(length=128), nullable=True),
            sa.Column("request_payload_hash", sa.String(length=64), nullable=True),
            sa.Column("deduplication_key", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "category IN ('support', 'bug', 'feature', 'access', 'security', 'upgrade')",
                name="ck_business_assistant_ticket_category",
            ),
            sa.CheckConstraint(
                "severity IN ('low', 'normal', 'high', 'critical')",
                name="ck_business_assistant_ticket_severity",
            ),
            sa.UniqueConstraint("tenant_id", "user_id", "request_key", name="uq_business_assistant_ticket_request_key"),
        )
        for name, columns in (
            ("ix_business_assistant_support_tickets_tenant_id", ["tenant_id"]),
            ("ix_business_assistant_support_tickets_user_id", ["user_id"]),
            ("ix_business_assistant_support_tickets_conversation_id", ["conversation_id"]),
            ("ix_business_assistant_support_tickets_category", ["category"]),
            ("ix_business_assistant_support_tickets_severity", ["severity"]),
            ("ix_business_assistant_support_tickets_status", ["status"]),
            ("ix_business_assistant_support_tickets_scope_status", ["tenant_id", "status", "created_at"]),
            ("ix_business_assistant_support_tickets_scope_request", ["tenant_id", "request_key"]),
            (
                "ix_business_assistant_support_tickets_scope_deduplication",
                ["tenant_id", "user_id", "deduplication_key"],
            ),
        ):
            op.create_index(name, "business_assistant_support_tickets", columns)

    if "business_assistant_active_ticket_claims" not in existing_tables:
        op.create_table(
            "business_assistant_active_ticket_claims",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "ticket_id",
                sa.Integer(),
                sa.ForeignKey("business_assistant_support_tickets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deduplication_key", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "tenant_id",
                "user_id",
                "deduplication_key",
                name="uq_business_assistant_active_ticket_claim",
            ),
            sa.UniqueConstraint("ticket_id", name="uq_business_assistant_active_ticket_claim_ticket"),
        )
        for name, columns in (
            ("ix_business_assistant_active_ticket_claims_ticket_id", ["ticket_id"]),
            ("ix_business_assistant_active_ticket_claims_tenant_id", ["tenant_id"]),
            ("ix_business_assistant_active_ticket_claims_user_id", ["user_id"]),
        ):
            op.create_index(name, "business_assistant_active_ticket_claims", columns)

    if "business_assistant_support_ticket_events" not in existing_tables:
        op.create_table(
            "business_assistant_support_ticket_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("business_assistant_support_tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("safe_metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name, columns in (
            ("ix_business_assistant_support_ticket_events_ticket_id", ["ticket_id"]),
            ("ix_business_assistant_support_ticket_events_tenant_id", ["tenant_id"]),
            ("ix_business_assistant_support_ticket_events_actor_user_id", ["actor_user_id"]),
            ("ix_business_assistant_support_ticket_events_event_type", ["event_type"]),
            ("ix_business_assistant_ticket_events_ticket_created", ["ticket_id", "created_at"]),
        ):
            op.create_index(name, "business_assistant_support_ticket_events", columns)


def downgrade() -> None:
    existing_tables = _existing_tables()
    for table_name in (
        "business_assistant_support_ticket_events",
        "business_assistant_active_ticket_claims",
        "business_assistant_support_tickets",
        "business_assistant_onboarding_progress",
        "business_assistant_memories",
        "business_assistant_tool_runs",
        "business_assistant_messages",
        "business_assistant_conversations",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)
