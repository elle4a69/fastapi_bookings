"""Reconcile pre-upgrade schema: missing tenant_id columns, bootcamp models, proposals, and learning events.

Revision ID: f3a4b5c6d7e8
Revises: b1c2d3e4f5a6
Create Date: 2026-09-25 11:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. calendar_notes.tenant_id
    if "calendar_notes" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("calendar_notes")}
        if "tenant_id" not in cols:
            op.add_column(
                "calendar_notes",
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            )
            # Backfill from provider's tenant_id if available
            op.execute("""
                UPDATE calendar_notes cn
                SET tenant_id = p.tenant_id
                FROM providers p
                WHERE cn.provider_id = p.id AND cn.tenant_id IS NULL;
            """)
            op.alter_column("calendar_notes", "tenant_id", nullable=False)
            op.create_index("ix_calendar_notes_tenant_id", "calendar_notes", ["tenant_id"])

    # 2. sms_outbound_jobs.tenant_id and lease_token
    if "sms_outbound_jobs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_outbound_jobs")}
        if "tenant_id" not in cols:
            op.add_column(
                "sms_outbound_jobs",
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            )
            op.execute("""
                UPDATE sms_outbound_jobs o
                SET tenant_id = m.tenant_id
                FROM sms_messages m
                WHERE o.message_id = m.id AND o.tenant_id IS NULL;
            """)
            op.create_index("ix_sms_outbound_jobs_tenant_id", "sms_outbound_jobs", ["tenant_id"])
        if "lease_token" not in cols:
            op.add_column(
                "sms_outbound_jobs",
                sa.Column("lease_token", sa.String(length=36), nullable=True),
            )

    # 3. sms_ai_jobs.tenant_id
    if "sms_ai_jobs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_ai_jobs")}
        if "tenant_id" not in cols:
            op.add_column(
                "sms_ai_jobs",
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            )
            op.execute("""
                UPDATE sms_ai_jobs j
                SET tenant_id = c.tenant_id
                FROM sms_conversations c
                WHERE j.conversation_id = c.id AND j.tenant_id IS NULL;
            """)
            op.create_index("ix_sms_ai_jobs_tenant_id", "sms_ai_jobs", ["tenant_id"])

    # 4. sms_conversation_events.tenant_id
    if "sms_conversation_events" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_conversation_events")}
        if "tenant_id" not in cols:
            op.add_column(
                "sms_conversation_events",
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            )
            op.execute("""
                UPDATE sms_conversation_events e
                SET tenant_id = c.tenant_id
                FROM sms_conversations c
                WHERE e.conversation_id = c.id AND e.tenant_id IS NULL;
            """)
            op.create_index("ix_sms_conversation_events_tenant_id", "sms_conversation_events", ["tenant_id"])

    # 5. sms_notes.tenant_id
    if "sms_notes" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_notes")}
        if "tenant_id" not in cols:
            op.add_column(
                "sms_notes",
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            )
            op.execute("""
                UPDATE sms_notes n
                SET tenant_id = c.tenant_id
                FROM sms_conversations c
                WHERE n.conversation_id = c.id AND n.tenant_id IS NULL;
            """)
            op.create_index("ix_sms_notes_tenant_id", "sms_notes", ["tenant_id"])

    # 6. sms_bootcamp_settings
    if "sms_bootcamp_settings" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("sms_bootcamp_settings")}
        if "provider_id" not in cols:
            op.add_column(
                "sms_bootcamp_settings",
                sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=True),
            )
            op.create_index("ix_sms_bootcamp_settings_provider_id", "sms_bootcamp_settings", ["provider_id"])
        # Reconcile unique constraint: drop old tenant_id unique if present and create composite
        try:
            op.drop_index("ix_sms_bootcamp_settings_tenant_id", table_name="sms_bootcamp_settings")
        except Exception:
            pass
        try:
            op.create_unique_constraint(
                "uq_sms_bootcamp_settings_tenant_provider",
                "sms_bootcamp_settings",
                ["tenant_id", "provider_id"],
            )
        except Exception:
            pass
        try:
            op.create_index("ix_sms_bootcamp_settings_tenant_id", "sms_bootcamp_settings", ["tenant_id"])
        except Exception:
            pass
    else:
        op.create_table(
            "sms_bootcamp_settings",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("active_style_profile", sa.JSON(), nullable=False),
            sa.Column("previous_style_profile", sa.JSON(), nullable=True),
            sa.Column("agent_name", sa.String(length=64), nullable=False, server_default="Tori"),
            sa.Column("system_prompt_template", sa.Text(), nullable=True),
            sa.Column("custom_training_notes", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "provider_id", name="uq_sms_bootcamp_settings_tenant_provider"),
        )

    # 7. sms_bootcamp_runs
    if "sms_bootcamp_runs" not in existing_tables:
        op.create_table(
            "sms_bootcamp_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
            sa.Column("selected_personas", sa.JSON(), nullable=False),
            sa.Column("selected_scenarios", sa.JSON(), nullable=True),
            sa.Column("autonomy_level", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("max_turns", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("style_profile", sa.JSON(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 8. sms_bootcamp_conversations
    if "sms_bootcamp_conversations" not in existing_tables:
        op.create_table(
            "sms_bootcamp_conversations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("sms_bootcamp_runs.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("persona_id", sa.String(length=64), nullable=False),
            sa.Column("persona_name", sa.String(length=128), nullable=False),
            sa.Column("scenario_id", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
            sa.Column("current_turn", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("needs_handoff", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("handoff_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 9. sms_bootcamp_messages
    if "sms_bootcamp_messages" not in existing_tables:
        op.create_table(
            "sms_bootcamp_messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("sms_bootcamp_conversations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 10. knowledge_proposals
    if "knowledge_proposals" not in existing_tables:
        op.create_table(
            "knowledge_proposals",
            sa.Column("id", sa.Integer(), primary_key=True, index=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("proposal_type", sa.String(length=24), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="pending", index=True),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="faq"),
            sa.Column("knowledge_kind", sa.String(length=32), nullable=False, server_default="durable_fact"),
            sa.Column("authority", sa.String(length=32), nullable=False, server_default="conversation_candidate"),
            sa.Column("user_query", sa.Text(), nullable=True),
            sa.Column("proposed_response", sa.Text(), nullable=True),
            sa.Column("target_memory_id", sa.Integer(), sa.ForeignKey("curated_memories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("contains_dynamic_fact", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("requires_review", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolution_code", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'dismissed', 'resolved')", name="ck_knowledge_proposals_status"),
            sa.CheckConstraint("proposal_type IN ('add', 'duplicate', 'conflict', 'stale', 'supersede', 'gap', 'quarantine')", name="ck_knowledge_proposals_type"),
            sa.UniqueConstraint("tenant_id", "fingerprint", "status", name="uq_knowledge_proposal_tenant_fingerprint_status"),
        )
        op.create_index(
            "ix_knowledge_proposals_review_queue",
            "knowledge_proposals",
            ["tenant_id", "status", "proposal_type", "created_at"],
        )

    # 11. learning_events
    if "learning_events" not in existing_tables:
        op.create_table(
            "learning_events",
            sa.Column("id", sa.String(length=36), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("conversation_id", sa.String(length=64), nullable=True, index=True),
            sa.Column("message_id", sa.String(length=64), nullable=True, index=True),
            sa.Column("event_type", sa.String(length=64), nullable=False, index=True),
            sa.Column("source", sa.String(length=64), nullable=False, index=True),
            sa.Column("customer_message", sa.Text(), nullable=True),
            sa.Column("original_ai_content", sa.Text(), nullable=True),
            sa.Column("human_content", sa.Text(), nullable=True),
            sa.Column("diff_payload", sa.JSON(), nullable=True),
            sa.Column("metadata_payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", index=True),
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_learning_events_tenant_status",
            "learning_events",
            ["tenant_id", "status", "created_at"],
        )
        op.create_index(
            "ix_learning_events_tenant_source_type",
            "learning_events",
            ["tenant_id", "source", "event_type"],
        )


def downgrade() -> None:
    pass
