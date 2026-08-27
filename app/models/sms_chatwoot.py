from datetime import datetime, timezone
import base64
import hashlib

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base
from ..core.config import settings


def _chatwoot_token_cipher():
    """Build a stable cipher from the application's configured key.

    The previous implementation read ``os.getenv`` directly. That bypassed
    Pydantic's ``.env`` loading and meant a manually launched server could use
    a different key from the application that saved the binding.
    """
    from cryptography.fernet import Fernet

    secret = settings.PUBLIC_API_KEY or settings.SECRET_KEY or "fallback-default-secret-key-change-me"
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

class SmsChatwootBinding(Base):
    __tablename__ = "sms_chatwoot_bindings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    chatwoot_account_id = Column(Integer, nullable=False)
    chatwoot_inbox_id = Column(Integer, nullable=False, index=True)
    chatwoot_base_url = Column(String, nullable=False)
    _chatwoot_api_token = Column("chatwoot_api_token", String, nullable=False)
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
            return _chatwoot_token_cipher().decrypt(self._chatwoot_api_token.encode("utf-8")).decode("utf-8")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to decrypt chatwoot_api_token for SmsChatwootBinding {self.id}: {e}")
            return ""

    @chatwoot_api_token.setter
    def chatwoot_api_token(self, value: str):
        """Encrypts the Chatwoot API token before storing it in the database."""
        if not value:
            self._chatwoot_api_token = ""
            return
        try:
            self._chatwoot_api_token = _chatwoot_token_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:
            self._chatwoot_api_token = value

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<SmsChatwootBinding id={self.id} chatwoot_inbox_id={self.chatwoot_inbox_id} is_enabled={self.is_enabled}>"
