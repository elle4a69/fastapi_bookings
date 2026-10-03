"""Add sms_bootcamp_message status column.

Revision ID: k2m3n4p5q6r7
Revises: j1k2m3n4p5q6
Create Date: 2026-10-02 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k2m3n4p5q6r7"
down_revision: Union[str, Sequence[str], None] = "j1k2m3n4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sms_bootcamp_messages",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("sms_bootcamp_messages", "status")
