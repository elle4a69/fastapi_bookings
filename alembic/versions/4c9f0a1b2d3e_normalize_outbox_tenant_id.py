"""Normalize outbox tenant identifiers and enforce tenant integrity.

Revision ID: 4c9f0a1b2d3e
Revises: f2c0b8d9e7a1
Create Date: 2026-09-05 00:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "4c9f0a1b2d3e"
down_revision = "f2c0b8d9e7a1"
branch_labels = None
depends_on = None


_INVALID_TENANT_IDS = sa.text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM outbox_events
        WHERE tenant_id IS NOT NULL
          AND NOT (
              CASE
                  WHEN tenant_id::text ~ '^[1-9][0-9]*$'
                  THEN (tenant_id::text)::numeric BETWEEN 1 AND 2147483647
                  ELSE FALSE
              END
          )
    )
    """
)

_ORPHAN_TENANT_IDS = sa.text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM outbox_events AS event
        LEFT JOIN tenants AS tenant
          ON tenant.id = (event.tenant_id::text)::integer
        WHERE event.tenant_id IS NOT NULL
          AND tenant.id IS NULL
    )
    """
)


def _require_online_mode() -> None:
    try:
        is_offline = context.is_offline_mode()
    except NameError:
        # Allows direct unit invocation outside an Alembic EnvironmentContext.
        is_offline = False
    if is_offline:
        raise RuntimeError(
            "outbox tenant normalization is online-only; migration DDL was not emitted"
        )


def _column_kind(inspector) -> str:
    tenant_columns = [
        column
        for column in inspector.get_columns("outbox_events")
        if column["name"] == "tenant_id"
    ]
    if len(tenant_columns) != 1:
        raise RuntimeError(
            "outbox tenant normalization blocked: tenant_id column shape is unexpected"
        )

    type_name = type(tenant_columns[0]["type"]).__name__.upper()
    if type_name in {"VARCHAR", "TEXT"}:
        return "text"
    if type_name == "INTEGER":
        return "integer"
    raise RuntimeError(
        "outbox tenant normalization blocked: tenant_id column type is unexpected"
    )


def _tenant_foreign_key(inspector):
    tenant_foreign_keys = [
        foreign_key
        for foreign_key in inspector.get_foreign_keys("outbox_events")
        if "tenant_id" in foreign_key.get("constrained_columns", [])
    ]
    if not tenant_foreign_keys:
        return None
    if len(tenant_foreign_keys) != 1:
        raise RuntimeError(
            "outbox tenant normalization blocked: tenant_id constraints are unexpected"
        )

    foreign_key = tenant_foreign_keys[0]
    options = foreign_key.get("options") or {}
    ondelete = options.get("ondelete") or foreign_key.get("ondelete")
    referred_schema = foreign_key.get("referred_schema")
    default_schema = getattr(inspector, "default_schema_name", None)
    is_exact = (
        foreign_key.get("constrained_columns") == ["tenant_id"]
        and foreign_key.get("referred_table") == "tenants"
        and foreign_key.get("referred_columns") == ["id"]
        and referred_schema in {None, default_schema}
        and isinstance(ondelete, str)
        and ondelete.upper() == "CASCADE"
        and bool(foreign_key.get("name"))
    )
    if not is_exact:
        raise RuntimeError(
            "outbox tenant normalization blocked: tenant_id constraint is unexpected"
        )
    return foreign_key


def _inspect_shape(bind: sa.engine.Connection) -> tuple[str, dict | None]:
    inspector = sa.inspect(bind)
    column_kind = _column_kind(inspector)
    foreign_key = _tenant_foreign_key(inspector)
    if column_kind == "text" and foreign_key is not None:
        raise RuntimeError(
            "outbox tenant normalization blocked: text tenant_id has an unexpected constraint"
        )
    return column_kind, foreign_key


def _assert_safe_tenant_ids(bind: sa.engine.Connection) -> tuple[str, dict | None]:
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "outbox tenant normalization requires PostgreSQL and was not applied"
        )

    # Prevent tenant or outbox writes between validation, conversion, and FK creation.
    bind.execute(sa.text("LOCK TABLE tenants, outbox_events IN ACCESS EXCLUSIVE MODE"))
    column_kind, foreign_key = _inspect_shape(bind)

    if bind.execute(_INVALID_TENANT_IDS).scalar_one():
        raise RuntimeError(
            "outbox tenant normalization blocked: invalid non-null tenant identifiers exist"
        )

    if bind.execute(_ORPHAN_TENANT_IDS).scalar_one():
        raise RuntimeError(
            "outbox tenant normalization blocked: orphan non-null tenant identifiers exist"
        )
    return column_kind, foreign_key


def upgrade() -> None:
    _require_online_mode()
    bind = op.get_bind()
    column_kind, foreign_key = _assert_safe_tenant_ids(bind)

    if column_kind == "text":
        op.alter_column(
            "outbox_events",
            "tenant_id",
            existing_type=sa.String(),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using="tenant_id::integer",
        )
    if foreign_key is None:
        op.create_foreign_key(
            "fk_outbox_events_tenant_id",
            "outbox_events",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    _require_online_mode()
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "outbox tenant normalization downgrade requires PostgreSQL and was not applied"
        )

    bind.execute(sa.text("LOCK TABLE tenants, outbox_events IN ACCESS EXCLUSIVE MODE"))
    column_kind, foreign_key = _inspect_shape(bind)
    if foreign_key is not None:
        op.drop_constraint(
            foreign_key["name"],
            "outbox_events",
            type_="foreignkey",
        )
    if column_kind == "integer":
        op.alter_column(
            "outbox_events",
            "tenant_id",
            existing_type=sa.Integer(),
            type_=sa.String(),
            existing_nullable=True,
            postgresql_using="tenant_id::text",
        )
