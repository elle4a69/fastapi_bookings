"""add webhook secret to chatwoot bindings

Revision ID: 5f8f9989df0c
Revises: 73a63e930e5b
Create Date: 2026-08-28 03:22:59.963585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f8f9989df0c'
down_revision: Union[str, Sequence[str], None] = '73a63e930e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    import secrets
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    from app.core.config import settings

    def _chatwoot_token_cipher():
        secret = settings.PUBLIC_API_KEY or settings.SECRET_KEY or "fallback-default-secret-key-change-me"
        key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(key_bytes))

    op.add_column('sms_chatwoot_bindings', sa.Column('webhook_secret', sa.String(), nullable=True))
    
    # Backfill existing bindings
    bind = sa.sql.table(
        'sms_chatwoot_bindings',
        sa.sql.column('id', sa.Integer),
        sa.sql.column('webhook_secret', sa.String)
    )
    
    connection = op.get_bind()
    results = connection.execute(sa.sql.select(bind.c.id)).fetchall()
    cipher = _chatwoot_token_cipher()
    for row in results:
        raw_secret = secrets.token_hex(32)
        encrypted_secret = cipher.encrypt(raw_secret.encode("utf-8")).decode("utf-8")
        connection.execute(
            bind.update().where(bind.c.id == row[0]).values(webhook_secret=encrypted_secret)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sms_chatwoot_bindings', 'webhook_secret')
