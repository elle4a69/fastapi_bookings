"""Recurring booking series model.

A recurring series is represented by a BookingSeries which stores the
recurrence pattern and associated metadata.  Each occurrence within
the series is stored as a regular Booking with a foreign key back
to the series.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class BookingSeries(Base):
    """Represents a series of recurring bookings.

    Attributes:
        id: Primary key.
        name: Optional name for the series (e.g. "Weekly Therapy").
        client_id: Client for whom the series is booked.
        service_id: Service being booked.
        provider_id: Preferred provider (may be null for any provider).
        location_id: Preferred location (may be null).
        recurrence_rule: iCalendar RRULE string defining the recurrence.
        end_date: Optional end date for the series.
        created_at: Timestamp when the series was created.
    """

    __tablename__ = "booking_series"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    recurrence_rule = Column(String, nullable=False)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    bookings = relationship("Booking", back_populates="series")
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<BookingSeries id={self.id} service_id={self.service_id}>"
