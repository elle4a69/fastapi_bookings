"""Expand support ticket contract with structured fields and authorisation state

Revision ID: v7w8x9y0z1a2
Revises: u5v6w7x8y9z0
Create Date: 2026-10-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'v7w8x9y0z1a2'
down_revision: Union[str, Sequence[str], None] = 'u5v6w7x8y9z0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_assistant_support_tickets" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("business_assistant_support_tickets")}
        with op.batch_alter_table("business_assistant_support_tickets") as batch_op:
            if "observed_behaviour" not in existing_cols:
                batch_op.add_column(sa.Column("observed_behaviour", sa.Text(), nullable=True))
            if "affected_product_area" not in existing_cols:
                batch_op.add_column(sa.Column("affected_product_area", sa.String(length=128), nullable=True))
                batch_op.create_index("ix_business_assistant_support_tickets_affected_area", ["affected_product_area"])
            if "user_impact" not in existing_cols:
                batch_op.add_column(sa.Column("user_impact", sa.Text(), nullable=True))
            if "acceptance_criteria" not in existing_cols:
                batch_op.add_column(sa.Column("acceptance_criteria", sa.Text(), nullable=True))
            if "authorisation_state" not in existing_cols:
                batch_op.add_column(
                    sa.Column("authorisation_state", sa.String(length=64), nullable=False, server_default="not_required")
                )
                batch_op.create_index("ix_business_assistant_support_tickets_authorisation_state", ["authorisation_state"])
            if "requires_owner_approval" not in existing_cols:
                batch_op.add_column(
                    sa.Column("requires_owner_approval", sa.Boolean(), nullable=False, server_default=sa.false())
                )
            if "resolution_summary" not in existing_cols:
                batch_op.add_column(sa.Column("resolution_summary", sa.Text(), nullable=True))
            if "coding_task_id" not in existing_cols:
                batch_op.add_column(sa.Column("coding_task_id", sa.String(length=128), nullable=True))
                batch_op.create_index("ix_business_assistant_support_tickets_coding_task_id", ["coding_task_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_assistant_support_tickets" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("business_assistant_support_tickets")}
        with op.batch_alter_table("business_assistant_support_tickets") as batch_op:
            if "coding_task_id" in existing_cols:
                batch_op.drop_index("ix_business_assistant_support_tickets_coding_task_id")
                batch_op.drop_column("coding_task_id")
            if "resolution_summary" in existing_cols:
                batch_op.drop_column("resolution_summary")
            if "requires_owner_approval" in existing_cols:
                batch_op.drop_column("requires_owner_approval")
            if "authorisation_state" in existing_cols:
                batch_op.drop_index("ix_business_assistant_support_tickets_authorisation_state")
                batch_op.drop_column("authorisation_state")
            if "acceptance_criteria" in existing_cols:
                batch_op.drop_column("acceptance_criteria")
            if "user_impact" in existing_cols:
                batch_op.drop_column("user_impact")
            if "affected_product_area" in existing_cols:
                batch_op.drop_index("ix_business_assistant_support_tickets_affected_area")
                batch_op.drop_column("affected_product_area")
            if "observed_behaviour" in existing_cols:
                batch_op.drop_column("observed_behaviour")
