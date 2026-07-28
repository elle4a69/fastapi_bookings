"""add_discovery_fields_to_tenant

Revision ID: ab69f4da7ff6
Revises: 7a91f2c8d4e0
Create Date: 2026-07-14 12:20:34.380715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab69f4da7ff6'
down_revision: Union[str, Sequence[str], None] = '7a91f2c8d4e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add discovery and location fields to the tenants table."""
    op.add_column('tenants', sa.Column('address', sa.String(), nullable=True))
    op.add_column('tenants', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('tenants', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('tenants', sa.Column('logo_url', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove discovery and location fields from the tenants table."""
    op.drop_column('tenants', 'logo_url')
    op.drop_column('tenants', 'longitude')
    op.drop_column('tenants', 'latitude')
    op.drop_column('tenants', 'address')
