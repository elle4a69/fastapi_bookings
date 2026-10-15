"""wp0_platform_ownership_and_tenant_lifecycle

Revision ID: a2b3c4d5e6f8
Revises: 10251fbf7103
Create Date: 2026-10-15 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f8'
down_revision: Union[str, Sequence[str], None] = '10251fbf7103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Update users table
    if "users" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            if "is_platform_owner" not in existing_cols:
                batch_op.add_column(sa.Column("is_platform_owner", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "is_superuser" not in existing_cols:
                batch_op.add_column(sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()))
            # make tenant_id nullable for platform owners
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=True)

    # 2. Update tenants table
    if "tenants" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("tenants")}
        with op.batch_alter_table("tenants") as batch_op:
            if "status" not in existing_cols:
                batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
            if "suspended_at" not in existing_cols:
                batch_op.add_column(sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
            if "suspension_reason" not in existing_cols:
                batch_op.add_column(sa.Column("suspension_reason", sa.Text(), nullable=True))

    # 3. Create tenant_invitations table
    if "tenant_invitations" not in existing_tables:
        op.create_table(
            "tenant_invitations",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("email", sa.String(), index=True, nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="owner"),
            sa.Column("token", sa.String(length=128), unique=True, index=True, nullable=False),
            sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("token", name="uq_tenant_invitations_token"),
        )
        op.create_index(op.f("ix_tenant_invitations_id"), "tenant_invitations", ["id"], unique=False)
        op.create_index(op.f("ix_tenant_invitations_tenant_id"), "tenant_invitations", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_tenant_invitations_email"), "tenant_invitations", ["email"], unique=False)
        op.create_index(op.f("ix_tenant_invitations_token"), "tenant_invitations", ["token"], unique=True)

    # 4. Update audit_logs table (nullable tenant_id)
    if "audit_logs" in existing_tables:
        with op.batch_alter_table("audit_logs") as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "audit_logs" in existing_tables:
        with op.batch_alter_table("audit_logs") as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)

    if "tenant_invitations" in existing_tables:
        op.drop_table("tenant_invitations")

    if "tenants" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("tenants")}
        with op.batch_alter_table("tenants") as batch_op:
            if "suspension_reason" in existing_cols:
                batch_op.drop_column("suspension_reason")
            if "suspended_at" in existing_cols:
                batch_op.drop_column("suspended_at")
            if "status" in existing_cols:
                batch_op.drop_column("status")

    if "users" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
            if "is_superuser" in existing_cols:
                batch_op.drop_column("is_superuser")
            if "is_platform_owner" in existing_cols:
                batch_op.drop_column("is_platform_owner")
