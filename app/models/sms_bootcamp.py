import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


def _utc_now():
    return datetime.now(timezone.utc)


class SmsBootcampRun(Base):
    __tablename__ = "sms_bootcamp_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="running")  # running, paused, stopped, completed, failed, waiting_approval
    selected_personas = Column(JSON, nullable=False, default=list)
    selected_scenarios = Column(JSON, nullable=True)
    autonomy_level = Column(Integer, default=2, nullable=False)
    max_turns = Column(Integer, nullable=False, default=5)
    style_profile = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    conversations = relationship(
        "SmsBootcampConversation",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SmsBootcampConversation.created_at",
    )

    def __repr__(self) -> str:
        return f"<SmsBootcampRun id={self.id} tenant_id={self.tenant_id} status={self.status} autonomy={self.autonomy_level}>"


class SmsBootcampConversation(Base):
    __tablename__ = "sms_bootcamp_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("sms_bootcamp_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    persona_id = Column(String(64), nullable=False)
    persona_name = Column(String(128), nullable=False)
    scenario_id = Column(String(100), nullable=True)
    status = Column(String(32), nullable=False, default="running")  # running, handoff, completed, stopped, waiting_approval
    current_turn = Column(Integer, nullable=False, default=0)
    needs_handoff = Column(Boolean, nullable=False, default=False)
    handoff_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")
    run = relationship("SmsBootcampRun", back_populates="conversations")
    messages = relationship(
        "SmsBootcampMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SmsBootcampMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<SmsBootcampConversation id={self.id} persona_id={self.persona_id} scenario_id={self.scenario_id} status={self.status}>"


class SmsBootcampMessage(Base):
    __tablename__ = "sms_bootcamp_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("sms_bootcamp_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # 'persona' or 'tori'
    text = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    conversation = relationship("SmsBootcampConversation", back_populates="messages")

    @property
    def status(self) -> str:
        if hasattr(self, "_status_override"):
            return self._status_override
        return (self.meta or {}).get("status", "sent" if self.role == "tori" else "received")

    @status.setter
    def status(self, val: str) -> None:
        self._status_override = val
        new_meta = dict(self.meta or {})
        new_meta["status"] = val
        self.meta = new_meta

    def __repr__(self) -> str:
        return f"<SmsBootcampMessage id={self.id} role={self.role} conv={self.conversation_id}>"


class SmsBootcampSettings(Base):
    __tablename__ = "sms_bootcamp_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", name="uq_sms_bootcamp_settings_tenant_provider"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    active_style_profile = Column(JSON, nullable=False, default=dict)
    previous_style_profile = Column(JSON, nullable=True)
    agent_name = Column(String(64), nullable=False, default="Tori")
    system_prompt_template = Column(Text, nullable=True)
    custom_training_notes = Column(Text, nullable=True)

    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<SmsBootcampSettings id={self.id} tenant_id={self.tenant_id} provider_id={self.provider_id} agent_name={self.agent_name}>"
