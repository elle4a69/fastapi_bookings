"""Baseline bridge migration connecting e8f9a0b1c2d3 to existing b1c2d3e4f5a6 stamp.

Revision ID: b1c2d3e4f5a6
Revises: e8f9a0b1c2d3
Create Date: 2026-09-25 10:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline bridge: no-op migration to reconcile existing database stamp with alembic graph
    pass


def downgrade() -> None:
    pass
