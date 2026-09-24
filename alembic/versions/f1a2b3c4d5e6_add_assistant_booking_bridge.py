"""Add disabled-by-default Assistant UI booking bridge storage.

Revision ID: f1a2b3c4d5e6
Revises: d7e8f9a0b1c2
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("assistant_booking_bridge_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("line_key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("default_location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("credential_key_id", sa.String(length=96), nullable=False, unique=True),
        sa.Column("secret_verifier", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_bridge_binding_tenant", "assistant_booking_bridge_bindings", ["tenant_id"])
    op.create_index("ix_assistant_bridge_binding_provider", "assistant_booking_bridge_bindings", ["provider_id"])
    op.create_table("assistant_booking_bridge_nonces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce", sa.String(length=96), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("binding_id", "nonce", name="uq_assistant_bridge_nonce"),
    )
    op.create_index("ix_assistant_bridge_nonce_binding", "assistant_booking_bridge_nonces", ["binding_id"])
    op.create_index("ix_assistant_bridge_nonce_expiry", "assistant_booking_bridge_nonces", ["expires_at"])
    op.create_table("assistant_booking_bridge_proposals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_assistant_bridge_proposal_binding", "assistant_booking_bridge_proposals", ["binding_id"])
    op.create_index("ix_assistant_bridge_proposal_expiry", "assistant_booking_bridge_proposals", ["expires_at"])
    op.create_table("assistant_booking_bridge_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(length=96), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("binding_id", "request_id", name="uq_assistant_bridge_receipt"),
    )
    op.create_index("ix_assistant_bridge_receipt_binding", "assistant_booking_bridge_receipts", ["binding_id"])


def downgrade():
    op.drop_table("assistant_booking_bridge_receipts")
    op.drop_table("assistant_booking_bridge_proposals")
    op.drop_table("assistant_booking_bridge_nonces")
    op.drop_table("assistant_booking_bridge_bindings")
