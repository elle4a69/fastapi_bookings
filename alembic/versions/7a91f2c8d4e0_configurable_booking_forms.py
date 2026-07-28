"""configurable booking forms and tenant-safe relationships

Revision ID: 7a91f2c8d4e0
Revises: c4d31b16692d
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a91f2c8d4e0"
down_revision: Union[str, None] = "c4d31b16692d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_for_record(bind, relation: str, record_column: str, record_id: int) -> int:
    rows = bind.execute(
        sa.text(
            f"SELECT DISTINCT services.tenant_id FROM {relation} "
            f"JOIN services ON services.id = {relation}.service_id "
            f"WHERE {relation}.{record_column} = :record_id"
        ),
        {"record_id": record_id},
    ).fetchall()
    if len(rows) != 1:
        raise RuntimeError(
            f"Cannot determine one tenant for {record_column}={record_id}; "
            "resolve orphaned or cross-tenant legacy relationships before upgrading."
        )
    return int(rows[0][0])


def _backfill_owner(bind, table: str, relation: str, record_column: str) -> None:
    tenant_rows = bind.execute(sa.text("SELECT id FROM tenants ORDER BY id")).fetchall()
    sole_tenant = int(tenant_rows[0][0]) if len(tenant_rows) == 1 else None
    for (record_id,) in bind.execute(sa.text(f"SELECT id FROM {table}")):
        tenant_id = sole_tenant or _tenant_for_record(bind, relation, record_column, int(record_id))
        bind.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tenant_id WHERE id = :record_id"),
            {"tenant_id": tenant_id, "record_id": record_id},
        )


def upgrade() -> None:
    bind = op.get_bind()

    for table in ("categories", "products", "add_ons", "service_categories", "service_providers", "service_products"):
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))

    _backfill_owner(bind, "categories", "service_categories", "category_id")
    _backfill_owner(bind, "products", "service_products", "product_id")
    tenant_rows = bind.execute(sa.text("SELECT id FROM tenants ORDER BY id")).fetchall()
    sole_tenant = int(tenant_rows[0][0]) if len(tenant_rows) == 1 else None
    for add_on_id, service_id in bind.execute(sa.text("SELECT id, service_id FROM add_ons")):
        tenant_id = bind.execute(
            sa.text("SELECT tenant_id FROM services WHERE id = :service_id"), {"service_id": service_id}
        ).scalar()
        if tenant_id is None:
            if sole_tenant is None:
                raise RuntimeError(f"Cannot determine tenant for add-on {add_on_id}")
            tenant_id = sole_tenant
        bind.execute(
            sa.text("UPDATE add_ons SET tenant_id = :tenant_id WHERE id = :id"),
            {"tenant_id": tenant_id, "id": add_on_id},
        )

    for table in ("service_categories", "service_providers", "service_products"):
        bind.execute(
            sa.text(
                f"UPDATE {table} SET tenant_id = "
                f"(SELECT services.tenant_id FROM services WHERE services.id = {table}.service_id)"
            )
        )

    # Legacy routes allowed duplicate links. Preserve the oldest row before
    # adding database-level pair uniqueness.
    for table, left, right in (
        ("service_categories", "service_id", "category_id"),
        ("service_providers", "service_id", "provider_id"),
        ("service_products", "service_id", "product_id"),
        ("location_providers", "location_id", "provider_id"),
        ("location_services", "location_id", "service_id"),
        ("location_categories", "location_id", "category_id"),
    ):
        bind.execute(
            sa.text(
                f"DELETE FROM {table} WHERE id NOT IN "
                f"(SELECT MIN(id) FROM {table} GROUP BY tenant_id, {left}, {right})"
            )
        )

    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    specs = {
        "products": ("uq_products_tenant_sku", ["tenant_id", "sku"]),
        "service_categories": ("uq_service_categories_pair", ["tenant_id", "service_id", "category_id"]),
        "service_providers": ("uq_service_providers_pair", ["tenant_id", "service_id", "provider_id"]),
        "service_products": ("uq_service_products_pair", ["tenant_id", "service_id", "product_id"]),
    }
    for table in ("categories", "products", "add_ons", "service_categories", "service_providers", "service_products"):
        with op.batch_alter_table(table, naming_convention=naming) as batch:
            batch.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
            batch.create_index(f"ix_{table}_tenant_id", ["tenant_id"])
            batch.create_foreign_key(f"fk_{table}_tenant_id_tenants", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if table == "products":
                batch.drop_constraint("uq_products_sku", type_="unique")
            if table in specs:
                name, columns = specs[table]
                batch.create_unique_constraint(name, columns)

    op.create_table(
        "booking_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("module_order", sa.JSON(), nullable=False),
        sa.Column("enabled_modules", sa.JSON(), nullable=False),
        sa.Column("predefined_values", sa.JSON(), nullable=False),
        sa.Column("provider_selection_mode", sa.String(), nullable=False, server_default="required"),
        sa.Column("clear_session_on_start", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_switch_to_ada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("widget_type", sa.String(), nullable=False, server_default="inline"),
        sa.Column("appearance", sa.JSON(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_booking_forms_tenant_slug"),
    )
    op.create_index("ix_booking_forms_tenant_id", "booking_forms", ["tenant_id"])
    op.create_index("ix_booking_forms_slug", "booking_forms", ["slug"])

    for table, left, right, left_table, right_table in (
        ("provider_categories", "provider_id", "category_id", "providers", "categories"),
        ("location_products", "location_id", "product_id", "locations", "products"),
        ("service_add_ons", "service_id", "add_on_id", "services", "add_ons"),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column(left, sa.Integer(), nullable=False),
            sa.Column(right, sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint([left], [f"{left_table}.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint([right], [f"{right_table}.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("tenant_id", left, right, name=f"uq_{table}_pair"),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_index(f"ix_{table}_{left}", table, [left])
        op.create_index(f"ix_{table}_{right}", table, [right])

    bind.execute(
        sa.text(
            "INSERT INTO service_add_ons (tenant_id, service_id, add_on_id) "
            "SELECT tenant_id, service_id, id FROM add_ons"
        )
    )
    with op.batch_alter_table("add_ons") as batch:
        batch.drop_column("service_id")

    for table, left, right in (
        ("location_providers", "location_id", "provider_id"),
        ("location_services", "location_id", "service_id"),
        ("location_categories", "location_id", "category_id"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.create_unique_constraint(f"uq_{table}_pair", ["tenant_id", left, right])


def downgrade() -> None:
    op.add_column("add_ons", sa.Column("service_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE add_ons SET service_id = "
            "(SELECT service_id FROM service_add_ons WHERE service_add_ons.add_on_id = add_ons.id ORDER BY id LIMIT 1)"
        )
    )
    with op.batch_alter_table("add_ons") as batch:
        batch.alter_column("service_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_add_ons_service_id_services", "services", ["service_id"], ["id"])

    for table in ("service_add_ons", "location_products", "provider_categories", "booking_forms"):
        op.drop_table(table)

    for table, left, right in (
        ("location_providers", "location_id", "provider_id"),
        ("location_services", "location_id", "service_id"),
        ("location_categories", "location_id", "category_id"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"uq_{table}_pair", type_="unique")

    specs = {
        "products": "uq_products_tenant_sku",
        "service_categories": "uq_service_categories_pair",
        "service_providers": "uq_service_providers_pair",
        "service_products": "uq_service_products_pair",
    }
    for table in ("service_products", "service_providers", "service_categories", "add_ons", "products", "categories"):
        with op.batch_alter_table(table) as batch:
            if table in specs:
                batch.drop_constraint(specs[table], type_="unique")
            batch.drop_index(f"ix_{table}_tenant_id")
            batch.drop_column("tenant_id")
            if table == "products":
                batch.create_unique_constraint("uq_products_sku", ["sku"])
