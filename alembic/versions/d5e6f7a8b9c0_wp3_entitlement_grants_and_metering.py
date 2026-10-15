"""wp3_entitlement_grants_and_metering

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create platform_entitlement_grants
    if "platform_entitlement_grants" not in existing_tables:
        op.create_table(
            "platform_entitlement_grants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entitlement_key", sa.String(length=128), nullable=False),
            sa.Column("value_type", sa.String(length=32), nullable=False, server_default="boolean"),
            sa.Column("granted_value", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(op.f("ix_platform_entitlement_grants_id"), "platform_entitlement_grants", ["id"], unique=False)
        op.create_index(op.f("ix_platform_entitlement_grants_tenant_id"), "platform_entitlement_grants", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_platform_entitlement_grants_entitlement_key"), "platform_entitlement_grants", ["entitlement_key"], unique=False)
        op.create_index(op.f("ix_platform_entitlement_grants_expires_at"), "platform_entitlement_grants", ["expires_at"], unique=False)
        op.create_index(op.f("ix_platform_entitlement_grants_granted_by_user_id"), "platform_entitlement_grants", ["granted_by_user_id"], unique=False)
        op.create_index(op.f("ix_platform_entitlement_grants_is_revoked"), "platform_entitlement_grants", ["is_revoked"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "platform_entitlement_grants" in existing_tables:
        op.drop_table("platform_entitlement_grants")
