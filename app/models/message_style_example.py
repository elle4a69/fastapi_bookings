"""Message Style Example Model.

Stores curated, approved procedural conversation style examples separately
from CuratedMemory (factual business knowledge).
"""

from datetime import datetime, timezone
import hashlib
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..db.database import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def compute_style_example_hash(intent: str, client_message: str) -> str:
    """Compute deterministic SHA-256 fingerprint for (intent, client_message)."""
    norm_intent = (intent or "").strip().lower()
    norm_client = (client_message or "").strip()
    return hashlib.sha256(f"{norm_intent}::{norm_client}".encode("utf-8")).hexdigest()


class MessageStyleExample(Base):
    """Curated procedural style and dialog flow examples.

    This table stores conversational style examples (e.g. greetings, tone, polite declines)
    used to condition assistant tone and dialogue patterns.
    Factual business knowledge belongs in CuratedMemory, NEVER here.
    """

    __tablename__ = "message_style_examples"
    __table_args__ = (
        Index(
            "ix_mse_lookup",
            "tenant_id",
            "provider_id",
            "intent",
            "is_active",
            "is_approved",
        ),
        Index("ix_mse_content_hash", "content_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    intent = Column(String(64), nullable=False, index=True)
    client_message = Column(Text, nullable=False)
    assistant_reply = Column(Text, nullable=False)
    category = Column(String(64), default="procedural", nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    source = Column(String(64), default="assistant_ui_import", nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    provider = relationship("Provider", foreign_keys=[provider_id])

    def __repr__(self) -> str:
        return (
            f"<MessageStyleExample id={self.id} tenant_id={self.tenant_id} "
            f"provider_id={self.provider_id} intent='{self.intent}' "
            f"category='{self.category}' approved={self.is_approved}>"
        )
