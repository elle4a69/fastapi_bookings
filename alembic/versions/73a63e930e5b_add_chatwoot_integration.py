"""add_chatwoot_integration

Revision ID: 73a63e930e5b
Revises: 73647371c9bc
Create Date: 2026-08-26 23:26:00.094330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73a63e930e5b'
down_revision: Union[str, Sequence[str], None] = '73647371c9bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create sms_chatwoot_bindings
    op.create_table(
        'sms_chatwoot_bindings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('chatwoot_account_id', sa.Integer(), nullable=False),
        sa.Column('chatwoot_inbox_id', sa.Integer(), nullable=False),
        sa.Column('chatwoot_base_url', sa.String(), nullable=False),
        sa.Column('chatwoot_api_token', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('channel_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sms_chatwoot_bindings_id'), 'sms_chatwoot_bindings', ['id'], unique=False)
    op.create_index(op.f('ix_sms_chatwoot_bindings_tenant_id'), 'sms_chatwoot_bindings', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_sms_chatwoot_bindings_provider_id'), 'sms_chatwoot_bindings', ['provider_id'], unique=False)
    op.create_index(op.f('ix_sms_chatwoot_bindings_chatwoot_inbox_id'), 'sms_chatwoot_bindings', ['chatwoot_inbox_id'], unique=False)

    # 2. Modify sms_conversations: sms_account_id nullable, add chatwoot_conversation_id, chatwoot_contact_id, chatwoot_inbox_id
    with op.batch_alter_table('sms_conversations', schema=None) as batch_op:
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=True)
        batch_op.add_column(sa.Column('chatwoot_conversation_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('chatwoot_contact_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('chatwoot_inbox_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_sms_conversations_chatwoot_conversation_id', ['chatwoot_conversation_id'], unique=False)

    # 3. Modify sms_messages: sms_account_id nullable, add chatwoot_message_id
    with op.batch_alter_table('sms_messages', schema=None) as batch_op:
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=True)
        batch_op.add_column(sa.Column('chatwoot_message_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_sms_messages_chatwoot_message_id', ['chatwoot_message_id'], unique=False)

    # 4. Modify sms_outbound_jobs: sms_account_id nullable
    with op.batch_alter_table('sms_outbound_jobs', schema=None) as batch_op:
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Modify sms_outbound_jobs
    with op.batch_alter_table('sms_outbound_jobs', schema=None) as batch_op:
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=False)

    # 2. Modify sms_messages
    with op.batch_alter_table('sms_messages', schema=None) as batch_op:
        batch_op.drop_index('ix_sms_messages_chatwoot_message_id')
        batch_op.drop_column('chatwoot_message_id')
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=False)

    # 3. Modify sms_conversations
    with op.batch_alter_table('sms_conversations', schema=None) as batch_op:
        batch_op.drop_index('ix_sms_conversations_chatwoot_conversation_id')
        batch_op.drop_column('chatwoot_inbox_id')
        batch_op.drop_column('chatwoot_contact_id')
        batch_op.drop_column('chatwoot_conversation_id')
        batch_op.alter_column('sms_account_id',
               existing_type=sa.Integer(),
               nullable=False)

    # 4. Drop sms_chatwoot_bindings
    op.drop_index(op.f('ix_sms_chatwoot_bindings_chatwoot_inbox_id'), table_name='sms_chatwoot_bindings')
    op.drop_index(op.f('ix_sms_chatwoot_bindings_provider_id'), table_name='sms_chatwoot_bindings')
    op.drop_index(op.f('ix_sms_chatwoot_bindings_tenant_id'), table_name='sms_chatwoot_bindings')
    op.drop_index(op.f('ix_sms_chatwoot_bindings_id'), table_name='sms_chatwoot_bindings')
    op.drop_table('sms_chatwoot_bindings')
