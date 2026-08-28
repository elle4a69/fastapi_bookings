"""Audit and repair booking slot allocation backfill integrity.

Revision ID: e1b2c3d4e5f6
Revises: d9a1f4b2e8c1
Create Date: 2026-08-29 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = 'e1b2c3d4e5f6'
down_revision = 'd9a1f4b2e8c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Execute audit and repair of slot allocations for all active bookings."""
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        from app.services.slot_allocation_service import audit_and_repair_slot_allocations
        result = audit_and_repair_slot_allocations(session, dry_run=False)
        print(f"[Alembic Migration] Slot allocation integrity audit and repair completed: {result.to_dict()}")
    finally:
        session.close()


def downgrade() -> None:
    """No structural changes to rollback."""
    pass
