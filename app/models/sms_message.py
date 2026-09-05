from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, Integer, ForeignKey, ForeignKeyConstraint, Text, String, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    normalized_body = Column(Text, nullable=True)
    direction = Column(String, nullable=False)  # 'inbound', 'outbound', 'draft', 'system'
    author_type = Column(String, nullable=False)  # 'customer', 'staff', 'fixed_autoresponder', 'ai', 'system'
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="received", nullable=False)  # 'received', 'queued', 'sending', 'sent', 'delivered', 'failed', 'cancelled', 'draft', 'discarded'
    provider_message_id = Column(String, nullable=True, index=True)
    chatwoot_binding_id = Column(Integer, nullable=True, index=True)
    chatwoot_message_id = Column(BigInteger, nullable=True, index=True)
    chatwoot_message_type = Column(String(32), nullable=True)
    chatwoot_content_type = Column(String(64), nullable=True)
    chatwoot_private = Column(Boolean, nullable=True)
    chatwoot_sender_type = Column(String(64), nullable=True)
    chatwoot_sender_reference = Column(String(255), nullable=True)
    chatwoot_attachment_metadata = Column(JSON, nullable=True)
    parent_message_id = Column(Integer, ForeignKey("sms_messages.id", ondelete="SET NULL"), nullable=True)
    client_request_id = Column(String, nullable=True, index=True)
    customer_turn_ref = Column(String, nullable=True, index=True)
    ai_metadata = Column(JSON, nullable=True)

    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "chatwoot_binding_id",
            "chatwoot_message_id",
            name="uq_sms_messages_binding_chatwoot_message",
        ),
        ForeignKeyConstraint(
            ["chatwoot_binding_id", "tenant_id"],
            ["sms_chatwoot_bindings.id", "sms_chatwoot_bindings.tenant_id"],
            name="fk_sms_messages_chatwoot_binding_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "chatwoot_binding_id"],
            ["sms_conversations.id", "sms_conversations.chatwoot_binding_id"],
            name="fk_sms_messages_conversation_chatwoot_binding",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "chatwoot_message_id IS NULL OR chatwoot_message_id > 0",
            name="ck_sms_messages_chatwoot_message_positive",
        ),
    )

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id], overlaps="chatwoot_binding,messages")
    provider = relationship("Provider")
    sms_account = relationship("SmsAccount")
    conversation = relationship(
        "SmsConversation",
        back_populates="messages",
        foreign_keys=[conversation_id],
        overlaps="chatwoot_binding,messages",
    )
    chatwoot_binding = relationship(
        "SmsChatwootBinding",
        back_populates="messages",
        foreign_keys=[chatwoot_binding_id, tenant_id],
        overlaps="conversation,messages,tenant",
    )
    author = relationship("User")
    
    # Self-referential relationship for drafts / replies
    parent = relationship("SmsMessage", remote_side=[id])

    def __repr__(self) -> str:
        return f"<SmsMessage id={self.id} direction={self.direction} author_type={self.author_type} status={self.status}>"
