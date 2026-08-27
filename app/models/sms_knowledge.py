from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Text, String, Boolean
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsKnowledgeEntry(Base):
    __tablename__ = "sms_knowledge_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    category = Column(String, nullable=False)  # 'service', 'policy', 'location', 'faq', 'tone'
    text = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    status = Column(String, default="proposed", nullable=False)  # 'proposed', 'approved', 'rejected', 'archived'
    provenance = Column(String, default="manual", nullable=False)  # 'manual', 'info_request', 'edited_draft', 'imported'
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    sms_account = relationship("SmsAccount")
    approved_by = relationship("User")

    def __repr__(self) -> str:
        return f"<SmsKnowledgeEntry id={self.id} category={self.category} status={self.status}>"


class SmsPromptProfile(Base):
    __tablename__ = "sms_prompt_profiles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    sms_account = relationship("SmsAccount")

    def __repr__(self) -> str:
        return f"<SmsPromptProfile id={self.id} name={self.name} is_active={self.is_active}>"
