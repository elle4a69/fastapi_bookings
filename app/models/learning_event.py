"""Model for unified learning event ingestion across SMS conversations and bootcamp."""

import difflib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
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
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def compute_text_diff(original: Optional[str], modified: Optional[str]) -> Dict[str, Any]:
    """Compute structural diff payload between original and modified text."""
    orig = (original or "").strip()
    mod = (modified or "").strip()
    words_orig = orig.split()
    words_mod = mod.split()
    matcher = difflib.SequenceMatcher(None, words_orig, words_mod)
    ratio = round(matcher.ratio(), 4)
    added = [
        w
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag in ("replace", "insert")
        for w in words_mod[j1:j2]
    ]
    removed = [
        w
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag in ("replace", "delete")
        for w in words_orig[i1:i2]
    ]
    return {
        "original_length": len(orig),
        "new_length": len(mod),
        "ratio": ratio,
        "added": added,
        "removed": removed,
        "word_diff": f"-{len(removed)} words, +{len(added)} words",
    }


class LearningEvent(Base):
    """Unified ingestion event capturing human-in-the-loop and conversational learning signals.

    Sources include live production SMS (production_messages) and simulated Bootcamp runs (bootcamp).
    """

    __tablename__ = "learning_events"
    __table_args__ = (
        Index(
            "ix_learning_events_tenant_status",
            "tenant_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_learning_events_tenant_source_type",
            "tenant_id",
            "source",
            "event_type",
        ),
        Index(
            "ix_learning_events_claim",
            "status",
            "next_attempt_at",
            "tenant_id",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id = Column(String(64), nullable=True, index=True)
    message_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    source = Column(String(64), nullable=False, index=True)
    customer_message = Column(Text, nullable=True)
    original_ai_content = Column(Text, nullable=True)
    human_content = Column(Text, nullable=True)
    diff_payload = Column(JSON, nullable=True)
    metadata_payload = Column(JSON, nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Worker leasing & retry columns (Phase 3)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return (
            f"<LearningEvent id={self.id} tenant_id={self.tenant_id} "
            f"event_type='{self.event_type}' source='{self.source}' status='{self.status}'>"
        )
