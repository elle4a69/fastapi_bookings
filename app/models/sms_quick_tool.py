from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.database import Base


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class SmsQuickTool(Base):
    __tablename__ = "sms_quick_tools"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    slot_index = Column(Integer, nullable=False)  # 0-4 for the 5 buttons
    label = Column(String(8), nullable=False)  # e.g. 'ADDR', 'LINK'
    content = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<SmsQuickTool id={self.id} tenant_id={self.tenant_id} "
            f"user_id={self.user_id} slot={self.slot_index} label='{self.label}'>"
        )
