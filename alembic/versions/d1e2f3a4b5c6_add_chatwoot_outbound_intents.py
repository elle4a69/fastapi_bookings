"""Add the fail-closed Package D Chatwoot outbound intent ledger.

Revision ID: d1e2f3a4b5c6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-06 04:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _online_postgresql_bind():
    if context.is_offline_mode():
        raise RuntimeError("Chatwoot outbound migration is online-only")
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Chatwoot outbound migration requires PostgreSQL")
    return bind


def _columns(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        raise RuntimeError("Chatwoot outbound migration found an unexpected table shape")
    return {column["name"] for column in inspector.get_columns(table_name)}


def _assert_upgrade_shape(bind) -> None:
    connection_columns = _columns(bind, "chatwoot_connections")
    binding_columns = _columns(bind, "sms_chatwoot_bindings")
    required_connection = {
        "id",
        "tenant_id",
        "instance_origin",
        "chatwoot_account_id",
        "signing_secret_ciphertext",
        "enabled",
    }
    required_binding = {"id", "tenant_id", "provider_id", "connection_id", "automation_enabled"}
    table_names = set(sa.inspect(bind).get_table_names())
    if (
        not required_connection <= connection_columns
        or not required_binding <= binding_columns
        or {"api_token_ciphertext", "outbound_enabled"} & connection_columns
        or "outbound_enabled" in binding_columns
        or "chatwoot_outbound_intents" in table_names
    ):
        raise RuntimeError("Chatwoot outbound migration found an unexpected table shape")


def _assert_downgrade_shape(bind) -> None:
    connection_columns = _columns(bind, "chatwoot_connections")
    binding_columns = _columns(bind, "sms_chatwoot_bindings")
    intent_columns = _columns(bind, "chatwoot_outbound_intents")
    if not {
        "api_token_ciphertext",
        "expected_integration_sender_type",
        "expected_integration_sender_id",
        "outbound_enabled",
    } <= connection_columns or "outbound_enabled" not in binding_columns or "message_id" not in intent_columns:
        raise RuntimeError("Chatwoot outbound downgrade found an unexpected table shape")


def _outbound_configuration_or_intent_exists(bind) -> bool:
    """Read only structural presence, never a credential or message value."""
    return bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM chatwoot_connections "
                "WHERE api_token_ciphertext IS NOT NULL "
                "OR expected_integration_sender_type IS NOT NULL "
                "OR expected_integration_sender_id IS NOT NULL "
                "OR outbound_enabled) "
                "OR EXISTS (SELECT 1 FROM sms_chatwoot_bindings WHERE outbound_enabled) "
                "OR EXISTS (SELECT 1 FROM chatwoot_outbound_intents)"
            )
        ).scalar_one()
    )


def upgrade() -> None:
    bind = _online_postgresql_bind()
    _assert_upgrade_shape(bind)
    op.execute(
        sa.text(
            "LOCK TABLE chatwoot_connections, sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE"
        )
    )
    _assert_upgrade_shape(bind)
    # PostgreSQL constant defaults preserve existing rows without data rewrite.
    op.add_column("chatwoot_connections", sa.Column("api_token_ciphertext", sa.String(length=4096), nullable=True))
    op.add_column("chatwoot_connections", sa.Column("expected_integration_sender_type", sa.String(length=64), nullable=True))
    op.add_column("chatwoot_connections", sa.Column("expected_integration_sender_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "chatwoot_connections",
        sa.Column("outbound_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "ck_chatwoot_connections_sender_positive",
        "chatwoot_connections",
        "expected_integration_sender_id IS NULL OR expected_integration_sender_id > 0",
    )
    op.add_column(
        "sms_chatwoot_bindings",
        sa.Column("outbound_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "chatwoot_outbound_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("outbound_correlation_id", sa.Uuid(), nullable=False),
        sa.Column("pre_send_cursor", sa.BigInteger(), nullable=True),
        sa.Column("remote_chatwoot_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("reconciliation_attempted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connection_id"], ["chatwoot_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["binding_id"], ["sms_chatwoot_bindings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["conversation_id"], ["sms_conversations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["message_id"], ["sms_messages.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("message_id", name="uq_chatwoot_outbound_intents_message"),
        sa.UniqueConstraint("outbound_correlation_id", name="uq_chatwoot_outbound_intents_correlation"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'SUCCEEDED', 'FAILED', 'OUTCOME_UNKNOWN', 'QUARANTINED')",
            name="ck_chatwoot_outbound_intents_status",
        ),
        sa.CheckConstraint("pre_send_cursor IS NULL OR pre_send_cursor > 0", name="ck_chatwoot_outbound_intents_cursor_positive"),
        sa.CheckConstraint("remote_chatwoot_message_id IS NULL OR remote_chatwoot_message_id > 0", name="ck_chatwoot_outbound_intents_remote_positive"),
    )
    for column in ("tenant_id", "provider_id", "connection_id", "binding_id", "conversation_id", "message_id", "status"):
        op.create_index(f"ix_chatwoot_outbound_intents_{column}", "chatwoot_outbound_intents", [column])


def downgrade() -> None:
    bind = _online_postgresql_bind()
    _assert_downgrade_shape(bind)
    op.execute(
        sa.text(
            "LOCK TABLE chatwoot_outbound_intents, chatwoot_connections, sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE"
        )
    )
    _assert_downgrade_shape(bind)
    if _outbound_configuration_or_intent_exists(bind):
        raise RuntimeError("Refusing downgrade because Chatwoot outbound configuration or intents exist")
    for column in ("tenant_id", "provider_id", "connection_id", "binding_id", "conversation_id", "message_id", "status"):
        op.drop_index(f"ix_chatwoot_outbound_intents_{column}", table_name="chatwoot_outbound_intents")
    op.drop_table("chatwoot_outbound_intents")
    op.drop_column("sms_chatwoot_bindings", "outbound_enabled")
    op.drop_constraint("ck_chatwoot_connections_sender_positive", "chatwoot_connections", type_="check")
    op.drop_column("chatwoot_connections", "outbound_enabled")
    op.drop_column("chatwoot_connections", "expected_integration_sender_id")
    op.drop_column("chatwoot_connections", "expected_integration_sender_type")
    op.drop_column("chatwoot_connections", "api_token_ciphertext")
