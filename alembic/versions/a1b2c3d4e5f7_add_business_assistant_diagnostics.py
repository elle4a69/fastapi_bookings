"""Add Business Assistant diagnostic-mode settings, client snapshots, and error logs

Revision ID: a1b2c3d4e5f7
Revises: z1a2b3c4d5e6
Create Date: 2026-10-09 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "business_assistant_diagnostic_settings" not in existing:
        op.create_table(
            "business_assistant_diagnostic_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("diagnostic_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "user_id", name="uq_ba_diagnostic_settings_scope"),
        )
        op.create_index("ix_business_assistant_diagnostic_settings_id", "business_assistant_diagnostic_settings", ["id"])
        op.create_index("ix_business_assistant_diagnostic_settings_tenant_id", "business_assistant_diagnostic_settings", ["tenant_id"])
        op.create_index("ix_business_assistant_diagnostic_settings_user_id", "business_assistant_diagnostic_settings", ["user_id"])
    if "business_assistant_client_snapshots" not in existing:
        op.create_table(
            "business_assistant_client_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "conversation_id",
                sa.Integer(),
                sa.ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("snapshot", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "user_id", "conversation_id", name="uq_ba_client_snapshots_scope"),
        )
        op.create_index("ix_business_assistant_client_snapshots_id", "business_assistant_client_snapshots", ["id"])
        op.create_index("ix_business_assistant_client_snapshots_tenant_id", "business_assistant_client_snapshots", ["tenant_id"])
        op.create_index("ix_business_assistant_client_snapshots_user_id", "business_assistant_client_snapshots", ["user_id"])
        op.create_index("ix_business_assistant_client_snapshots_conversation_id", "business_assistant_client_snapshots", ["conversation_id"])

    if "assistant_error_logs" not in existing:
        op.create_table(
            "assistant_error_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column(
                "conversation_id",
                sa.Integer(),
                sa.ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("source", sa.String(32), nullable=False),
            sa.Column("tool_name", sa.String(96), nullable=True),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("message", sa.String(500), nullable=False),
            sa.Column("transport", sa.String(32), nullable=True),
            sa.Column("route", sa.String(256), nullable=True),
        )
        op.create_index("ix_assistant_error_logs_id", "assistant_error_logs", ["id"])
        op.create_index("ix_assistant_error_logs_tenant_id", "assistant_error_logs", ["tenant_id"])
        op.create_index("ix_assistant_error_logs_user_id", "assistant_error_logs", ["user_id"])
        op.create_index("ix_assistant_error_logs_conversation_id", "assistant_error_logs", ["conversation_id"])
        op.create_index("ix_assistant_error_logs_timestamp", "assistant_error_logs", ["timestamp"])
        op.create_index("ix_assistant_error_logs_source", "assistant_error_logs", ["source"])
        op.create_index("ix_assistant_error_logs_tool_name", "assistant_error_logs", ["tool_name"])
        op.create_index("ix_assistant_error_logs_error_code", "assistant_error_logs", ["error_code"])
        op.create_index("ix_assistant_error_logs_tenant_timestamp", "assistant_error_logs", ["tenant_id", "timestamp"])
        op.create_index("ix_assistant_error_logs_conversation", "assistant_error_logs", ["conversation_id", "timestamp"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "assistant_error_logs" in existing:
        op.drop_table("assistant_error_logs")
    if "business_assistant_client_snapshots" in existing:
        op.drop_table("business_assistant_client_snapshots")
    if "business_assistant_diagnostic_settings" in existing:
        op.drop_table("business_assistant_diagnostic_settings")
