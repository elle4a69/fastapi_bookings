"""Add pgvector extension and HNSW cosine distance index.

Revision ID: j1k2m3n4p5q6
Revises: h8j0k2m4n6p8
Create Date: 2026-10-02 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1k2m3n4p5q6"
down_revision: Union[str, Sequence[str], None] = "h8j0k2m4n6p8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_curated_memories_embedding_hnsw "
            "ON curated_memories USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_curated_memories_embedding_hnsw;")
