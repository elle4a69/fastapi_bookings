"""Data retention and cleanup service.

Implements policies for GDPR-compliant client anonymisation, and cleanup of
historic bookings, notifications, and audit logs.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import uuid

from ..models.client import Client
from ..models.booking import Booking
from ..models.audit import AuditLog
from ..models.notification import Notification, NotificationLog
from ..core.state_machine import BookingStatus


def anonymize_client(db: Session, client_id: int, tenant_id: int) -> bool:
    """Anonymize a client record to comply with GDPR 'Right to be Forgotten' request,

    while keeping historical references (e.g. bookings, invoices) intact.
    """
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant_id).first()
    if not client:
        return False

    unique_id = str(uuid.uuid4())[:8]
    client.name = "Anonymized Client"
    client.email = f"anonymized-{unique_id}@example.com"
    client.phone = "0000000000"
    client.address_line1 = None
    client.address_line2 = None
    client.city = None
    client.state = None
    client.postcode = None
    client.country = None
    client.notes = "Client anonymized under GDPR Right to be Forgotten."
    client.active = False
    client.deleted_at = datetime.now(timezone.utc)

    db.commit()
    return True


def cleanup_historic_records(db: Session, tenant_id: int, days_threshold: int = 365) -> dict:
    """Delete log entries, notifications, and cancelled bookings older than a threshold (in days)."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

    # 1. Delete old notification logs
    deleted_noti_logs = db.query(NotificationLog).filter(
        NotificationLog.created_at < cutoff_date
    ).delete(synchronize_session=False)

    # 2. Delete old notifications (must handle foreign key in notification_logs first)
    deleted_notis = db.query(Notification).filter(
        Notification.tenant_id == tenant_id,
        Notification.created_at < cutoff_date
    ).delete(synchronize_session=False)

    # 3. Delete old audit logs
    deleted_audit = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.timestamp < cutoff_date
    ).delete(synchronize_session=False)

    # 4. Delete cancelled bookings
    deleted_bookings = db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.status == BookingStatus.CANCELLED,
        Booking.start_time < cutoff_date
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "deleted_notification_logs": deleted_noti_logs,
        "deleted_notifications": deleted_notis,
        "deleted_audit_logs": deleted_audit,
        "deleted_cancelled_bookings": deleted_bookings
    }
