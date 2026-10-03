"""Add chatwoot fields and provider_knowledge

Revision ID: s4t5u6v7w8x9
Revises: m3n4p5q6r7s8
Create Date: 2026-10-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 's4t5u6v7w8x9'
down_revision: Union[str, Sequence[str], None] = 'm3n4p5q6r7s8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clients
    op.add_column('clients', sa.Column('chatwoot_contact_id', sa.Integer(), nullable=True))
    op.add_column('clients', sa.Column('street_address', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('suburb', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('clients', sa.Column('longitude', sa.Float(), nullable=True))
    
    with op.batch_alter_table('clients') as batch_op:
        batch_op.create_unique_constraint('uq_clients_chatwoot_contact_id', ['chatwoot_contact_id'])

    # Providers
    op.add_column('providers', sa.Column('chatwoot_inbox_id', sa.Integer(), nullable=True))
    op.add_column('providers', sa.Column('system_persona', sa.Text(), nullable=True))
    op.add_column('providers', sa.Column('max_char_limit', sa.Integer(), server_default='160', nullable=False))
    
    with op.batch_alter_table('providers') as batch_op:
        batch_op.create_unique_constraint('uq_providers_chatwoot_inbox_id', ['chatwoot_inbox_id'])

    # ProviderKnowledge
    op.create_table('provider_knowledge',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('fact_key', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index(
        'idx_active_knowledge',
        'provider_knowledge',
        ['tenant_id', 'fact_key'],
        unique=False,
        postgresql_where=sa.text('superseded_at IS NULL')
    )
    op.create_index(op.f('ix_provider_knowledge_id'), 'provider_knowledge', ['id'], unique=False)
    op.create_index(op.f('ix_provider_knowledge_tenant_id'), 'provider_knowledge', ['tenant_id'], unique=False)


def downgrade() -> None:
    # Drop indexes and table for provider_knowledge
    op.drop_index(op.f('ix_provider_knowledge_tenant_id'), table_name='provider_knowledge')
    op.drop_index(op.f('ix_provider_knowledge_id'), table_name='provider_knowledge')
    op.drop_index('idx_active_knowledge', table_name='provider_knowledge', postgresql_where=sa.text('superseded_at IS NULL'))
    op.drop_table('provider_knowledge')

    # Drop columns and constraints for providers
    with op.batch_alter_table('providers') as batch_op:
        batch_op.drop_constraint('uq_providers_chatwoot_inbox_id', type_='unique')
        batch_op.drop_column('max_char_limit')
        batch_op.drop_column('system_persona')
        batch_op.drop_column('chatwoot_inbox_id')

    # Drop columns and constraints for clients
    with op.batch_alter_table('clients') as batch_op:
        batch_op.drop_constraint('uq_clients_chatwoot_contact_id', type_='unique')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
        batch_op.drop_column('suburb')
        batch_op.drop_column('street_address')
        batch_op.drop_column('chatwoot_contact_id')
