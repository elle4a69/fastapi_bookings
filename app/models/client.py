"""Client model.

Represents a customer booking a service.  Clients store contact
information plus optional portal authentication fields, address,
and consent records required for the public client portal.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..db.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    password_hash = Column(String, nullable=True)
    address_line1 = Column(String, nullable=True)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postcode = Column(String, nullable=True)
    country = Column(String, nullable=True)
    timezone = Column(String, nullable=True)
    accepts_marketing = Column(Boolean, default=False, nullable=False)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="client")

    def __repr__(self) -> str:
        return f"<Client id={self.id} name={self.name}>"