"""Tenant-scoped booking idempotency and GDPR tenant isolation.

Revision ID: d4f6h8j0l2n4
Revises: c3e5g7i9k1m2
Create Date: 2026-10-01 20:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd4f6h8j0l2n4'
down_revision: Union[str, Sequence[str], None] = 'c3e5g7i9k1m2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "bookings" in existing_tables:
        indexes = {i["name"]: i for i in inspector.get_indexes("bookings")}
        uqs = {u["name"]: u for u in inspector.get_unique_constraints("bookings")}

        # 1. Drop existing unique index/constraint on idempotency_key if present
        if "ix_bookings_idempotency_key" in indexes:
            op.drop_index("ix_bookings_idempotency_key", table_name="bookings")
        elif "uq_bookings_idempotency_key" in uqs:
            op.drop_constraint("uq_bookings_idempotency_key", "bookings", type_="unique")

        # 2. Re-create non-unique index on idempotency_key
        op.create_index(
            "ix_bookings_idempotency_key",
            "bookings",
            ["idempotency_key"],
            unique=False,
        )

        # 3. Add composite unique constraint on (tenant_id, idempotency_key)
        if "uq_tenant_booking_idempotency" not in uqs:
            op.create_unique_constraint(
                "uq_tenant_booking_idempotency",
                "bookings",
                ["tenant_id", "idempotency_key"],
            )

    if "gdpr_consents" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("gdpr_consents")}
        indexes = {i["name"] for i in inspector.get_indexes("gdpr_consents")}

        if "tenant_id" not in cols:
            with op.batch_alter_table("gdpr_consents") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "tenant_id",
                        sa.Integer(),
                        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                        nullable=True,
                    )
                )

            # Backfill tenant_id from clients table if any exist
            op.execute(
                sa.text(
                    "UPDATE gdpr_consents "
                    "SET tenant_id = (SELECT tenant_id FROM clients WHERE clients.id = gdpr_consents.client_id) "
                    "WHERE tenant_id IS NULL"
                )
            )

            # Enforce non-nullable constraint
            with op.batch_alter_table("gdpr_consents") as batch_op:
                batch_op.alter_column("tenant_id", nullable=False)

        if "ix_gdpr_consents_tenant_id" not in indexes:
            op.create_index(
                "ix_gdpr_consents_tenant_id",
                "gdpr_consents",
                ["tenant_id"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "bookings" in existing_tables:
        uqs = {u["name"] for u in inspector.get_unique_constraints("bookings")}
        indexes = {i["name"] for i in inspector.get_indexes("bookings")}

        if "uq_tenant_booking_idempotency" in uqs:
            op.drop_constraint("uq_tenant_booking_idempotency", "bookings", type_="unique")

        if "ix_bookings_idempotency_key" in indexes:
            op.drop_index("ix_bookings_idempotency_key", table_name="bookings")

        op.create_index(
            "ix_bookings_idempotency_key",
            "bookings",
            ["idempotency_key"],
            unique=True,
        )

    if "gdpr_consents" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("gdpr_consents")}
        indexes = {i["name"] for i in inspector.get_indexes("gdpr_consents")}

        if "ix_gdpr_consents_tenant_id" in indexes:
            op.drop_index("ix_gdpr_consents_tenant_id", table_name="gdpr_consents")

        if "tenant_id" in cols:
            with op.batch_alter_table("gdpr_consents") as batch_op:
                batch_op.drop_column("tenant_id")
