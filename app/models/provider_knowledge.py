"""Provider Knowledge model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from ..db.database import Base


class ProviderKnowledge(Base):
    __tablename__ = "provider_knowledge"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Using Integer here because tenants.id is Integer
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_key = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index(
            "idx_active_knowledge",
            "tenant_id",
            "fact_key",
            postgresql_where=(superseded_at.is_(None))
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderKnowledge id={self.id} tenant_id={self.tenant_id} fact_key={self.fact_key}>"
