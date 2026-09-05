"""Add the authenticated, tenant-scoped Chatwoot ingress data boundary.

Revision ID: a4c8e2f19b70
Revises: d7e8f9a0b1c2
Create Date: 2026-09-06 00:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "a4c8e2f19b70"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


_INTEGER_MIN = -(2**31)
_INTEGER_MAX = 2**31 - 1


def _online_postgresql_bind():
    if context.is_offline_mode():
        raise RuntimeError(
            "Chatwoot authenticated-ingress migration is online-only; "
            "migration DDL was not emitted"
        )
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Chatwoot authenticated-ingress migration requires PostgreSQL")
    return bind


def _column_map(inspector, table_name: str):
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _is_integer(column) -> bool:
    return isinstance(column["type"], sa.Integer) and not isinstance(
        column["type"], sa.BigInteger
    )


def _assert_upgrade_shape(bind) -> None:
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    required = {"sms_chatwoot_bindings", "sms_conversations", "sms_messages"}
    missing = required - tables
    if missing:
        raise RuntimeError("Chatwoot ingress migration found an unexpected table shape")
    if {"chatwoot_connections", "chatwoot_webhook_receipts"} & tables:
        raise RuntimeError("Chatwoot ingress migration found a partial target schema")

    expected = {
        "sms_chatwoot_bindings": {
            "id": (False, _is_integer),
            "tenant_id": (False, _is_integer),
            "provider_id": (False, _is_integer),
            "chatwoot_account_id": (False, _is_integer),
            "chatwoot_inbox_id": (False, _is_integer),
            "chatwoot_base_url": (False, lambda column: isinstance(column["type"], sa.String)),
            "chatwoot_api_token": (False, lambda column: isinstance(column["type"], sa.String)),
            "webhook_secret": (True, lambda column: isinstance(column["type"], sa.String)),
        },
        "sms_conversations": {
            "id": (False, _is_integer),
            "tenant_id": (False, _is_integer),
            "chatwoot_conversation_id": (True, _is_integer),
            "chatwoot_contact_id": (True, _is_integer),
            "chatwoot_inbox_id": (True, _is_integer),
        },
        "sms_messages": {
            "id": (False, _is_integer),
            "tenant_id": (False, _is_integer),
            "conversation_id": (False, _is_integer),
            "chatwoot_message_id": (True, _is_integer),
        },
    }
    forbidden_new_columns = {
        "sms_chatwoot_bindings": {"connection_id", "channel", "ingress_enabled"},
        "sms_conversations": {"chatwoot_binding_id"},
        "sms_messages": {
            "chatwoot_binding_id",
            "chatwoot_message_type",
            "chatwoot_content_type",
            "chatwoot_private",
            "chatwoot_sender_type",
            "chatwoot_sender_reference",
            "chatwoot_attachment_metadata",
        },
    }
    target_constraint_names = {
        "uq_sms_chatwoot_bindings_id_tenant",
        "uq_sms_chatwoot_bindings_connection_inbox",
        "fk_sms_chatwoot_bindings_connection_tenant",
        "ck_sms_chatwoot_bindings_inbox_positive",
        "ck_sms_chatwoot_bindings_account_positive",
        "ck_sms_chatwoot_bindings_legacy_or_connection",
        "uq_sms_conversations_binding_conversation",
        "uq_sms_conversations_id_chatwoot_binding",
        "fk_sms_conversations_chatwoot_binding_tenant",
        "ck_sms_conversations_chatwoot_conversation_positive",
        "ck_sms_conversations_chatwoot_contact_positive",
        "ck_sms_conversations_chatwoot_inbox_positive",
        "uq_sms_messages_binding_chatwoot_message",
        "fk_sms_messages_chatwoot_binding_tenant",
        "fk_sms_messages_conversation_chatwoot_binding",
        "ck_sms_messages_chatwoot_message_positive",
    }
    for table_name, columns in expected.items():
        actual = _column_map(inspector, table_name)
        if forbidden_new_columns[table_name] & set(actual):
            raise RuntimeError("Chatwoot ingress migration found a partial target schema")
        for name, (nullable, type_check) in columns.items():
            column = actual.get(name)
            if column is None or column["nullable"] is not nullable or not type_check(column):
                raise RuntimeError("Chatwoot ingress migration found an unexpected column shape")
        existing_names = {
            item.get("name")
            for collection in (
                inspector.get_unique_constraints(table_name),
                inspector.get_foreign_keys(table_name),
                inspector.get_check_constraints(table_name),
                inspector.get_indexes(table_name),
            )
            for item in collection
            if item.get("name")
        }
        if target_constraint_names & existing_names:
            raise RuntimeError("Chatwoot ingress migration found a partial target schema")


def _scalar_bool(bind, statement: str) -> bool:
    return bool(bind.execute(sa.text(statement)).scalar_one())


def _preflight_legacy_values(bind) -> None:
    nonpositive_checks = (
        (
            "sms_chatwoot_bindings",
            "chatwoot_account_id <= 0 OR chatwoot_inbox_id <= 0",
        ),
        (
            "sms_conversations",
            "(chatwoot_conversation_id IS NOT NULL AND chatwoot_conversation_id <= 0) "
            "OR (chatwoot_contact_id IS NOT NULL AND chatwoot_contact_id <= 0) "
            "OR (chatwoot_inbox_id IS NOT NULL AND chatwoot_inbox_id <= 0)",
        ),
        (
            "sms_messages",
            "chatwoot_message_id IS NOT NULL AND chatwoot_message_id <= 0",
        ),
    )
    for table_name, condition in nonpositive_checks:
        if _scalar_bool(
            bind, f"SELECT EXISTS (SELECT 1 FROM {table_name} WHERE {condition})"
        ):
            raise RuntimeError(
                "Chatwoot ingress migration found non-positive remote identifiers"
            )

def upgrade() -> None:
    bind = _online_postgresql_bind()
    _assert_upgrade_shape(bind)
    op.execute(
        sa.text(
            "LOCK TABLE sms_chatwoot_bindings, sms_conversations, sms_messages "
            "IN ACCESS EXCLUSIVE MODE"
        )
    )
    _assert_upgrade_shape(bind)
    _preflight_legacy_values(bind)

    op.create_table(
        "chatwoot_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("instance_origin", sa.String(length=2048), nullable=False),
        sa.Column("chatwoot_account_id", sa.BigInteger(), nullable=False),
        sa.Column("signing_secret_ciphertext", sa.String(length=4096), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chatwoot_account_id > 0",
            name="ck_chatwoot_connections_account_positive",
        ),
        sa.CheckConstraint(
            "length(instance_origin) BETWEEN 1 AND 2048",
            name="ck_chatwoot_connections_origin_length",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_chatwoot_connections_public_id"),
        sa.UniqueConstraint(
            "instance_origin",
            "chatwoot_account_id",
            name="uq_chatwoot_connections_origin_account",
        ),
        sa.UniqueConstraint(
            "id", "tenant_id", name="uq_chatwoot_connections_id_tenant"
        ),
    )
    op.create_index(
        "ix_chatwoot_connections_tenant_id",
        "chatwoot_connections",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "chatwoot_webhook_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("chatwoot_inbox_id", sa.BigInteger(), nullable=True),
        sa.Column("chatwoot_conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("chatwoot_message_id", sa.BigInteger(), nullable=True),
        sa.Column("webhook_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(event_type) BETWEEN 1 AND 64",
            name="ck_chatwoot_webhook_receipts_event_type_length",
        ),
        sa.CheckConstraint(
            "length(outcome) BETWEEN 1 AND 64",
            name="ck_chatwoot_webhook_receipts_outcome_length",
        ),
        sa.CheckConstraint(
            "chatwoot_inbox_id IS NULL OR chatwoot_inbox_id > 0",
            name="ck_chatwoot_webhook_receipts_inbox_positive",
        ),
        sa.CheckConstraint(
            "chatwoot_conversation_id IS NULL OR chatwoot_conversation_id > 0",
            name="ck_chatwoot_webhook_receipts_conversation_positive",
        ),
        sa.CheckConstraint(
            "chatwoot_message_id IS NULL OR chatwoot_message_id > 0",
            name="ck_chatwoot_webhook_receipts_message_positive",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["chatwoot_connections.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id",
            "delivery_id",
            name="uq_chatwoot_webhook_receipts_connection_delivery",
        ),
    )
    op.create_index(
        "ix_chatwoot_webhook_receipts_connection_id",
        "chatwoot_webhook_receipts",
        ["connection_id"],
        unique=False,
    )

    op.alter_column(
        "sms_chatwoot_bindings",
        "chatwoot_account_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        nullable=True,
    )
    op.alter_column(
        "sms_chatwoot_bindings",
        "chatwoot_inbox_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    for column_name in ("chatwoot_base_url", "chatwoot_api_token"):
        op.alter_column(
            "sms_chatwoot_bindings",
            column_name,
            existing_type=sa.String(),
            existing_nullable=False,
            nullable=True,
        )
    op.alter_column(
        "sms_chatwoot_bindings",
        "is_enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("false"),
    )
    op.add_column(
        "sms_chatwoot_bindings", sa.Column("connection_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "sms_chatwoot_bindings", sa.Column("channel", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "sms_chatwoot_bindings",
        sa.Column(
            "ingress_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sms_chatwoot_bindings_connection_id",
        "sms_chatwoot_bindings",
        ["connection_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_sms_chatwoot_bindings_id_tenant",
        "sms_chatwoot_bindings",
        ["id", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_sms_chatwoot_bindings_connection_inbox",
        "sms_chatwoot_bindings",
        ["connection_id", "chatwoot_inbox_id"],
    )
    op.create_foreign_key(
        "fk_sms_chatwoot_bindings_connection_tenant",
        "sms_chatwoot_bindings",
        "chatwoot_connections",
        ["connection_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_sms_chatwoot_bindings_inbox_positive",
        "sms_chatwoot_bindings",
        "chatwoot_inbox_id > 0",
    )
    op.create_check_constraint(
        "ck_sms_chatwoot_bindings_account_positive",
        "sms_chatwoot_bindings",
        "chatwoot_account_id IS NULL OR chatwoot_account_id > 0",
    )
    op.create_check_constraint(
        "ck_sms_chatwoot_bindings_legacy_or_connection",
        "sms_chatwoot_bindings",
        "(connection_id IS NULL AND channel IS NULL AND ingress_enabled = false) "
        "OR (connection_id IS NOT NULL AND channel = 'web_widget' "
        "AND is_enabled = false "
        "AND chatwoot_account_id IS NULL AND chatwoot_base_url IS NULL "
        "AND chatwoot_api_token IS NULL AND webhook_secret IS NULL)",
    )

    op.alter_column(
        "sms_conversations",
        "chatwoot_conversation_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "sms_conversations",
        "chatwoot_contact_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "sms_conversations",
        "chatwoot_inbox_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.add_column(
        "sms_conversations",
        sa.Column("chatwoot_binding_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sms_conversations_chatwoot_binding_id",
        "sms_conversations",
        ["chatwoot_binding_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_sms_conversations_binding_conversation",
        "sms_conversations",
        ["chatwoot_binding_id", "chatwoot_conversation_id"],
    )
    op.create_unique_constraint(
        "uq_sms_conversations_id_chatwoot_binding",
        "sms_conversations",
        ["id", "chatwoot_binding_id"],
    )
    op.create_foreign_key(
        "fk_sms_conversations_chatwoot_binding_tenant",
        "sms_conversations",
        "sms_chatwoot_bindings",
        ["chatwoot_binding_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    for name, condition in (
        (
            "ck_sms_conversations_chatwoot_conversation_positive",
            "chatwoot_conversation_id IS NULL OR chatwoot_conversation_id > 0",
        ),
        (
            "ck_sms_conversations_chatwoot_contact_positive",
            "chatwoot_contact_id IS NULL OR chatwoot_contact_id > 0",
        ),
        (
            "ck_sms_conversations_chatwoot_inbox_positive",
            "chatwoot_inbox_id IS NULL OR chatwoot_inbox_id > 0",
        ),
    ):
        op.create_check_constraint(name, "sms_conversations", condition)

    op.alter_column(
        "sms_messages",
        "chatwoot_message_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.add_column(
        "sms_messages",
        sa.Column("chatwoot_binding_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sms_messages_chatwoot_binding_id",
        "sms_messages",
        ["chatwoot_binding_id"],
        unique=False,
    )
    for column in (
        sa.Column("chatwoot_message_type", sa.String(length=32), nullable=True),
        sa.Column("chatwoot_content_type", sa.String(length=64), nullable=True),
        sa.Column("chatwoot_private", sa.Boolean(), nullable=True),
        sa.Column("chatwoot_sender_type", sa.String(length=64), nullable=True),
        sa.Column("chatwoot_sender_reference", sa.String(length=255), nullable=True),
        sa.Column("chatwoot_attachment_metadata", sa.JSON(), nullable=True),
    ):
        op.add_column("sms_messages", column)
    op.create_unique_constraint(
        "uq_sms_messages_binding_chatwoot_message",
        "sms_messages",
        ["chatwoot_binding_id", "chatwoot_message_id"],
    )
    op.create_foreign_key(
        "fk_sms_messages_chatwoot_binding_tenant",
        "sms_messages",
        "sms_chatwoot_bindings",
        ["chatwoot_binding_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_sms_messages_conversation_chatwoot_binding",
        "sms_messages",
        "sms_conversations",
        ["conversation_id", "chatwoot_binding_id"],
        ["id", "chatwoot_binding_id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_sms_messages_chatwoot_message_positive",
        "sms_messages",
        "chatwoot_message_id IS NULL OR chatwoot_message_id > 0",
    )


def _downgrade_has_package_b_data(bind) -> bool:
    checks = (
        "SELECT EXISTS (SELECT 1 FROM chatwoot_connections)",
        "SELECT EXISTS (SELECT 1 FROM chatwoot_webhook_receipts)",
        """
        SELECT EXISTS (
            SELECT 1 FROM sms_chatwoot_bindings
            WHERE connection_id IS NOT NULL OR channel IS NOT NULL OR ingress_enabled
        )
        """,
        "SELECT EXISTS (SELECT 1 FROM sms_conversations WHERE chatwoot_binding_id IS NOT NULL)",
        """
        SELECT EXISTS (
            SELECT 1 FROM sms_messages
            WHERE chatwoot_binding_id IS NOT NULL
               OR chatwoot_message_type IS NOT NULL
               OR chatwoot_content_type IS NOT NULL
               OR chatwoot_private IS NOT NULL
               OR chatwoot_sender_type IS NOT NULL
               OR chatwoot_sender_reference IS NOT NULL
               OR chatwoot_attachment_metadata IS NOT NULL
        )
        """,
    )
    return any(_scalar_bool(bind, statement) for statement in checks)


def _downgrade_values_fit_legacy_schema(bind) -> bool:
    if _scalar_bool(
        bind,
        """
        SELECT EXISTS (
            SELECT 1 FROM sms_chatwoot_bindings
            WHERE chatwoot_account_id IS NULL OR chatwoot_base_url IS NULL
               OR chatwoot_api_token IS NULL
        )
        """,
    ):
        return False

    columns = (
        ("sms_chatwoot_bindings", "chatwoot_account_id"),
        ("sms_chatwoot_bindings", "chatwoot_inbox_id"),
        ("sms_conversations", "chatwoot_conversation_id"),
        ("sms_conversations", "chatwoot_contact_id"),
        ("sms_conversations", "chatwoot_inbox_id"),
        ("sms_messages", "chatwoot_message_id"),
    )
    for table_name, column_name in columns:
        if _scalar_bool(
            bind,
            f"SELECT EXISTS (SELECT 1 FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL AND "
            f"({column_name} < {_INTEGER_MIN} OR {column_name} > {_INTEGER_MAX}))",
        ):
            return False
    return True


def downgrade() -> None:
    bind = _online_postgresql_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if not {"chatwoot_connections", "chatwoot_webhook_receipts"} <= tables:
        raise RuntimeError("Chatwoot ingress downgrade found an unexpected schema")
    op.execute(
        sa.text(
            "LOCK TABLE chatwoot_webhook_receipts, chatwoot_connections, "
            "sms_chatwoot_bindings, sms_conversations, sms_messages "
            "IN ACCESS EXCLUSIVE MODE"
        )
    )
    if _downgrade_has_package_b_data(bind):
        raise RuntimeError(
            "Refusing downgrade because Package B data or normalized metadata exists"
        )
    if not _downgrade_values_fit_legacy_schema(bind):
        raise RuntimeError(
            "Refusing downgrade because values do not fit the legacy schema"
        )

    op.drop_constraint(
        "ck_sms_messages_chatwoot_message_positive",
        "sms_messages",
        type_="check",
    )
    op.drop_constraint(
        "fk_sms_messages_conversation_chatwoot_binding",
        "sms_messages",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_sms_messages_chatwoot_binding_tenant",
        "sms_messages",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_sms_messages_binding_chatwoot_message",
        "sms_messages",
        type_="unique",
    )
    for column_name in (
        "chatwoot_attachment_metadata",
        "chatwoot_sender_reference",
        "chatwoot_sender_type",
        "chatwoot_private",
        "chatwoot_content_type",
        "chatwoot_message_type",
    ):
        op.drop_column("sms_messages", column_name)
    op.drop_index(
        "ix_sms_messages_chatwoot_binding_id", table_name="sms_messages"
    )
    op.drop_column("sms_messages", "chatwoot_binding_id")
    op.alter_column(
        "sms_messages",
        "chatwoot_message_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )

    for constraint_name in (
        "ck_sms_conversations_chatwoot_inbox_positive",
        "ck_sms_conversations_chatwoot_contact_positive",
        "ck_sms_conversations_chatwoot_conversation_positive",
    ):
        op.drop_constraint(constraint_name, "sms_conversations", type_="check")
    op.drop_constraint(
        "fk_sms_conversations_chatwoot_binding_tenant",
        "sms_conversations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_sms_conversations_binding_conversation",
        "sms_conversations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_sms_conversations_id_chatwoot_binding",
        "sms_conversations",
        type_="unique",
    )
    op.drop_index(
        "ix_sms_conversations_chatwoot_binding_id", table_name="sms_conversations"
    )
    op.drop_column("sms_conversations", "chatwoot_binding_id")
    for column_name in (
        "chatwoot_inbox_id",
        "chatwoot_contact_id",
        "chatwoot_conversation_id",
    ):
        op.alter_column(
            "sms_conversations",
            column_name,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=True,
        )

    for constraint_name in (
        "ck_sms_chatwoot_bindings_legacy_or_connection",
        "ck_sms_chatwoot_bindings_account_positive",
        "ck_sms_chatwoot_bindings_inbox_positive",
    ):
        op.drop_constraint(constraint_name, "sms_chatwoot_bindings", type_="check")
    op.drop_constraint(
        "fk_sms_chatwoot_bindings_connection_tenant",
        "sms_chatwoot_bindings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_sms_chatwoot_bindings_connection_inbox",
        "sms_chatwoot_bindings",
        type_="unique",
    )
    op.drop_constraint(
        "uq_sms_chatwoot_bindings_id_tenant",
        "sms_chatwoot_bindings",
        type_="unique",
    )
    op.drop_index(
        "ix_sms_chatwoot_bindings_connection_id",
        table_name="sms_chatwoot_bindings",
    )
    for column_name in ("ingress_enabled", "channel", "connection_id"):
        op.drop_column("sms_chatwoot_bindings", column_name)
    for column_name in ("chatwoot_base_url", "chatwoot_api_token"):
        op.alter_column(
            "sms_chatwoot_bindings",
            column_name,
            existing_type=sa.String(),
            existing_nullable=True,
            nullable=False,
        )
    op.alter_column(
        "sms_chatwoot_bindings",
        "is_enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("true"),
    )
    op.alter_column(
        "sms_chatwoot_bindings",
        "chatwoot_inbox_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "sms_chatwoot_bindings",
        "chatwoot_account_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )

    op.drop_index(
        "ix_chatwoot_webhook_receipts_connection_id",
        table_name="chatwoot_webhook_receipts",
    )
    op.drop_table("chatwoot_webhook_receipts")
    op.drop_index(
        "ix_chatwoot_connections_tenant_id", table_name="chatwoot_connections"
    )
    op.drop_table("chatwoot_connections")
