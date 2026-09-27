"""Add incall/outcall capabilities, service mode, travel charges, and location privacy schema.

Revision ID: c5e6f7a8b9c0
Revises: b2c3d4e5f6a7
Create Date: 2026-09-27 14:20:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = 'c5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Tenants table updates
    if "tenants" in existing_tables:
        tenant_cols = {c["name"] for c in inspector.get_columns("tenants")}
        with op.batch_alter_table("tenants") as batch_op:
            if "allow_in_call" not in tenant_cols:
                batch_op.add_column(sa.Column("allow_in_call", sa.Boolean(), nullable=False, server_default=sa.true()))
            if "allow_out_call" not in tenant_cols:
                batch_op.add_column(sa.Column("allow_out_call", sa.Boolean(), nullable=False, server_default=sa.true()))
            if "travel_charge_origin" not in tenant_cols:
                batch_op.add_column(sa.Column("travel_charge_origin", sa.String(), nullable=False, server_default="ALWAYS_FROM_BASE"))

    # 2. Providers table updates
    if "providers" in existing_tables:
        provider_cols = {c["name"] for c in inspector.get_columns("providers")}
        with op.batch_alter_table("providers") as batch_op:
            if "allow_in_call" not in provider_cols:
                batch_op.add_column(sa.Column("allow_in_call", sa.Boolean(), nullable=False, server_default=sa.true()))
            if "allow_out_call" not in provider_cols:
                batch_op.add_column(sa.Column("allow_out_call", sa.Boolean(), nullable=False, server_default=sa.true()))

    # 3. Services table updates
    if "services" in existing_tables:
        service_cols = {c["name"] for c in inspector.get_columns("services")}
        with op.batch_alter_table("services") as batch_op:
            if "outcall_price" not in service_cols:
                batch_op.add_column(sa.Column("outcall_price", sa.Numeric(precision=10, scale=2), nullable=True))
            if "outcall_buffer_before" not in service_cols:
                batch_op.add_column(sa.Column("outcall_buffer_before", sa.Integer(), nullable=False, server_default="0"))
            if "outcall_buffer_after" not in service_cols:
                batch_op.add_column(sa.Column("outcall_buffer_after", sa.Integer(), nullable=False, server_default="0"))

        # Default existing services outcall_price to price where allow_out_call is true
        try:
            op.execute(
                sa.text(
                    "UPDATE services SET outcall_price = price "
                    "WHERE (allow_out_call = 1 OR allow_out_call = true) AND outcall_price IS NULL"
                )
            )
        except Exception:
            # Tolerant if dialect has different boolean representation
            pass

    # 4. Locations table updates
    if "locations" in existing_tables:
        location_cols = {c["name"] for c in inspector.get_columns("locations")}
        with op.batch_alter_table("locations") as batch_op:
            if "is_client_hidden" not in location_cols:
                batch_op.add_column(sa.Column("is_client_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))

    # 5. Bookings table updates
    if "bookings" in existing_tables:
        booking_cols = {c["name"] for c in inspector.get_columns("bookings")}
        with op.batch_alter_table("bookings") as batch_op:
            if "service_mode" not in booking_cols:
                batch_op.add_column(sa.Column("service_mode", sa.String(), nullable=False, server_default="in_call"))
            if "client_suburb" not in booking_cols:
                batch_op.add_column(sa.Column("client_suburb", sa.String(), nullable=True))
            if "client_postcode" not in booking_cols:
                batch_op.add_column(sa.Column("client_postcode", sa.String(), nullable=True))
            if "service_address" not in booking_cols:
                batch_op.add_column(sa.Column("service_address", sa.String(), nullable=True))
            if "chargeable_travel_distance_km" not in booking_cols:
                batch_op.add_column(sa.Column("chargeable_travel_distance_km", sa.Float(), nullable=True))
            if "chargeable_travel_fee" not in booking_cols:
                batch_op.add_column(sa.Column("chargeable_travel_fee", sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 5. Bookings table rollback
    if "bookings" in existing_tables:
        booking_cols = {c["name"] for c in inspector.get_columns("bookings")}
        with op.batch_alter_table("bookings") as batch_op:
            for col in (
                "chargeable_travel_fee",
                "chargeable_travel_distance_km",
                "service_address",
                "client_postcode",
                "client_suburb",
                "service_mode",
            ):
                if col in booking_cols:
                    batch_op.drop_column(col)

    # 4. Locations table rollback
    if "locations" in existing_tables:
        location_cols = {c["name"] for c in inspector.get_columns("locations")}
        with op.batch_alter_table("locations") as batch_op:
            if "is_client_hidden" in location_cols:
                batch_op.drop_column("is_client_hidden")

    # 3. Services table rollback
    if "services" in existing_tables:
        service_cols = {c["name"] for c in inspector.get_columns("services")}
        with op.batch_alter_table("services") as batch_op:
            for col in ("outcall_buffer_after", "outcall_buffer_before", "outcall_price"):
                if col in service_cols:
                    batch_op.drop_column(col)

    # 2. Providers table rollback
    if "providers" in existing_tables:
        provider_cols = {c["name"] for c in inspector.get_columns("providers")}
        with op.batch_alter_table("providers") as batch_op:
            for col in ("allow_out_call", "allow_in_call"):
                if col in provider_cols:
                    batch_op.drop_column(col)

    # 1. Tenants table rollback
    if "tenants" in existing_tables:
        tenant_cols = {c["name"] for c in inspector.get_columns("tenants")}
        with op.batch_alter_table("tenants") as batch_op:
            for col in ("travel_charge_origin", "allow_out_call", "allow_in_call"):
                if col in tenant_cols:
                    batch_op.drop_column(col)
