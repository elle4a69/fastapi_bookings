"""Admin dashboard bootstrap endpoint."""

from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.booking import Booking
from ...models.provider import Provider
from ...models.service import Service


router = APIRouter()


def _row_to_dict(row: object) -> dict[str, Any]:
    """Serialize a SQLAlchemy model using mapped column values only."""
    mapper = sa_inspect(row).mapper
    return {column.key: getattr(row, column.key) for column in mapper.column_attrs}


@router.get("/dashboard/bootstrap", tags=["dashboard"])
def admin_dashboard_bootstrap(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return aggregated data for the admin dashboard."""
    now = datetime.utcnow()
    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1)

    today_bookings = (
        db.query(Booking)
        .filter(
            Booking.start_time >= start_of_day,
            Booking.start_time < end_of_day,
            Booking.tenant_id == current_user.tenant_id,
        )
        .all()
    )
    upcoming_bookings = (
        db.query(Booking)
        .filter(
            Booking.start_time >= now,
            Booking.status.in_(["pending", "confirmed"]),
            Booking.tenant_id == current_user.tenant_id,
        )
        .order_by(Booking.start_time)
        .limit(5)
        .all()
    )
    pending_bookings = (
        db.query(Booking)
        .filter(
            Booking.status == "pending",
            Booking.tenant_id == current_user.tenant_id,
        )
        .order_by(Booking.start_time)
        .all()
    )
    providers = db.query(Provider).filter(Provider.tenant_id == current_user.tenant_id).all()
    services = db.query(Service).filter(Service.tenant_id == current_user.tenant_id).all()

    summary = {
        "todayBookingCount": len(today_bookings),
        "upcomingBookingCount": db.query(Booking)
        .filter(Booking.start_time >= now, Booking.tenant_id == current_user.tenant_id)
        .count(),
        "pendingBookingCount": len(pending_bookings),
        "providerCount": len(providers),
        "serviceCount": len(services),
    }
    return {
        "ok": True,
        "data": {
            "today": [_row_to_dict(row) for row in today_bookings],
            "upcomingBookings": [_row_to_dict(row) for row in upcoming_bookings],
            "pendingBookings": [_row_to_dict(row) for row in pending_bookings],
            "providers": [_row_to_dict(row) for row in providers],
            "services": [_row_to_dict(row) for row in services],
            "summary": summary,
        },
    }
