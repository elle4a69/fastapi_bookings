"""add booking slot allocations table and backfill active bookings

Revision ID: d9a1f4b2e8c1
Revises: 5f8f9989df0c
Create Date: 2026-08-29 04:50:00.000000

"""
from typing import Sequence, Union
from datetime import datetime, timezone, timedelta
from alembic import op
import sqlalchemy as sa


revision: str = 'd9a1f4b2e8c1'
down_revision: Union[str, None] = '5f8f9989df0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create booking_slot_allocations table
    op.create_table(
        'booking_slot_allocations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('booking_id', sa.Integer(), sa.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('slot_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
        sa.UniqueConstraint('provider_id', 'slot_start', name='uq_provider_slot_allocation'),
    )
    op.create_index('ix_slot_alloc_tenant_prov_start', 'booking_slot_allocations', ['tenant_id', 'provider_id', 'slot_start'])
    op.create_index(op.f('ix_booking_slot_allocations_booking_id'), 'booking_slot_allocations', ['booking_id'])
    op.create_index(op.f('ix_booking_slot_allocations_tenant_id'), 'booking_slot_allocations', ['tenant_id'])
    op.create_index(op.f('ix_booking_slot_allocations_provider_id'), 'booking_slot_allocations', ['provider_id'])

    # Backfill active bookings
    bind = op.get_bind()
    bookings = bind.execute(sa.text("SELECT id, tenant_id, provider_id, service_id, start_time, end_time, status FROM bookings WHERE CAST(status AS VARCHAR) NOT IN ('CANCELLED', 'cancelled')")).fetchall()
    
    for b in bookings:
        b_id, b_tenant, b_prov, b_svc, b_start, b_end, _ = b
        if isinstance(b_start, str):
            try:
                b_start = datetime.fromisoformat(b_start)
            except Exception:
                continue
        if isinstance(b_end, str):
            try:
                b_end = datetime.fromisoformat(b_end)
            except Exception:
                continue
        if b_start.tzinfo is None:
            b_start = b_start.replace(tzinfo=timezone.utc)
        if b_end.tzinfo is None:
            b_end = b_end.replace(tzinfo=timezone.utc)

        # 15m default buffer
        buf_before = 15
        buf_after = 15
        if b_svc:
            svc_row = bind.execute(sa.text(f"SELECT buffer_before, buffer_after FROM services WHERE id = {b_svc}")).fetchone()
            if svc_row:
                buf_before = max(15, svc_row[0] or 15)
                buf_after = max(15, svc_row[1] or 15)

        blocked_start = b_start - timedelta(minutes=buf_before)
        blocked_end = b_end + timedelta(minutes=buf_after)
        min_bucket = (blocked_start.minute // 15) * 15
        current_slot = blocked_start.replace(minute=min_bucket, second=0, microsecond=0)

        while current_slot < blocked_end:
            try:
                bind.execute(
                    sa.text("INSERT INTO booking_slot_allocations (tenant_id, booking_id, provider_id, slot_start, created_at) VALUES (:t, :b, :p, :s, :c)"),
                    {"t": b_tenant, "b": b_id, "p": b_prov, "s": current_slot, "c": datetime.now(timezone.utc)}
                )
            except Exception:
                # Ignore duplicate in backfill if any
                pass
            current_slot += timedelta(minutes=15)


def downgrade() -> None:
    op.drop_table('booking_slot_allocations')
