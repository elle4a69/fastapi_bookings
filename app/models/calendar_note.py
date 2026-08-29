"""Calendar note model.

Stores textual notes attached to a provider and date/time range on the
admin calendar.  Notes can be used to mark holidays, reminders, or
custom block-out messages that appear in the admin dashboard view.
"""

from datetime import datetime, date

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from ..db.database import Base


class CalendarNote(Base):
    """A text annotation on the admin calendar for a provider and date."""

    __tablename__ = "calendar_notes"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(String, nullable=True)   # HH:MM
    end_time = Column(String, nullable=True)     # HH:MM
    text = Column(Text, nullable=False)
    note_type = Column(String, nullable=True)
    is_time_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<CalendarNote id={self.id} date={self.date}>"
