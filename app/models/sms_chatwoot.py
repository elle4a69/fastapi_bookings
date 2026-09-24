from datetime import datetime, timezone
import base64
import hashlib
import logging

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base
from ..core.config import settings


logger = logging.getLogger(__name__)


class SmsChatwootCredentialError(RuntimeError):
    """Fixed, non-sensitive failure raised for unusable Chatwoot secrets."""


def _chatwoot_token_cipher():
    """Build a stable cipher from the application's configured key.

    The previous implementation read ``os.getenv`` directly. That bypassed
    Pydantic's ``.env`` loading and meant a manually launched server could use
    a different key from the application that saved the binding.
    """
    from cryptography.fernet import Fernet

    secret = settings.PUBLIC_API_KEY or settings.SECRET_KEY
    if not secret:
        raise SmsChatwootCredentialError(
            "Chatwoot credential encryption is unavailable."
        )
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
            return _chatwoot_token_cipher().decrypt(self._chatwoot_api_token.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.error("Chatwoot API token decryption failed.")
            raise SmsChatwootCredentialError(
                "Chatwoot API token decryption failed."
            ) from None

    @chatwoot_api_token.setter
    def chatwoot_api_token(self, value: str):
        """Encrypts the Chatwoot API token before storing it in the database."""
        if not value:
            self._chatwoot_api_token = ""
            return
        try:
            encrypted = _chatwoot_token_cipher().encrypt(value.encode("utf-8"))
        except Exception:
            logger.error("Chatwoot API token encryption failed.")
            raise SmsChatwootCredentialError(
                "Chatwoot API token encryption failed."
            ) from None
        self._chatwoot_api_token = encrypted.decode("utf-8")

    @property
    def webhook_secret(self) -> str:
        """Decrypts and returns the Chatwoot webhook secret."""
        if not self._webhook_secret:
            return ""
        try:
            return _chatwoot_token_cipher().decrypt(self._webhook_secret.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.error("Chatwoot webhook secret decryption failed.")
            raise SmsChatwootCredentialError(
                "Chatwoot webhook secret decryption failed."
            ) from None

    @webhook_secret.setter
    def webhook_secret(self, value: str):
        """Encrypts the Chatwoot webhook secret before storing it in the database."""
        if not value:
            self._webhook_secret = ""
            return
        try:
            encrypted = _chatwoot_token_cipher().encrypt(value.encode("utf-8"))
        except Exception:
            logger.error("Chatwoot webhook secret encryption failed.")
            raise SmsChatwootCredentialError(
                "Chatwoot webhook secret encryption failed."
            ) from None
        self._webhook_secret = encrypted.decode("utf-8")

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<SmsChatwootBinding id={self.id} chatwoot_inbox_id={self.chatwoot_inbox_id} is_enabled={self.is_enabled}>"
