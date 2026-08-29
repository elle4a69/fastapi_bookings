from datetime import datetime, timezone
import uuid
from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base

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
                import os
                import base64
                import hashlib
                import json
                from cryptography.fernet import Fernet
                
                secret = os.getenv("SECRET_KEY") or os.getenv("PUBLIC_API_KEY") or "fallback-default-secret-key-change-me"
                key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                f = Fernet(fernet_key)
                
                encrypted_str = self._credentials["encrypted_data"]
                decrypted_bytes = f.decrypt(encrypted_str.encode("utf-8"))
                return json.loads(decrypted_bytes.decode("utf-8"))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to decrypt credentials for SmsAccount {self.id}: {e}")
                return {}
        return self._credentials if isinstance(self._credentials, dict) else {}

    @credentials.setter
    def credentials(self, value: dict):
        """Encrypts credentials before storing them in the database JSON field."""
        if not value:
            self._credentials = {}
            return
        try:
            import os
            import base64
            import hashlib
            import json
            from cryptography.fernet import Fernet
            
            secret = os.getenv("SECRET_KEY") or os.getenv("PUBLIC_API_KEY") or "fallback-default-secret-key-change-me"
            key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            f = Fernet(fernet_key)
            
            serialized = json.dumps(value)
            encrypted_str = f.encrypt(serialized.encode("utf-8")).decode("utf-8")
            self._credentials = {"encrypted_data": encrypted_str}
        except Exception:
            self._credentials = value
    
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
