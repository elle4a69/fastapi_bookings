"""wp2_flexprice_billing_and_projections

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a9
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create billing_accounts
    if "billing_accounts" not in existing_tables:
        op.create_table(
            "billing_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("flexprice_customer_id", sa.String(length=128), nullable=True),
            sa.Column("billing_state", sa.String(length=32), nullable=False, server_default="unconfigured"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", name="uq_billing_accounts_tenant_id"),
        )
        op.create_index(op.f("ix_billing_accounts_id"), "billing_accounts", ["id"], unique=False)
        op.create_index(op.f("ix_billing_accounts_tenant_id"), "billing_accounts", ["tenant_id"], unique=True)
        op.create_index(op.f("ix_billing_accounts_flexprice_customer_id"), "billing_accounts", ["flexprice_customer_id"], unique=False)
        op.create_index(op.f("ix_billing_accounts_billing_state"), "billing_accounts", ["billing_state"], unique=False)

    # 2. Create subscription_projections
    if "subscription_projections" not in existing_tables:
        op.create_table(
            "subscription_projections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_subscription_id", sa.String(length=128), nullable=False),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_event_timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_event_sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("external_subscription_id", name="uq_subscription_projections_ext_sub_id"),
        )
        op.create_index(op.f("ix_subscription_projections_id"), "subscription_projections", ["id"], unique=False)
        op.create_index(op.f("ix_subscription_projections_tenant_id"), "subscription_projections", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_subscription_projections_external_subscription_id"), "subscription_projections", ["external_subscription_id"], unique=True)
        op.create_index(op.f("ix_subscription_projections_plan_id"), "subscription_projections", ["plan_id"], unique=False)
        op.create_index(op.f("ix_subscription_projections_status"), "subscription_projections", ["status"], unique=False)

    # 3. Create entitlement_snapshots
    if "entitlement_snapshots" not in existing_tables:
        op.create_table(
            "entitlement_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entitlement_key", sa.String(length=128), nullable=False),
            sa.Column("value_type", sa.String(length=32), nullable=False),
            sa.Column("value", sa.String(length=255), nullable=False),
            sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_subscription_id", sa.String(length=128), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "entitlement_key", name="uq_tenant_entitlement_key"),
        )
        op.create_index(op.f("ix_entitlement_snapshots_id"), "entitlement_snapshots", ["id"], unique=False)
        op.create_index(op.f("ix_entitlement_snapshots_tenant_id"), "entitlement_snapshots", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_entitlement_snapshots_entitlement_key"), "entitlement_snapshots", ["entitlement_key"], unique=False)
        op.create_index(op.f("ix_entitlement_snapshots_source_subscription_id"), "entitlement_snapshots", ["source_subscription_id"], unique=False)

    # 4. Create provider_event_inbox
    if "provider_event_inbox" not in existing_tables:
        op.create_table(
            "provider_event_inbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="flexprice"),
            sa.Column("external_event_id", sa.String(length=128), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("payload_digest", sa.String(length=64), nullable=False),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("provider", "external_event_id", name="uq_provider_event_inbox_provider_event"),
        )
        op.create_index(op.f("ix_provider_event_inbox_id"), "provider_event_inbox", ["id"], unique=False)
        op.create_index(op.f("ix_provider_event_inbox_provider"), "provider_event_inbox", ["provider"], unique=False)
        op.create_index(op.f("ix_provider_event_inbox_external_event_id"), "provider_event_inbox", ["external_event_id"], unique=False)
        op.create_index(op.f("ix_provider_event_inbox_event_type"), "provider_event_inbox", ["event_type"], unique=False)
        op.create_index(op.f("ix_provider_event_inbox_processing_status"), "provider_event_inbox", ["processing_status"], unique=False)

    # 5. Create usage_event_outbox
    if "usage_event_outbox" not in existing_tables:
        op.create_table(
            "usage_event_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("meter_key", sa.String(length=64), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("delivery_state", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("idempotency_key", name="uq_usage_event_outbox_idempotency_key"),
        )
        op.create_index(op.f("ix_usage_event_outbox_id"), "usage_event_outbox", ["id"], unique=False)
        op.create_index(op.f("ix_usage_event_outbox_tenant_id"), "usage_event_outbox", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_usage_event_outbox_idempotency_key"), "usage_event_outbox", ["idempotency_key"], unique=True)
        op.create_index(op.f("ix_usage_event_outbox_meter_key"), "usage_event_outbox", ["meter_key"], unique=False)
        op.create_index(op.f("ix_usage_event_outbox_delivery_state"), "usage_event_outbox", ["delivery_state"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "usage_event_outbox" in existing_tables:
        op.drop_table("usage_event_outbox")

    if "provider_event_inbox" in existing_tables:
        op.drop_table("provider_event_inbox")

    if "entitlement_snapshots" in existing_tables:
        op.drop_table("entitlement_snapshots")

    if "subscription_projections" in existing_tables:
        op.drop_table("subscription_projections")

    if "billing_accounts" in existing_tables:
        op.drop_table("billing_accounts")
