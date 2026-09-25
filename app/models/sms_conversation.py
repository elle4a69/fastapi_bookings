from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, UniqueConstraint
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
    source = Column(String, default="sms", nullable=True)  # 'sms', 'web_chat'
    unread_count = Column(Integer, default=0, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    ai_enabled = Column(Boolean, default=True, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Chatwoot fields
    chatwoot_conversation_id = Column(Integer, nullable=True, index=True)
    chatwoot_contact_id = Column(Integer, nullable=True)
    chatwoot_inbox_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("sms_account_id", "customer_address", name="uq_sms_account_customer"),
    )

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    sms_account = relationship("SmsAccount")
    client = relationship("Client")
    messages = relationship("SmsMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="SmsMessage.occurred_at")

    def __repr__(self) -> str:
        return f"<SmsConversation id={self.id} sms_account_id={self.sms_account_id} customer={self.customer_address}>"
