"""Search availability API routes.

This endpoint allows the client to search for available appointment
options using a flexible set of criteria.  A booking flow can start
from location, provider, category, service or a desired time range.
The scheduling engine returns possible combinations of service,
provider, location, resource and time.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models import Service, Provider, Location, Category, Tenant
from ...services import scheduling_service
from ..deps import get_public_tenant


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
    tenant: Tenant = Depends(get_public_tenant),
) -> Any:
    """Search for availability using flexible criteria.

    Returns a list of available options.  Each option may include the
    service, provider, location, resource and time.
    """
    service = None
    if query.service_id:
        service = db.query(Service).filter(Service.id == query.service_id, Service.tenant_id == tenant.id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if query.provider_id:
        provider = db.query(Provider).filter(Provider.id == query.provider_id, Provider.tenant_id == tenant.id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    location = None
    if query.location_id:
        location = db.query(Location).filter(Location.id == query.location_id, Location.tenant_id == tenant.id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
    
    # Determine time window and enforce timezone awareness
    start_time = query.date_from or datetime.now(timezone.utc)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    
    end_time = query.date_to or (start_time + timedelta(days=7))
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
        
    results = []
    if service:
        raw_results = scheduling_service.compute_availability(
            db,
            service=service,
            provider=provider,
            location=location,
            start_time=start_time,
            end_time=end_time,
        )
        for slot in raw_results:
            slot_copy = dict(slot)
            slot_copy["service"] = {"id": service.id, "name": service.name}
            results.append(slot_copy)
    else:
        services = db.query(Service).filter(Service.tenant_id == tenant.id, Service.active == True).all()
        if query.category_id is not None:
            services = [
                s for s in services 
                if getattr(s, "category_id", None) == query.category_id 
                or any(sc.category_id == query.category_id for sc in s.categories)
            ]
        for s in services:
            service_slots = scheduling_service.compute_availability(
                db,
                service=s,
                provider=provider,
                location=location,
                start_time=start_time,
                end_time=end_time,
            )
            for slot in service_slots:
                slot_copy = dict(slot)
                slot_copy["service"] = {"id": s.id, "name": s.name}
                results.append(slot_copy)

    return {"ok": True, "data": results, "meta": {"count": len(results)}}