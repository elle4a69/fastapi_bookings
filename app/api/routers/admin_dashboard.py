"""Admin dashboard bootstrap endpoint."""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.booking import Booking as BookingModel
from ...models.provider import Provider as ProviderModel
from ...models.service import Service as ServiceModel
from ...schemas.booking import Booking as BookingSchema
from ...schemas.provider import Provider as ProviderSchema
from ...schemas.service import Service as ServiceSchema


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
        db.query(BookingModel)
        .filter(BookingModel.start_time >= start_of_day, BookingModel.start_time < end_of_day)
        .all()
    )
    # Upcoming bookings (next 5)
    upcoming_bookings = (
        db.query(BookingModel)
        .filter(BookingModel.start_time >= now, BookingModel.status.in_(["pending", "confirmed"]))
        .order_by(BookingModel.start_time)
        .limit(5)
        .all()
    )
    # Pending bookings (all)
    pending_bookings = (
        db.query(BookingModel)
        .filter(BookingModel.status == "pending")
        .order_by(BookingModel.start_time)
        .all()
    )
    providers = db.query(ProviderModel).all()
    services = db.query(ServiceModel).all()
    summary = {
        "todayBookingCount": len(today_bookings),
        "upcomingBookingCount": db.query(BookingModel).filter(BookingModel.start_time >= now).count(),
        "pendingBookingCount": len(pending_bookings),
        "providerCount": db.query(ProviderModel).count(),
        "serviceCount": db.query(ServiceModel).count(),
    }
    
    # Serialize ORM models to Pydantic schemas
    serialized_today = [BookingSchema.model_validate(b).model_dump() for b in today_bookings]
    serialized_upcoming = [BookingSchema.model_validate(b).model_dump() for b in upcoming_bookings]
    serialized_pending = [BookingSchema.model_validate(b).model_dump() for b in pending_bookings]
    serialized_providers = [ProviderSchema.model_validate(p).model_dump() for p in providers]
    serialized_services = [ServiceSchema.model_validate(s).model_dump() for s in services]
    
    return {
        "ok": True,
        "data": {
            "today": serialized_today,
            "upcomingBookings": serialized_upcoming,
            "pendingBookings": serialized_pending,
            "providers": serialized_providers,
            "services": serialized_services,
            "summary": summary,
        },
    }