"""Database models for voice-first onboarding workflow persistence.

Supports persistent tenant onboarding plans, domain states (1-8), step progression,
staged facts, lease tracking, control epochs, and append-only audit logging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.database import Base


class OnboardingPlan(Base):
    """Persistent onboarding plan for a tenant and internal user."""

    __tablename__ = "onboarding_plans"
    __table_args__ = (
        Index("ix_onboarding_plans_tenant_user_status", "tenant_id", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), nullable=False, default="in_progress")
    current_step_id = Column(String(64), nullable=True)
    domains_state = Column(JSON, nullable=False, default=dict)
    control_epoch = Column(Integer, nullable=False, default=1)
    active_lease_token = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")
    steps = relationship(
        "OnboardingStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="OnboardingStep.domain, OnboardingStep.id",
    )
    audit_logs = relationship(
        "OnboardingAuditLog",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="OnboardingAuditLog.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<OnboardingPlan id={self.id} tenant_id={self.tenant_id} "
            f"user_id={self.user_id} status='{self.status}' current_step_id='{self.current_step_id}'>"
        )


class OnboardingStep(Base):
    """An individual adaptive step within an onboarding plan."""

    __tablename__ = "onboarding_steps"
    __table_args__ = (
        UniqueConstraint("plan_id", "step_id", name="uq_onboarding_step_plan_step"),
        Index("ix_onboarding_steps_plan_domain", "plan_id", "domain"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    plan_id = Column(
        Integer,
        ForeignKey("onboarding_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(String(64), nullable=False)
    domain = Column(Integer, nullable=False)
    route = Column(String(255), nullable=False)
    form_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="not_started")
    required_facts = Column(JSON, nullable=False, default=list)
    answered_facts = Column(JSON, nullable=False, default=dict)
    staged_fields = Column(JSON, nullable=False, default=dict)
    persisted_entity_id = Column(String(64), nullable=True)
    persisted_revision = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    plan = relationship("OnboardingPlan", back_populates="steps")

    def __repr__(self) -> str:
        return (
            f"<OnboardingStep id={self.id} plan_id={self.plan_id} "
            f"step_id='{self.step_id}' domain={self.domain} status='{self.status}'>"
        )


class OnboardingAuditLog(Base):
    """Audit log entry for an onboarding action or state change."""

    __tablename__ = "onboarding_audit_logs"
    __table_args__ = (
        Index("ix_onboarding_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_onboarding_audit_logs_plan_created", "plan_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        Integer,
        ForeignKey("onboarding_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(64), nullable=False)
    actor = Column(String(32), nullable=False)  # 'agent', 'user'
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    # Relationships
    tenant = relationship("Tenant")
    plan = relationship("OnboardingPlan", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<OnboardingAuditLog id={self.id} plan_id={self.plan_id} "
            f"action='{self.action}' actor='{self.actor}'>"
        )
