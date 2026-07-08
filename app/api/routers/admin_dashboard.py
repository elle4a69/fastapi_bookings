"""Admin dashboard bootstrap endpoint."""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.booking import Booking
from ...models.provider import Provider
from ...models.service import Service


router = APIRouter()


@router.get("/dashboard/bootstrap", tags=["dashboard"])
def admin_dashboard_bootstrap(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return aggregated data for the admin dashboard.

    This endpoint provides a summary of today's bookings, upcoming bookings,
    pending bookings and counts of key entities. It is intended to be
    called once when the dashboard loads to minimize initial requests.
    """
    now = datetime.utcnow()
    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1)
    # Today's bookings
    today_bookings = (
        db.query(Booking)
        .filter(
            Booking.start_time >= start_of_day,
            Booking.start_time < end_of_day,
            Booking.tenant_id == current_user.tenant_id
        )
        .all()
    )
    # Upcoming bookings (next 5)
    upcoming_bookings = (
        db.query(Booking)
        .filter(
            Booking.start_time >= now,
            Booking.status.in_(["pending", "confirmed"]),
            Booking.tenant_id == current_user.tenant_id
        )
        .order_by(Booking.start_time)
        .limit(5)
        .all()
    )
    # Pending bookings (all)
    pending_bookings = (
        db.query(Booking)
        .filter(
            Booking.status == "pending",
            Booking.tenant_id == current_user.tenant_id
        )
        .order_by(Booking.start_time)
        .all()
    )
    providers = db.query(Provider).filter(Provider.tenant_id == current_user.tenant_id).all()
    services = db.query(Service).filter(Service.tenant_id == current_user.tenant_id).all()
    summary = {
        "todayBookingCount": len(today_bookings),
        "upcomingBookingCount": db.query(Booking).filter(Booking.start_time >= now, Booking.tenant_id == current_user.tenant_id).count(),
        "pendingBookingCount": len(pending_bookings),
        "providerCount": db.query(Provider).filter(Provider.tenant_id == current_user.tenant_id).count(),
        "serviceCount": db.query(Service).filter(Service.tenant_id == current_user.tenant_id).count(),
    }
    return {
        "ok": True,
        "data": {
            "today": today_bookings,
            "upcomingBookings": upcoming_bookings,
            "pendingBookings": pending_bookings,
            "providers": providers,
            "services": services,
            "summary": summary,
        },
    }