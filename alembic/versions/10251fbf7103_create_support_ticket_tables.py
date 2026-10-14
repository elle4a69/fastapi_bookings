"""create support ticket tables

Revision ID: 10251fbf7103
Revises: a1b2c3d4e5f7
Create Date: 2026-10-14 19:15:33.308355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10251fbf7103'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include support ticket tables."""
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('triage_priority', sa.String(length=20), nullable=False),
        sa.Column('error_context', sa.JSON(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('codex_thread_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'idempotency_key', name='uq_support_tickets_tenant_idempotency'),
    )
    op.create_index(op.f('ix_support_tickets_category'), 'support_tickets', ['category'], unique=False)
    op.create_index(op.f('ix_support_tickets_codex_thread_id'), 'support_tickets', ['codex_thread_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_created_by_user_id'), 'support_tickets', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_idempotency_key'), 'support_tickets', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_support_tickets_status'), 'support_tickets', ['status'], unique=False)
    op.create_index(op.f('ix_support_tickets_tenant_id'), 'support_tickets', ['tenant_id'], unique=False)
    op.create_index('ix_support_tickets_tenant_status', 'support_tickets', ['tenant_id', 'status'], unique=False)
    op.create_index(op.f('ix_support_tickets_triage_priority'), 'support_tickets', ['triage_priority'], unique=False)

    op.create_table(
        'support_ticket_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('sender_user_id', sa.Integer(), nullable=True),
        sa.Column('sender_type', sa.String(length=20), nullable=False),
        sa.Column('visibility', sa.String(length=20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_support_ticket_messages_sender_user_id'), 'support_ticket_messages', ['sender_user_id'], unique=False)
    op.create_index(op.f('ix_support_ticket_messages_ticket_id'), 'support_ticket_messages', ['ticket_id'], unique=False)

    op.create_table(
        'support_ticket_audit_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_support_ticket_audit_events_actor_user_id'), 'support_ticket_audit_events', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_support_ticket_audit_events_ticket_id'), 'support_ticket_audit_events', ['ticket_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema by dropping support ticket tables."""
    op.drop_index(op.f('ix_support_ticket_audit_events_ticket_id'), table_name='support_ticket_audit_events')
    op.drop_index(op.f('ix_support_ticket_audit_events_actor_user_id'), table_name='support_ticket_audit_events')
    op.drop_table('support_ticket_audit_events')

    op.drop_index(op.f('ix_support_ticket_messages_ticket_id'), table_name='support_ticket_messages')
    op.drop_index(op.f('ix_support_ticket_messages_sender_user_id'), table_name='support_ticket_messages')
    op.drop_table('support_ticket_messages')

    op.drop_index(op.f('ix_support_tickets_triage_priority'), table_name='support_tickets')
    op.drop_index('ix_support_tickets_tenant_status', table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_tenant_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_status'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_idempotency_key'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_created_by_user_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_codex_thread_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_category'), table_name='support_tickets')
    op.drop_table('support_tickets')
