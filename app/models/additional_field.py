"""Additional/intake field models.

AdditionalField defines a configurable field that can appear on the
public booking form, client registration/profile form, or an
admin-only form.  AdditionalFieldResponse stores submitted values
against a booking and/or client.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.database import Base


class AdditionalField(Base):
    """Configurable field definition.

    scope values:
    - client: shown on client registration/profile
    - booking: shown during booking checkout/intake
    - service: shown for a specific service booking form
    """

    __tablename__ = "additional_fields"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String, default="booking", nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    name = Column(String, nullable=False)
    label = Column(String, nullable=False)
    field_type = Column(String, default="text", nullable=False)
    required = Column(Boolean, default=False, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    placeholder = Column(String, nullable=True)
    help_text = Column(Text, nullable=True)
    options_json = Column(Text, nullable=True)
    default_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service")


class AdditionalFieldResponse(Base):
    """Submitted additional/intake field value."""

    __tablename__ = "additional_field_responses"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("additional_fields.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    field = relationship("AdditionalField")
    client = relationship("Client")
    booking = relationship("Booking")
