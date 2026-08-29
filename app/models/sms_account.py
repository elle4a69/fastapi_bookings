from datetime import datetime, timezone
import uuid
from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base

import logging
from ..core.crypto import encrypt_dict, decrypt_dict, CryptoError

logger = logging.getLogger(__name__)

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
        if isinstance(self._credentials, dict) and "encrypted_data" in self._credentials:
            try:
                return decrypt_dict(self._credentials)
            except Exception:
                logger.error("Failed to decrypt credentials for SmsAccount %s", self.id)
                return {}
        return {}

    @credentials.setter
    def credentials(self, value: dict):
        """Encrypts credentials before storing them in the database JSON field."""
        if not value:
            self._credentials = {}
            return
        # Fail closed: centralized crypto raises CryptoError if encryption fails. Never fall back to plaintext.
        self._credentials = encrypt_dict(value)
    
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
