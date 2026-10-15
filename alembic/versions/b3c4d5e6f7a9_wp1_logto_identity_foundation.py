"""wp1_logto_identity_foundation

Revision ID: b3c4d5e6f7a9
Revises: a2b3c4d5e6f8
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a9'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create external_identity_links
    if "external_identity_links" not in existing_tables:
        op.create_table(
            "external_identity_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="logto"),
            sa.Column("external_subject_id", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("provider", "external_subject_id", name="uq_external_identity_provider_subject"),
        )
        op.create_index(op.f("ix_external_identity_links_id"), "external_identity_links", ["id"], unique=False)
        op.create_index(op.f("ix_external_identity_links_provider"), "external_identity_links", ["provider"], unique=False)
        op.create_index(op.f("ix_external_identity_links_external_subject_id"), "external_identity_links", ["external_subject_id"], unique=False)
        op.create_index(op.f("ix_external_identity_links_user_id"), "external_identity_links", ["user_id"], unique=False)
        op.create_index(op.f("ix_external_identity_links_email"), "external_identity_links", ["email"], unique=False)

    # 2. Create external_organization_links
    if "external_organization_links" not in existing_tables:
        op.create_table(
            "external_organization_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="logto"),
            sa.Column("external_organization_id", sa.String(length=128), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provisioning_state", sa.String(length=32), nullable=False, server_default="provisioned"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("provider", "external_organization_id", name="uq_external_org_provider_org_id"),
            sa.UniqueConstraint("provider", "tenant_id", name="uq_external_org_provider_tenant_id"),
        )
        op.create_index(op.f("ix_external_organization_links_id"), "external_organization_links", ["id"], unique=False)
        op.create_index(op.f("ix_external_organization_links_provider"), "external_organization_links", ["provider"], unique=False)
        op.create_index(op.f("ix_external_organization_links_external_organization_id"), "external_organization_links", ["external_organization_id"], unique=False)
        op.create_index(op.f("ix_external_organization_links_tenant_id"), "external_organization_links", ["tenant_id"], unique=False)

    # 3. Create identity_outbox_events
    if "identity_outbox_events" not in existing_tables:
        op.create_table(
            "identity_outbox_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("idempotency_key", name="uq_identity_outbox_events_idempotency_key"),
        )
        op.create_index(op.f("ix_identity_outbox_events_id"), "identity_outbox_events", ["id"], unique=False)
        op.create_index(op.f("ix_identity_outbox_events_tenant_id"), "identity_outbox_events", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_identity_outbox_events_user_id"), "identity_outbox_events", ["user_id"], unique=False)
        op.create_index(op.f("ix_identity_outbox_events_event_type"), "identity_outbox_events", ["event_type"], unique=False)
        op.create_index(op.f("ix_identity_outbox_events_status"), "identity_outbox_events", ["status"], unique=False)
        op.create_index(op.f("ix_identity_outbox_events_idempotency_key"), "identity_outbox_events", ["idempotency_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "identity_outbox_events" in existing_tables:
        op.drop_table("identity_outbox_events")

    if "external_organization_links" in existing_tables:
        op.drop_table("external_organization_links")

    if "external_identity_links" in existing_tables:
        op.drop_table("external_identity_links")
