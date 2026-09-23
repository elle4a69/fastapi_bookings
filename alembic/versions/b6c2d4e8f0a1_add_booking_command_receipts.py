"""Add tenant-scoped booking command receipts.

Revision ID: b6c2d4e8f0a1
Revises: d7e8f9a0b1c2
Create Date: 2026-09-24 00:00:00.000000

This revision deliberately descends from the committed ``d7e8f9a0b1c2`` head.
The untracked unsafe ``e8`` migration in the dirty main worktree is excluded;
integration must resolve that lineage separately before deployment.

No receipt is backfilled from audit data. Existing bookings with idempotency
keys therefore remain legacy records and fail closed on replay.
"""

from alembic import op
import sqlalchemy as sa


revision = "b6c2d4e8f0a1"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_index("ix_bookings_idempotency_key")
        batch_op.create_unique_constraint(
            "uq_bookings_tenant_id_id",
            ["tenant_id", "id"],
        )
        batch_op.create_unique_constraint(
            "uq_bookings_tenant_idempotency_key",
            ["tenant_id", "idempotency_key"],
        )

    op.create_table(
        "booking_command_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint_version", sa.Integer(), nullable=False),
        sa.Column("request_hmac", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "fingerprint_version >= 1",
            name="ck_booking_command_receipts_version",
        ),
        sa.CheckConstraint(
            "length(request_hmac) = 64",
            name="ck_booking_command_receipts_hmac_length",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "booking_id"],
            ["bookings.tenant_id", "bookings.id"],
            name="fk_booking_command_receipts_tenant_booking",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_booking_command_receipts_tenant_key",
        ),
        sa.UniqueConstraint(
            "booking_id",
            name="uq_booking_command_receipts_booking_id",
        ),
    )
    op.create_index(
        "ix_booking_command_receipts_id",
        "booking_command_receipts",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_booking_command_receipts_tenant_id",
        "booking_command_receipts",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_booking_command_receipts_tenant_id",
        table_name="booking_command_receipts",
    )
    op.drop_index(
        "ix_booking_command_receipts_id",
        table_name="booking_command_receipts",
    )
    op.drop_table("booking_command_receipts")

    # Restoring the historical global unique index will fail safely if two
    # tenants have used the same non-null key after this migration. Operators
    # must reconcile those rows before requesting a downgrade.
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint(
            "uq_bookings_tenant_idempotency_key",
            type_="unique",
        )
        batch_op.drop_constraint("uq_bookings_tenant_id_id", type_="unique")
        batch_op.create_index(
            "ix_bookings_idempotency_key",
            ["idempotency_key"],
            unique=True,
        )
