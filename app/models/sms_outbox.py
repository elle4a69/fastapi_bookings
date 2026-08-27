from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Text, String, JSON
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsOutboundJob(Base):
    __tablename__ = "sms_outbound_jobs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("sms_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)  # 'PENDING', 'PROCESSING', 'SUCCESS', 'FAILED'
    retry_count = Column(Integer, default=0, nullable=False)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    error_log = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    message = relationship("SmsMessage")
    sms_account = relationship("SmsAccount")

    def __repr__(self) -> str:
        return f"<SmsOutboundJob id={self.id} message_id={self.message_id} status={self.status}>"


class SmsAiJob(Base):
    __tablename__ = "sms_ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_turn_ref = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)  # 'PENDING', 'CANCELLED', 'PROCESSED'
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("SmsConversation")

    def __repr__(self) -> str:
        return f"<SmsAiJob id={self.id} conversation_id={self.conversation_id} status={self.status}>"


class SmsConversationEvent(Base):
    __tablename__ = "sms_conversation_events"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # e.g., 'arrival', 'takeover', 'ai-reply-skipped', 'ai-reply-cancelled'
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversation = relationship("SmsConversation")

    def __repr__(self) -> str:
        return f"<SmsConversationEvent id={self.id} conversation_id={self.conversation_id} type={self.type}>"


class SmsNote(Base):
    __tablename__ = "sms_notes"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversation = relationship("SmsConversation")
    author = relationship("User")

    def __repr__(self) -> str:
        return f"<SmsNote id={self.id} conversation_id={self.conversation_id} author_id={self.author_id}>"
