"""Add durable, tenant-safe webhook delivery records.

Revision ID: f2c0b8d9e7a1
Revises: e1b2c3d4e5f6
Create Date: 2026-09-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f2c0b8d9e7a1"
down_revision = "e1b2c3d4e5f6"
branch_labels = ("webhook_safety_remediation",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbox_event_id", sa.Integer(), sa.ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False),
        # Keep the event-recipient audit record if a registration is removed.
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("webhooks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("encrypted_signing_secret", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.UniqueConstraint("outbox_event_id", "webhook_id", name="uq_webhook_delivery_event_hook"),
    )
    op.create_index("ix_webhook_deliveries_outbox_event_id", "webhook_deliveries", ["outbox_event_id"])
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("ix_webhook_deliveries_tenant_id", "webhook_deliveries", ["tenant_id"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_lease_token", "webhook_deliveries", ["lease_token"])
    op.create_index("ix_webhook_deliveries_next_attempt_at", "webhook_deliveries", ["next_attempt_at"])
    op.add_column("outbox_events", sa.Column("webhook_snapshot_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("outbox_events", "webhook_snapshot_at")
    op.drop_index("ix_webhook_deliveries_next_attempt_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_lease_token", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_tenant_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_outbox_event_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
