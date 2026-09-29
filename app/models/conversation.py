"""Channel-Neutral Domain Models.

Defines channel-agnostic messaging models for omnichannel support (SMS, WhatsApp,
Instagram, Messenger, WebChat, Simulated) while maintaining full backward
compatibility with legacy single-channel storage.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Dict, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from ..db.database import Base


class ChannelType(str, enum.Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    MESSENGER = "messenger"
    WEBCHAT = "webchat"
    CHATWOOT = "chatwoot"
    SIMULATED = "simulated"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None


class MessageSource(str, enum.Enum):
    CLIENT = "client"
    ASSISTANT = "assistant"
    OPERATOR = "operator"
    SIMULATED = "simulated"
    CHATWOOT = "chatwoot"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None


class ChannelAccount(Base):
    __tablename__ = "channel_accounts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    channel_type = Column(
        SQLEnum(ChannelType, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    inbox_name = Column(String, nullable=False)
    account_identifier = Column(String, nullable=False, index=True)  # phone number, handle, etc.
    chatwoot_inbox_id = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    credentials_encrypted = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    conversations = relationship("Conversation", back_populates="channel_account", cascade="all, delete-orphan")

    @property
    def credentials(self) -> dict:
        """Decrypts and returns credentials from the database JSON field."""
        if not self.credentials_encrypted:
            return {}
        import os
        secret = os.getenv("SECRET_KEY") or os.getenv("ENCRYPTION_KEY")
        if not secret:
            raise RuntimeError("Encryption key is not configured; failing closed")
        if isinstance(self.credentials_encrypted, dict) and "encrypted_data" in self.credentials_encrypted:
            try:
                import base64
                import hashlib
                import json
                from cryptography.fernet import Fernet

                key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                f = Fernet(fernet_key)

                encrypted_str = self.credentials_encrypted["encrypted_data"]
                decrypted_bytes = f.decrypt(encrypted_str.encode("utf-8"))
                return json.loads(decrypted_bytes.decode("utf-8"))
            except Exception as e:
                raise RuntimeError("Encryption failed; failing closed") from e
        return self.credentials_encrypted if isinstance(self.credentials_encrypted, dict) else {}

    @credentials.setter
    def credentials(self, value: dict):
        """Encrypts credentials before storing them in the database JSON field."""
        if not value:
            self.credentials_encrypted = {}
            return
        import os
        secret = os.getenv("SECRET_KEY") or os.getenv("ENCRYPTION_KEY")
        if not secret:
            raise RuntimeError("Encryption key is not configured; failing closed")
        try:
            import base64
            import hashlib
            import json
            from cryptography.fernet import Fernet

            key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            f = Fernet(fernet_key)

            serialized = json.dumps(value)
            encrypted_str = f.encrypt(serialized.encode("utf-8")).decode("utf-8")
            self.credentials_encrypted = {"encrypted_data": encrypted_str}
        except Exception as e:
            raise RuntimeError("Encryption failed; failing closed") from e

    def __repr__(self) -> str:
        return f"<ChannelAccount id={self.id} channel_type={self.channel_type} account_identifier={self.account_identifier}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    channel_account_id = Column(Integer, ForeignKey("channel_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    external_conversation_id = Column(String, nullable=True, index=True)  # e.g. Chatwoot conversation ID
    contact_identifier = Column(String, nullable=False, index=True)  # customer phone or handle
    contact_name = Column(String, nullable=True)
    status = Column(String, default="active", nullable=False, index=True)  # 'active', 'archived', 'paused'
    metadata_payload = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    channel_account = relationship("ChannelAccount", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @property
    def channel_type(self) -> Optional[ChannelType]:
        if self.channel_account and self.channel_account.channel_type:
            return self.channel_account.channel_type
        if isinstance(self.metadata_payload, dict):
            raw = self.metadata_payload.get("channel_type")
            if raw:
                try:
                    return ChannelType(raw)
                except Exception:
                    pass
        return None

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} tenant_id={self.tenant_id} contact={self.contact_identifier} status={self.status}>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    direction = Column(
        SQLEnum(MessageDirection, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    source = Column(
        SQLEnum(MessageSource, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    external_message_id = Column(String, nullable=True, index=True)
    delivery_status = Column(
        SQLEnum(DeliveryStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )
    tool_calls = Column(JSON, nullable=True)
    metadata_payload = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id} direction={self.direction} source={self.source}>"
