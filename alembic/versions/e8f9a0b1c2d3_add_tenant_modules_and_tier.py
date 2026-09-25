"""add_tenant_modules_and_tier

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('subscription_tier', sa.String(), server_default='starter', nullable=False))
    op.add_column('tenants', sa.Column('addon_quota', sa.Integer(), server_default='0', nullable=False))
    op.add_column('tenants', sa.Column('enabled_modules', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'enabled_modules')
    op.drop_column('tenants', 'addon_quota')
    op.drop_column('tenants', 'subscription_tier')
