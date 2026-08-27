"""add_sms_rate_limit_fields

Revision ID: 73647371c9bc
Revises: 62202d3e7aa6
Create Date: 2026-08-25 22:15:51.368893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73647371c9bc'
down_revision: Union[str, Sequence[str], None] = '62202d3e7aa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sms_accounts', sa.Column('throughput_limit', sa.Integer(), server_default='60', nullable=False))
    op.add_column('sms_accounts', sa.Column('quiet_hours_start', sa.String(), nullable=True))
    op.add_column('sms_accounts', sa.Column('quiet_hours_end', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sms_accounts', 'quiet_hours_end')
    op.drop_column('sms_accounts', 'quiet_hours_start')
    op.drop_column('sms_accounts', 'throughput_limit')
    # ### end Alembic commands ###
