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

from ..db.database import Base


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
    # Package D credentials are deliberately connection-scoped.  The legacy
    # binding token fields remain inert historical data and are never read.
    _api_token_ciphertext = Column("api_token_ciphertext", String(4096), nullable=True)
    expected_integration_sender_type = Column(String(64), nullable=True)
    expected_integration_sender_id = Column(BigInteger, nullable=True)
    enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    outbound_enabled = Column(
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
        CheckConstraint(
            "expected_integration_sender_id IS NULL OR expected_integration_sender_id > 0",
            name="ck_chatwoot_connections_sender_positive",
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
    outbound_intents = relationship(
        "ChatwootOutboundIntent",
        back_populates="connection",
        passive_deletes=True,
    )

    @property
    def has_signing_secret(self) -> bool:
        return bool(self._signing_secret_ciphertext)

    @property
    def has_api_token(self) -> bool:
        return bool(self._api_token_ciphertext)

    @property
    def has_expected_integration_sender(self) -> bool:
        return bool(
            self.expected_integration_sender_type
            and self.expected_integration_sender_id
        )

    @property
    def outbound_ready(self) -> bool:
        """Structural readiness only; no credential plaintext is exposed."""
        return bool(
            self.enabled
            and self.outbound_enabled
            and self.has_signing_secret
            and self.has_api_token
            and self.has_expected_integration_sender
        )

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
    assistant_ui_policy_scope = Column(String(128), nullable=True)
    outbound_enabled = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    channel_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

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
    outbound_intents = relationship(
        "ChatwootOutboundIntent",
        back_populates="binding",
        passive_deletes=True,
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
    def effective_outbound_enabled(self) -> bool:
        return bool(
            self.connection_id is not None
            and self.channel == "web_widget"
            and self.outbound_enabled
            # Outbound must retain the authenticated ingress path so a signed
            # echo can be verified before it ever reconciles local state.
            and self.effective_ingress_enabled
            and self.connection is not None
            and self.connection.outbound_ready
        )

    @property
    def effective_automation_enabled(self) -> bool:
        return bool(
            self.automation_enabled
            and self.effective_outbound_enabled
            and self.assistant_ui_policy_scope
        )

    def __repr__(self) -> str:
        return f"<SmsChatwootBinding id={self.id} chatwoot_inbox_id={self.chatwoot_inbox_id} is_enabled={self.is_enabled}>"


class ChatwootOutboundIntent(Base):
    """One locally-owned, fail-closed FastAPI-to-Chatwoot handoff intent.

    This is an audit and reconciliation ledger, not a generic provider job.
    It contains only structural identifiers plus the opaque correlation UUID.
    """

    __tablename__ = "chatwoot_outbound_intents"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    connection_id = Column(
        Integer,
        ForeignKey("chatwoot_connections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    binding_id = Column(
        Integer,
        ForeignKey("sms_chatwoot_bindings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("sms_conversations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("sms_messages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    outbound_correlation_id = Column(
        Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True
    )
    pre_send_cursor = Column(BigInteger, nullable=True)
    remote_chatwoot_message_id = Column(BigInteger, nullable=True)
    status = Column(
        String(32), default="PENDING", server_default=text("'PENDING'"), nullable=False, index=True
    )
    reconciliation_attempted = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("message_id", name="uq_chatwoot_outbound_intents_message"),
        UniqueConstraint(
            "outbound_correlation_id", name="uq_chatwoot_outbound_intents_correlation"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'SUCCEEDED', 'FAILED', 'OUTCOME_UNKNOWN', 'QUARANTINED')",
            name="ck_chatwoot_outbound_intents_status",
        ),
        CheckConstraint(
            "pre_send_cursor IS NULL OR pre_send_cursor > 0",
            name="ck_chatwoot_outbound_intents_cursor_positive",
        ),
        CheckConstraint(
            "remote_chatwoot_message_id IS NULL OR remote_chatwoot_message_id > 0",
            name="ck_chatwoot_outbound_intents_remote_positive",
        ),
    )

    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    provider = relationship("Provider", foreign_keys=[provider_id])
    connection = relationship("ChatwootConnection", back_populates="outbound_intents")
    binding = relationship("SmsChatwootBinding", back_populates="outbound_intents")
    conversation = relationship("SmsConversation", foreign_keys=[conversation_id])
    message = relationship("SmsMessage", foreign_keys=[message_id])
