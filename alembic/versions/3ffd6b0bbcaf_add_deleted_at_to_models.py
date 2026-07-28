"""add_deleted_at_to_models

Revision ID: 3ffd6b0bbcaf
Revises: 989cd554d405
Create Date: 2026-07-10 09:57:13.148859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ffd6b0bbcaf'
down_revision: Union[str, Sequence[str], None] = '989cd554d405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. clients
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # 2. providers
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # 3. services
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # 4. bookings index
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.create_index('uq_active_bookings', ['provider_id', 'start_time'], unique=True, sqlite_where=sa.text("status != 'cancelled'"), postgresql_where=sa.text("status != 'CANCELLED'::bookingstatus"))

    # 5. holds index
    with op.batch_alter_table('holds', schema=None) as batch_op:
        batch_op.create_index('uq_pending_holds', ['provider_id', 'start_time'], unique=True, sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'PENDING'::holdstatus"))


def downgrade() -> None:
    with op.batch_alter_table('holds', schema=None) as batch_op:
        batch_op.drop_index('uq_pending_holds', sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'PENDING'::holdstatus"))

    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.drop_index('uq_active_bookings', sqlite_where=sa.text("status != 'cancelled'"), postgresql_where=sa.text("status != 'CANCELLED'::bookingstatus"))

    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
