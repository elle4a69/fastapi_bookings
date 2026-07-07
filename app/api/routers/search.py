"""Search availability API routes.

This endpoint allows the client to search for available appointment
options using a flexible set of criteria.  A booking flow can start
from location, provider, category, service or a desired time range.
The scheduling engine returns possible combinations of service,
provider, location, resource and time.
"""

from datetime import datetime, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models import Service, Provider, Location, Category
from ...services import scheduling_service


class AvailabilitySearchQuery(BaseModel):
    location_id: Optional[int] = Field(None, description="Restrict to a specific location")
    provider_id: Optional[int] = Field(None, description="Restrict to a specific provider")
    category_id: Optional[int] = Field(None, description="Restrict to services in this category")
    service_id: Optional[int] = Field(None, description="Restrict to a specific service")
    desired_time: Optional[str] = Field(
        None,
        description=(
            "Time of day preference such as 'morning', 'afternoon', 'evening' or a specific ISO "
            "timestamp"
        ),
    )
    date_from: Optional[datetime] = Field(None, description="Earliest acceptable date/time")
    date_to: Optional[datetime] = Field(None, description="Latest acceptable date/time")


router = APIRouter(prefix="/api/public/search-availability", tags=["search-availability"])


@router.post("", response_model=Any)
def search_availability(
    query: AvailabilitySearchQuery,
    db: Session = Depends(get_db),
) -> Any:
    """Search for availability using flexible criteria.

    Returns a list of available options.  Each option may include the
    service, provider, location, resource and time.  This function
    currently returns an empty list as the scheduling engine is not yet
    implemented.
    """
    service = None
    if query.service_id:
        service = db.query(Service).filter(Service.id == query.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if query.provider_id:
        provider = db.query(Provider).filter(Provider.id == query.provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    location = None
    if query.location_id:
        location = db.query(Location).filter(Location.id == query.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
    # Determine time window
    start_time = query.date_from or datetime.utcnow()
    end_time = query.date_to or (start_time + timedelta(days=7))  # default to one week window
    # Compute availability (stub)
    if service:
        results = scheduling_service.compute_availability(
            db,
            service=service,
            provider=provider,
            location=location,
            start_time=start_time,
            end_time=end_time,
        )
    else:
        # When no service is specified you might need to iterate over
        # multiple services or categories.  This is not yet
        # implemented.
        results = []
    return {"ok": True, "data": results, "meta": {"count": len(results)}}