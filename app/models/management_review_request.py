"""ManagementReviewRequest model.

Represents a request submitted by a restricted client for manual review,
without reserving a slot or taking payment.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from ..db.database import Base


class ManagementReviewRequest(Base):
    __tablename__ = "management_review_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)

    preferred_time = Column(DateTime(timezone=True), nullable=True)
    reason = Column(String, nullable=True)
    state = Column(String, default="pending", nullable=False)  # pending, approved, rejected
    slot_reserved = Column(Boolean, default=False, nullable=False)
    payment_taken = Column(Boolean, default=False, nullable=False)

    resolution_notes = Column(Text, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client")
    service = relationship("Service")
    provider = relationship("Provider")
    location = relationship("Location")
    resolved_by = relationship("User")

    def __repr__(self) -> str:
        return f"<ManagementReviewRequest id={self.id} state={self.state}>"
