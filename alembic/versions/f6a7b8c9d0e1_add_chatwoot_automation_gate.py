"""Add the disabled-by-default Chatwoot automation policy gate.

Revision ID: f6a7b8c9d0e1
Revises: a4c8e2f19b70
Create Date: 2026-09-06 02:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "a4c8e2f19b70"
branch_labels = None
depends_on = None


def _online_postgresql_bind():
    if context.is_offline_mode():
        raise RuntimeError(
            "Chatwoot processing migration is online-only; migration DDL was not emitted"
        )
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Chatwoot processing migration requires PostgreSQL")
    return bind


def _column_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    if "sms_chatwoot_bindings" not in set(inspector.get_table_names()):
        raise RuntimeError("Chatwoot processing migration found an unexpected table shape")
    return {column["name"] for column in inspector.get_columns("sms_chatwoot_bindings")}


def _assert_upgrade_shape(bind) -> None:
    columns = _column_names(bind)
    required = {"id", "connection_id", "ingress_enabled", "channel"}
    if not required <= columns or "automation_enabled" in columns:
        raise RuntimeError("Chatwoot processing migration found an unexpected table shape")


def _assert_downgrade_shape(bind) -> None:
    columns = _column_names(bind)
    if "automation_enabled" not in columns:
        raise RuntimeError("Chatwoot processing downgrade found an unexpected table shape")


def _automation_is_enabled(bind) -> bool:
    # Deliberately structural only: this reads no tenant, customer, message, or
    # credential data before deciding whether a destructive downgrade is safe.
    return bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM sms_chatwoot_bindings "
                "WHERE automation_enabled)"
            )
        ).scalar_one()
    )


def upgrade() -> None:
    bind = _online_postgresql_bind()
    _assert_upgrade_shape(bind)
    op.execute(sa.text("LOCK TABLE sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE"))
    _assert_upgrade_shape(bind)
    # PostgreSQL constant defaults preserve existing rows without an UPDATE.
    op.add_column(
        "sms_chatwoot_bindings",
        sa.Column(
            "automation_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    bind = _online_postgresql_bind()
    _assert_downgrade_shape(bind)
    op.execute(sa.text("LOCK TABLE sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE"))
    _assert_downgrade_shape(bind)
    if _automation_is_enabled(bind):
        raise RuntimeError(
            "Refusing downgrade because Chatwoot automation configuration exists"
        )
    op.drop_column("sms_chatwoot_bindings", "automation_enabled")
