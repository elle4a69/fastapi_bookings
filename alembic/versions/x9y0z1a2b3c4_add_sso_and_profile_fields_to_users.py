"""Add SSO and profile fields to users table

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-10-05 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'x9y0z1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'w8x9y0z1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            if "email" not in existing_cols:
                batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
                batch_op.create_index("ix_users_email", ["email"])
            if "google_sub" not in existing_cols:
                batch_op.add_column(sa.Column("google_sub", sa.String(), nullable=True))
                batch_op.create_index("ix_users_google_sub", ["google_sub"])
            if "chatwoot_user_id" not in existing_cols:
                batch_op.add_column(sa.Column("chatwoot_user_id", sa.Integer(), nullable=True))
                batch_op.create_index("ix_users_chatwoot_user_id", ["chatwoot_user_id"])
            if "first_name" not in existing_cols:
                batch_op.add_column(sa.Column("first_name", sa.String(), nullable=True))
            if "last_name" not in existing_cols:
                batch_op.add_column(sa.Column("last_name", sa.String(), nullable=True))
            if "avatar_url" not in existing_cols:
                batch_op.add_column(sa.Column("avatar_url", sa.String(), nullable=True))
            if "is_active" not in existing_cols:
                batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            if "is_active" in existing_cols:
                batch_op.drop_column("is_active")
            if "avatar_url" in existing_cols:
                batch_op.drop_column("avatar_url")
            if "last_name" in existing_cols:
                batch_op.drop_column("last_name")
            if "first_name" in existing_cols:
                batch_op.drop_column("first_name")
            if "chatwoot_user_id" in existing_cols:
                batch_op.drop_index("ix_users_chatwoot_user_id")
                batch_op.drop_column("chatwoot_user_id")
            if "google_sub" in existing_cols:
                batch_op.drop_index("ix_users_google_sub")
                batch_op.drop_column("google_sub")
            if "email" in existing_cols:
                batch_op.drop_index("ix_users_email")
                batch_op.drop_column("email")
