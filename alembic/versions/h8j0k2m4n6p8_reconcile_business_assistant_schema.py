"""Reconcile pre-existing Business Assistant persistence tables safely.

Revision ID: h8j0k2m4n6p8
Revises: g7h9j1k3m5n7
Create Date: 2026-10-02 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8j0k2m4n6p8"
down_revision: Union[str, Sequence[str], None] = "g7h9j1k3m5n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_NAME = "business_assistant_conversations"
_REQUIRED_COLUMNS = {
    "tenant_id": sa.Column("tenant_id", sa.Integer(), nullable=False),
    "user_id": sa.Column("user_id", sa.Integer(), nullable=False),
    "title": sa.Column("title", sa.String(length=160), nullable=True),
    "status": sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    "creation_request_key": sa.Column("creation_request_key", sa.String(length=128), nullable=True),
    "creation_payload_hash": sa.Column("creation_payload_hash", sa.String(length=64), nullable=True),
    "created_at": sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
}


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_missing_foundation_tables() -> None:
    """Create absent foundation tables using the original additive revision."""
    import importlib.util
    from pathlib import Path

    foundation_path = Path(__file__).with_name("g7h9j1k3m5n7_add_business_assistant_foundation.py")
    spec = importlib.util.spec_from_file_location("business_assistant_foundation_reconciliation", foundation_path)
    if not spec or not spec.loader:
        raise RuntimeError("The Business Assistant foundation migration is unavailable for reconciliation.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()


def _add_unique_constraint(name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE_NAME) as batch:
            batch.create_unique_constraint(name, columns)
    else:
        op.create_unique_constraint(name, _TABLE_NAME, columns)


def upgrade() -> None:
    """Add missing foundation storage and conversation idempotency fields without reset."""
    if any(table not in _existing_tables() for table in (
        "business_assistant_conversations",
        "business_assistant_messages",
        "business_assistant_tool_runs",
        "business_assistant_memories",
        "business_assistant_onboarding_progress",
        "business_assistant_support_tickets",
        "business_assistant_active_ticket_claims",
        "business_assistant_support_ticket_events",
    )):
        _create_missing_foundation_tables()

    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns(_TABLE_NAME)}
    for name, column in _REQUIRED_COLUMNS.items():
        if name not in existing_columns:
            op.add_column(_TABLE_NAME, column)

    inspector = sa.inspect(op.get_bind())
    unique_names = {item.get("name") for item in inspector.get_unique_constraints(_TABLE_NAME)}
    index_names = {item.get("name") for item in inspector.get_indexes(_TABLE_NAME)}
    if "uq_business_assistant_conversation_creation_key" not in unique_names and "uq_business_assistant_conversation_creation_key" not in index_names:
        _add_unique_constraint(
            "uq_business_assistant_conversation_creation_key",
            ["tenant_id", "user_id", "creation_request_key"],
        )
    if "ix_business_assistant_conversations_scope_updated" not in index_names:
        op.create_index(
            "ix_business_assistant_conversations_scope_updated",
            _TABLE_NAME,
            ["tenant_id", "user_id", "updated_at"],
        )


def downgrade() -> None:
    """Leave reconciled production tables intact; this repair migration is additive only."""
    pass
