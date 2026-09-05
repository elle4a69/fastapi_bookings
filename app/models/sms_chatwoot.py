import base64
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship

from ..core.config import settings
from ..db.database import Base


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


class ChatwootConnection(Base):
    """Tenant-owned account-level boundary for authenticated Chatwoot ingress."""

    __tablename__ = "chatwoot_connections"

    id = Column(Integer, primary_key=True)
    public_id = Column(Uuid(as_uuid=True), default=uuid4, nullable=False)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_origin = Column(String(2048), nullable=False)
    chatwoot_account_id = Column(BigInteger, nullable=False)
    _signing_secret_ciphertext = Column(
        "signing_secret_ciphertext", String(4096), nullable=True
    )
    enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_chatwoot_connections_public_id"),
        UniqueConstraint(
            "instance_origin",
            "chatwoot_account_id",
            name="uq_chatwoot_connections_origin_account",
        ),
        UniqueConstraint(
            "id", "tenant_id", name="uq_chatwoot_connections_id_tenant"
        ),
        CheckConstraint(
            "chatwoot_account_id > 0",
            name="ck_chatwoot_connections_account_positive",
        ),
        CheckConstraint(
            "length(instance_origin) BETWEEN 1 AND 2048",
            name="ck_chatwoot_connections_origin_length",
        ),
    )

    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    inbox_bindings = relationship(
        "SmsChatwootBinding",
        back_populates="connection",
        passive_deletes=True,
        overlaps="tenant",
    )
    webhook_receipts = relationship(
        "ChatwootWebhookReceipt",
        back_populates="connection",
        passive_deletes=True,
    )

    @property
    def has_signing_secret(self) -> bool:
        return bool(self._signing_secret_ciphertext)

    @property
    def webhook_path(self) -> str:
        return f"/api/messaging/chatwoot/webhooks/{self.public_id}"


class ChatwootWebhookReceipt(Base):
    """Structural replay receipt; intentionally excludes message payload data."""

    __tablename__ = "chatwoot_webhook_receipts"

    id = Column(Integer, primary_key=True)
    connection_id = Column(
        Integer,
        ForeignKey("chatwoot_connections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    delivery_id = Column(Uuid(as_uuid=True), nullable=False)
    event_type = Column(String(64), nullable=False)
    outcome = Column(String(64), nullable=False)
    chatwoot_inbox_id = Column(BigInteger, nullable=True)
    chatwoot_conversation_id = Column(BigInteger, nullable=True)
    chatwoot_message_id = Column(BigInteger, nullable=True)
    webhook_timestamp = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "delivery_id",
            name="uq_chatwoot_webhook_receipts_connection_delivery",
        ),
        CheckConstraint(
            "length(event_type) BETWEEN 1 AND 64",
            name="ck_chatwoot_webhook_receipts_event_type_length",
        ),
        CheckConstraint(
            "length(outcome) BETWEEN 1 AND 64",
            name="ck_chatwoot_webhook_receipts_outcome_length",
        ),
        CheckConstraint(
            "chatwoot_inbox_id IS NULL OR chatwoot_inbox_id > 0",
            name="ck_chatwoot_webhook_receipts_inbox_positive",
        ),
        CheckConstraint(
            "chatwoot_conversation_id IS NULL OR chatwoot_conversation_id > 0",
            name="ck_chatwoot_webhook_receipts_conversation_positive",
        ),
        CheckConstraint(
            "chatwoot_message_id IS NULL OR chatwoot_message_id > 0",
            name="ck_chatwoot_webhook_receipts_message_positive",
        ),
    )

    connection = relationship("ChatwootConnection", back_populates="webhook_receipts")

class SmsChatwootBinding(Base):
    __tablename__ = "sms_chatwoot_bindings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id = Column(Integer, nullable=True, index=True)
    chatwoot_account_id = Column(BigInteger, nullable=True)
    chatwoot_inbox_id = Column(BigInteger, nullable=False, index=True)
    chatwoot_base_url = Column(String, nullable=True)
    _chatwoot_api_token = Column("chatwoot_api_token", String, nullable=True)
    _webhook_secret = Column("webhook_secret", String, nullable=True)
    is_enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    channel = Column(String(32), nullable=True)
    ingress_enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    # Package C deliberately has no control that can enable automation. This
    # remains a disabled-by-default future policy input only.
    automation_enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
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

    @property
    def webhook_secret(self) -> str:
        """Decrypts and returns the Chatwoot webhook secret."""
        if not self._webhook_secret:
            return ""
        try:
            return _chatwoot_token_cipher().decrypt(self._webhook_secret.encode("utf-8")).decode("utf-8")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to decrypt webhook_secret for SmsChatwootBinding {self.id}: {e}")
            return ""

    @webhook_secret.setter
    def webhook_secret(self, value: str):
        """Encrypts the Chatwoot webhook secret before storing it in the database."""
        if not value:
            self._webhook_secret = ""
            return
        try:
            self._webhook_secret = _chatwoot_token_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:
            self._webhook_secret = value

    __table_args__ = (
        UniqueConstraint(
            "id", "tenant_id", name="uq_sms_chatwoot_bindings_id_tenant"
        ),
        UniqueConstraint(
            "connection_id",
            "chatwoot_inbox_id",
            name="uq_sms_chatwoot_bindings_connection_inbox",
        ),
        ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["chatwoot_connections.id", "chatwoot_connections.tenant_id"],
            name="fk_sms_chatwoot_bindings_connection_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "chatwoot_inbox_id > 0",
            name="ck_sms_chatwoot_bindings_inbox_positive",
        ),
        CheckConstraint(
            "chatwoot_account_id IS NULL OR chatwoot_account_id > 0",
            name="ck_sms_chatwoot_bindings_account_positive",
        ),
        CheckConstraint(
            "(connection_id IS NULL AND channel IS NULL AND ingress_enabled = false) "
            "OR (connection_id IS NOT NULL AND channel = 'web_widget' "
            "AND is_enabled = false "
            "AND chatwoot_account_id IS NULL AND chatwoot_base_url IS NULL "
            "AND chatwoot_api_token IS NULL AND webhook_secret IS NULL)",
            name="ck_sms_chatwoot_bindings_legacy_or_connection",
        ),
    )

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id], overlaps="connection,inbox_bindings")
    provider = relationship("Provider")
    connection = relationship(
        "ChatwootConnection",
        back_populates="inbox_bindings",
        foreign_keys=[connection_id, tenant_id],
        overlaps="tenant,inbox_bindings",
    )
    conversations = relationship(
        "SmsConversation",
        back_populates="chatwoot_binding",
        passive_deletes=True,
        overlaps="tenant",
    )
    messages = relationship(
        "SmsMessage",
        back_populates="chatwoot_binding",
        passive_deletes=True,
        overlaps="tenant",
    )

    @property
    def effective_ingress_enabled(self) -> bool:
        return bool(
            self.connection_id is not None
            and self.ingress_enabled
            and self.channel == "web_widget"
            and not self.is_enabled
            and self.connection is not None
            and self.connection.enabled
            and self.connection.has_signing_secret
        )

    @property
    def has_api_token(self) -> bool:
        return bool(self._chatwoot_api_token)

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_secret)

    def __repr__(self) -> str:
        return f"<SmsChatwootBinding id={self.id} chatwoot_inbox_id={self.chatwoot_inbox_id} is_enabled={self.is_enabled}>"
