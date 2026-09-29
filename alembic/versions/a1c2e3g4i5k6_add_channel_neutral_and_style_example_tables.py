"""Add channel-neutral messaging and message style example tables.

Revision ID: a1c2e3g4i5k6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-29 17:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e3g4i5k6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. channel_accounts
    if "channel_accounts" not in existing_tables:
        op.create_table(
            "channel_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=True),
            sa.Column("channel_type", sa.String(length=32), nullable=False),
            sa.Column("inbox_name", sa.String(), nullable=False),
            sa.Column("account_identifier", sa.String(), nullable=False),
            sa.Column("chatwoot_inbox_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("credentials_encrypted", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_channel_accounts_id"), "channel_accounts", ["id"], unique=False)
        op.create_index(op.f("ix_channel_accounts_tenant_id"), "channel_accounts", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_channel_accounts_provider_id"), "channel_accounts", ["provider_id"], unique=False)
        op.create_index(op.f("ix_channel_accounts_channel_type"), "channel_accounts", ["channel_type"], unique=False)
        op.create_index(op.f("ix_channel_accounts_account_identifier"), "channel_accounts", ["account_identifier"], unique=False)
        op.create_index(op.f("ix_channel_accounts_chatwoot_inbox_id"), "channel_accounts", ["chatwoot_inbox_id"], unique=False)

    # 2. conversations
    if "conversations" not in existing_tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=True),
            sa.Column("channel_account_id", sa.Integer(), sa.ForeignKey("channel_accounts.id", ondelete="CASCADE"), nullable=True),
            sa.Column("external_conversation_id", sa.String(), nullable=True),
            sa.Column("contact_identifier", sa.String(), nullable=False),
            sa.Column("contact_name", sa.String(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("metadata_payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_conversations_id"), "conversations", ["id"], unique=False)
        op.create_index(op.f("ix_conversations_tenant_id"), "conversations", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_conversations_provider_id"), "conversations", ["provider_id"], unique=False)
        op.create_index(op.f("ix_conversations_channel_account_id"), "conversations", ["channel_account_id"], unique=False)
        op.create_index(op.f("ix_conversations_external_conversation_id"), "conversations", ["external_conversation_id"], unique=False)
        op.create_index(op.f("ix_conversations_contact_identifier"), "conversations", ["contact_identifier"], unique=False)
        op.create_index(op.f("ix_conversations_status"), "conversations", ["status"], unique=False)
        op.create_index("ix_conversations_tenant_external_id", "conversations", ["tenant_id", "external_conversation_id"], unique=False)

    # 3. messages
    if "messages" not in existing_tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=True),
            sa.Column("direction", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("external_message_id", sa.String(), nullable=True),
            sa.Column("delivery_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("tool_calls", sa.JSON(), nullable=True),
            sa.Column("metadata_payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
        op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
        op.create_index(op.f("ix_messages_tenant_id"), "messages", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_messages_provider_id"), "messages", ["provider_id"], unique=False)
        op.create_index(op.f("ix_messages_external_message_id"), "messages", ["external_message_id"], unique=False)
        op.create_index("ix_messages_tenant_external_msg_id", "messages", ["tenant_id", "external_message_id"], unique=False)

    # 4. message_style_examples
    if "message_style_examples" not in existing_tables:
        op.create_table(
            "message_style_examples",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("intent", sa.String(length=64), nullable=False),
            sa.Column("client_message", sa.Text(), nullable=False),
            sa.Column("assistant_reply", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="procedural"),
            sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="assistant_ui_import"),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_message_style_examples_id"), "message_style_examples", ["id"], unique=False)
        op.create_index(op.f("ix_message_style_examples_tenant_id"), "message_style_examples", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_message_style_examples_provider_id"), "message_style_examples", ["provider_id"], unique=False)
        op.create_index(op.f("ix_message_style_examples_intent"), "message_style_examples", ["intent"], unique=False)
        op.create_index(op.f("ix_message_style_examples_is_approved"), "message_style_examples", ["is_approved"], unique=False)
        op.create_index(op.f("ix_message_style_examples_is_active"), "message_style_examples", ["is_active"], unique=False)
        op.create_index(op.f("ix_message_style_examples_content_hash"), "message_style_examples", ["content_hash"], unique=False)
        op.create_index(
            "ix_mse_lookup",
            "message_style_examples",
            ["tenant_id", "provider_id", "intent", "is_active", "is_approved"],
            unique=False,
        )
        op.create_index("ix_mse_content_hash", "message_style_examples", ["content_hash"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "message_style_examples" in existing_tables:
        op.drop_table("message_style_examples")
    if "messages" in existing_tables:
        op.drop_table("messages")
    if "conversations" in existing_tables:
        op.drop_table("conversations")
    if "channel_accounts" in existing_tables:
        op.drop_table("channel_accounts")
