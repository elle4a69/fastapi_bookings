import base64
from datetime import datetime, timezone
import hashlib
import json
import logging
import uuid

from cryptography.fernet import Fernet
from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from ..core.config import settings
from ..db.database import Base


logger = logging.getLogger(__name__)


class SmsCredentialError(RuntimeError):
    """Fixed, non-sensitive failure raised for unusable credential storage."""


def _sms_credential_cipher() -> Fernet:
    secret = settings.SECRET_KEY or settings.PUBLIC_API_KEY
    if not secret:
        raise SmsCredentialError("SMS credential encryption is unavailable.")
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

class SmsAccount(Base):
    __tablename__ = "sms_accounts"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    transport_type = Column(String, nullable=False)  # 'simulator', 'mobilemessage'
    display_name = Column(String, nullable=False)
    sender_address = Column(String, nullable=False)  # E.164 phone number
    _credentials = Column("credentials", JSON, nullable=True)  # Mapped database column
    is_enabled = Column(Boolean, default=True, nullable=False)

    @property
    def credentials(self) -> dict:
        """Decrypts and returns credentials from the database JSON field."""
        if not self._credentials:
            return {}
        try:
            if not isinstance(self._credentials, dict):
                raise SmsCredentialError("SMS credential storage is invalid.")
            encrypted_value = self._credentials.get("encrypted_data")
            if not isinstance(encrypted_value, str) or not encrypted_value:
                raise SmsCredentialError("SMS credential storage is invalid.")
            decrypted = _sms_credential_cipher().decrypt(encrypted_value.encode("utf-8"))
            value = json.loads(decrypted.decode("utf-8"))
            if not isinstance(value, dict):
                raise SmsCredentialError("SMS credential storage is invalid.")
            return value
        except SmsCredentialError:
            logger.error("SMS credential decryption failed.")
            raise
        except Exception:
            logger.error("SMS credential decryption failed.")
            raise SmsCredentialError("SMS credential decryption failed.") from None

    @credentials.setter
    def credentials(self, value: dict):
        """Encrypts credentials before storing them in the database JSON field."""
        if not value:
            self._credentials = {}
            return
        try:
            if not isinstance(value, dict):
                raise SmsCredentialError("SMS credentials must be a mapping.")
            serialized = json.dumps(value, separators=(",", ":"), sort_keys=True)
            encrypted = _sms_credential_cipher().encrypt(serialized.encode("utf-8"))
        except Exception:
            logger.error("SMS credential encryption failed.")
            raise SmsCredentialError("SMS credential encryption failed.") from None
        self._credentials = {"encrypted_data": encrypted.decode("utf-8")}
    
    # Autoresponder config
    autoresponder_enabled = Column(Boolean, default=False, nullable=False)
    autoresponder_text = Column(Text, nullable=True)
    
    # AI controls
    ai_enabled = Column(Boolean, default=False, nullable=False)
    ai_mode = Column(String, default="off", nullable=False)  # off, draft, autopilot, paused
    line_prompt = Column(Text, nullable=True)
    
    catchup_cutoff_days = Column(Integer, default=30, nullable=False)
    
    # Rate Limiting & Quiet Hours
    throughput_limit = Column(Integer, default=60, nullable=False)
    quiet_hours_start = Column(String, nullable=True)
    quiet_hours_end = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<SmsAccount id={self.id} display_name={self.display_name} transport_type={self.transport_type}>"
