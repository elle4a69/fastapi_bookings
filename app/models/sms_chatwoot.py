from datetime import datetime, timezone
import logging

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base
from ..core.crypto import encrypt_string, decrypt_string, CryptoError

logger = logging.getLogger(__name__)


class SmsChatwootBinding(Base):
    __tablename__ = "sms_chatwoot_bindings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    chatwoot_account_id = Column(Integer, nullable=False)
    chatwoot_inbox_id = Column(Integer, nullable=False, index=True)
    chatwoot_base_url = Column(String, nullable=False)
    _chatwoot_api_token = Column("chatwoot_api_token", String, nullable=False)
    _webhook_secret = Column("webhook_secret", String, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    channel_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def chatwoot_api_token(self) -> str:
        """Decrypts and returns the Chatwoot API token."""
        if not self._chatwoot_api_token:
            return ""
        try:
            return decrypt_string(self._chatwoot_api_token)
        except Exception:
            logger.error("Failed to decrypt chatwoot_api_token for SmsChatwootBinding %s", self.id)
            return ""

    @chatwoot_api_token.setter
    def chatwoot_api_token(self, value: str):
        """Encrypts the Chatwoot API token before storing it in the database."""
        if not value:
            self._chatwoot_api_token = ""
            return
        # Fail closed: centralized crypto raises CryptoError if encryption fails. Never fall back to plaintext.
        self._chatwoot_api_token = encrypt_string(value)

    @property
    def webhook_secret(self) -> str:
        """Decrypts and returns the Chatwoot webhook secret."""
        if not self._webhook_secret:
            return ""
        try:
            return decrypt_string(self._webhook_secret)
        except Exception:
            logger.error("Failed to decrypt webhook_secret for SmsChatwootBinding %s", self.id)
            return ""

    @webhook_secret.setter
    def webhook_secret(self, value: str):
        """Encrypts the Chatwoot webhook secret before storing it in the database."""
        if not value:
            self._webhook_secret = ""
            return
        # Fail closed: centralized crypto raises CryptoError if encryption fails. Never fall back to plaintext.
        self._webhook_secret = encrypt_string(value)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<SmsChatwootBinding id={self.id} chatwoot_inbox_id={self.chatwoot_inbox_id} is_enabled={self.is_enabled}>"
