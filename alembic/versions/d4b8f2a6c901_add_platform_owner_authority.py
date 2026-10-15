"""add persisted platform-owner authority

Revision ID: d4b8f2a6c901
Revises: 10251fbf7103
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b8f2a6c901"
down_revision: Union[str, Sequence[str], None] = "10251fbf7103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the fail-closed persisted platform-owner capability."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_platform_owner",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(
            "ix_users_platform_owner_active",
            ["is_platform_owner", "is_active"],
            unique=False,
        )


def downgrade() -> None:
    """Remove the capability after application rollback and owner approval."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_platform_owner_active")
        batch_op.drop_column("is_platform_owner")
