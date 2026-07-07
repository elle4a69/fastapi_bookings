"""Notification and reminder models.

The notification layer is local-only. It stores reminder rules,
templates, generated notification records, queue/log entries and
device push tokens without calling any external provider.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    recipient_email = Column(String, nullable=True)
    type = Column(String, nullable=False, default="email")
    status = Column(String, nullable=False, default="pending")
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    booking = relationship("Booking")
    logs = relationship("NotificationLog", back_populates="notification")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} type={self.type} status={self.status}>"


class NotificationTemplate(Base):
    """Reusable notification content template."""

    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False, default="email")
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    locale = Column(String, nullable=False, default="en")
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rules = relationship("ReminderRule", back_populates="template")
    logs = relationship("NotificationLog", back_populates="template")


class ReminderRule(Base):
    """Defines when a reminder/notification should be generated."""

    __tablename__ = "reminder_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    event_type = Column(String, nullable=False, default="booking.start")
    channel = Column(String, nullable=False, default="email")
    audience = Column(String, nullable=False, default="client")
    timing = Column(String, nullable=False, default="before")
    offset_minutes = Column(Integer, nullable=False, default=1440)
    template_id = Column(Integer, ForeignKey("notification_templates.id"), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    conditions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    template = relationship("NotificationTemplate", back_populates="rules")
    logs = relationship("NotificationLog", back_populates="rule")


class NotificationLog(Base):
    """Audit log for queued, previewed and dispatched notifications."""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=True)
    outbox_event_id = Column(Integer, ForeignKey("outbox_events.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("notification_templates.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("reminder_rules.id"), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    channel = Column(String, nullable=False, default="email")
    recipient = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="queued")
    provider = Column(String, nullable=False, default="local-placeholder")
    gateway_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    dispatched_at = Column(DateTime, nullable=True)

    notification = relationship("Notification", back_populates="logs")
    template = relationship("NotificationTemplate", back_populates="logs")
    rule = relationship("ReminderRule", back_populates="logs")
    booking = relationship("Booking")
    client = relationship("Client")
    outbox_event = relationship("OutboxEvent")


class DeviceToken(Base):
    """Stores push-device tokens for FCM/APNs."""

    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_device_tokens_token"),)

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    token = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    client = relationship("Client")
    user = relationship("User")


class NotificationPreference(Base):
    """Per-client notification preferences."""

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("client_id", name="uq_notification_preferences_client_id"),)

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    email_enabled = Column(Boolean, default=True, nullable=False)
    sms_enabled = Column(Boolean, default=True, nullable=False)
    push_enabled = Column(Boolean, default=True, nullable=False)
    reminders_enabled = Column(Boolean, default=True, nullable=False)
    marketing_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    client = relationship("Client")