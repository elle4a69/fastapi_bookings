"""Add knowledge_graph_projections table and indices.

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-09-25 12:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if "knowledge_graph_projections" not in existing_tables:
        op.create_table(
            "knowledge_graph_projections",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("learning_event_id", sa.String(36), sa.ForeignKey("learning_events.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("curated_memory_id", sa.Integer(), sa.ForeignKey("curated_memories.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("projection_type", sa.String(50), nullable=False),
            sa.Column("graph_group_id", sa.String(100), nullable=False, index=True),
            sa.Column("graph_episode_uuid", sa.String(100), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending", index=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column("lease_owner", sa.String(100), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("projection_version", sa.String(20), nullable=False, server_default="1.0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("learning_event_id", "projection_type", name="uq_kgp_event_type"),
        )
        op.create_index(
            "ix_kgp_claim",
            "knowledge_graph_projections",
            ["status", "next_attempt_at", "tenant_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if "knowledge_graph_projections" in existing_tables:
        op.drop_index("ix_kgp_claim", table_name="knowledge_graph_projections")
        op.drop_table("knowledge_graph_projections")
