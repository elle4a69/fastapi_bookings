from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsConversation(Base):
    __tablename__ = "sms_conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    customer_address = Column(String, nullable=False, index=True)  # E.164 normalized customer phone
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    state = Column(String, default="auto-reply", nullable=False)  # 'taken-over', 'auto-reply', 'paused'
    unread_count = Column(Integer, default=0, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Chatwoot fields
    chatwoot_binding_id = Column(Integer, nullable=True, index=True)
    chatwoot_conversation_id = Column(BigInteger, nullable=True, index=True)
    chatwoot_contact_id = Column(BigInteger, nullable=True)
    chatwoot_inbox_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("sms_account_id", "customer_address", name="uq_sms_account_customer"),
        UniqueConstraint(
            "chatwoot_binding_id",
            "chatwoot_conversation_id",
            name="uq_sms_conversations_binding_conversation",
        ),
        UniqueConstraint(
            "id",
            "chatwoot_binding_id",
            name="uq_sms_conversations_id_chatwoot_binding",
        ),
        ForeignKeyConstraint(
            ["chatwoot_binding_id", "tenant_id"],
            ["sms_chatwoot_bindings.id", "sms_chatwoot_bindings.tenant_id"],
            name="fk_sms_conversations_chatwoot_binding_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "chatwoot_conversation_id IS NULL OR chatwoot_conversation_id > 0",
            name="ck_sms_conversations_chatwoot_conversation_positive",
        ),
        CheckConstraint(
            "chatwoot_contact_id IS NULL OR chatwoot_contact_id > 0",
            name="ck_sms_conversations_chatwoot_contact_positive",
        ),
        CheckConstraint(
            "chatwoot_inbox_id IS NULL OR chatwoot_inbox_id > 0",
            name="ck_sms_conversations_chatwoot_inbox_positive",
        ),
    )

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id], overlaps="chatwoot_binding,conversations")
    provider = relationship("Provider")
    sms_account = relationship("SmsAccount")
    client = relationship("Client")
    chatwoot_binding = relationship(
        "SmsChatwootBinding",
        back_populates="conversations",
        foreign_keys=[chatwoot_binding_id, tenant_id],
        overlaps="tenant,conversations",
    )
    messages = relationship(
        "SmsMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SmsMessage.occurred_at",
        foreign_keys="SmsMessage.conversation_id",
    )

    def __repr__(self) -> str:
        return f"<SmsConversation id={self.id} sms_account_id={self.sms_account_id} customer={self.customer_address}>"
