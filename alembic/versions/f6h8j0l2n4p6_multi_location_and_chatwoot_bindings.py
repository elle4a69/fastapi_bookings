"""Multi-location relational topology and chatwoot binding refinements.

Revision ID: f6h8j0l2n4p6
Revises: e5g7i9k1m3o5
Create Date: 2026-10-01 22:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f6h8j0l2n4p6'
down_revision: Union[str, Sequence[str], None] = 'e5g7i9k1m3o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Update sms_chatwoot_bindings
    chatwoot_cols = {c["name"] for c in inspector.get_columns("sms_chatwoot_bindings")}
    if "location_id" not in chatwoot_cols:
        op.add_column(
            "sms_chatwoot_bindings",
            sa.Column("location_id", sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            "fk_sms_chatwoot_bindings_location_id_locations",
            "sms_chatwoot_bindings",
            "locations",
            ["location_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            "ix_sms_chatwoot_bindings_location_id",
            "sms_chatwoot_bindings",
            ["location_id"],
            unique=False,
        )

    # Make provider_id nullable for tenant/location dedicated inboxes
    with op.batch_alter_table("sms_chatwoot_bindings", schema=None) as batch_op:
        batch_op.alter_column(
            "provider_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    chatwoot_indices = {i["name"] for i in inspector.get_indexes("sms_chatwoot_bindings")}
    if "ix_sms_chatwoot_bindings_tenant_location" not in chatwoot_indices:
        op.create_index(
            "ix_sms_chatwoot_bindings_tenant_location",
            "sms_chatwoot_bindings",
            ["tenant_id", "location_id"],
            unique=False,
        )
    if "ix_sms_chatwoot_bindings_tenant_provider" not in chatwoot_indices:
        op.create_index(
            "ix_sms_chatwoot_bindings_tenant_provider",
            "sms_chatwoot_bindings",
            ["tenant_id", "provider_id"],
            unique=False,
        )

    # 2. Add composite indexes on location_providers
    loc_prov_indices = {i["name"] for i in inspector.get_indexes("location_providers")}
    if "ix_location_providers_location_provider" not in loc_prov_indices:
        op.create_index(
            "ix_location_providers_location_provider",
            "location_providers",
            ["location_id", "provider_id"],
            unique=False,
        )
    if "ix_location_providers_provider_location" not in loc_prov_indices:
        op.create_index(
            "ix_location_providers_provider_location",
            "location_providers",
            ["provider_id", "location_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    loc_prov_indices = {i["name"] for i in inspector.get_indexes("location_providers")}
    if "ix_location_providers_provider_location" in loc_prov_indices:
        op.drop_index("ix_location_providers_provider_location", table_name="location_providers")
    if "ix_location_providers_location_provider" in loc_prov_indices:
        op.drop_index("ix_location_providers_location_provider", table_name="location_providers")

    chatwoot_indices = {i["name"] for i in inspector.get_indexes("sms_chatwoot_bindings")}
    if "ix_sms_chatwoot_bindings_tenant_provider" in chatwoot_indices:
        op.drop_index("ix_sms_chatwoot_bindings_tenant_provider", table_name="sms_chatwoot_bindings")
    if "ix_sms_chatwoot_bindings_tenant_location" in chatwoot_indices:
        op.drop_index("ix_sms_chatwoot_bindings_tenant_location", table_name="sms_chatwoot_bindings")

    with op.batch_alter_table("sms_chatwoot_bindings", schema=None) as batch_op:
        batch_op.alter_column(
            "provider_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    if "ix_sms_chatwoot_bindings_location_id" in chatwoot_indices:
        op.drop_index("ix_sms_chatwoot_bindings_location_id", table_name="sms_chatwoot_bindings")

    chatwoot_fks = {fk["name"] for fk in inspector.get_foreign_keys("sms_chatwoot_bindings")}
    if "fk_sms_chatwoot_bindings_location_id_locations" in chatwoot_fks:
        op.drop_constraint("fk_sms_chatwoot_bindings_location_id_locations", "sms_chatwoot_bindings", type_="foreignkey")

    chatwoot_cols = {c["name"] for c in inspector.get_columns("sms_chatwoot_bindings")}
    if "location_id" in chatwoot_cols:
        op.drop_column("sms_chatwoot_bindings", "location_id")
