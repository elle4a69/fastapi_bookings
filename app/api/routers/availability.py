"""Availability endpoints supporting in-call and out-call 5-segment operational windows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant
from ...models.tenant import Tenant
from ...models.provider import Provider
from ...models.service import Service
from ...schemas.availability import AvailabilityQuery, AvailabilityResponse, TimeSlot
from ...services.availability_service import get_available_slots

router = APIRouter()


@router.get("/availability", tags=["availability"], response_model=AvailabilityResponse)
def availability(
    service_id: int = Query(..., description="Service ID"),
    provider_id: int = Query(..., description="Provider ID"),
    date: datetime = Query(..., description="Date for which availability is requested"),
    service_mode: str = Query("in_call", description="Delivery mode: in_call or out_call"),
    client_suburb: Optional[str] = Query(None, description="Client suburb for out-call transit resolution"),
    service_address: Optional[str] = Query(None, description="Client street address for out-call transit resolution"),
    client_postcode: Optional[str] = Query(None, description="Client postal code"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return available time slots for a provider and service on a specific date.

    Supports both in-call and out-call 5-segment operational windows.
    Backward compatible with all standard in-call availability requests.
    """
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.tenant_id == tenant.id).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    slots = get_available_slots(
        db=db,
        service_duration=service.duration,
        provider_id=provider_id,
        date=date,
        service_id=service.id,
        service_mode=service_mode,
        client_suburb=client_suburb,
        service_address=service_address,
        client_postcode=client_postcode,
    )

    formatted: List[Dict[str, Any]] = []
    for slot in slots:
        item: Dict[str, Any] = {
            "start": slot["start"].isoformat(),
            "end": slot["end"].isoformat(),
            "provider_id": provider.id,
            "provider_name": provider.name,
        }
        if "operational_window" in slot:
            item["operational_window"] = slot["operational_window"]
        formatted.append(item)

    return {"ok": True, "data": formatted}


@router.post("/availability", tags=["availability"], response_model=AvailabilityResponse)
def query_availability(
    query_in: AvailabilityQuery,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """POST endpoint for availability searches with structured body."""
    service = db.query(Service).filter(Service.id == query_in.service_id, Service.tenant_id == tenant.id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    if query_in.provider_id:
        provider = db.query(Provider).filter(Provider.id == query_in.provider_id, Provider.tenant_id == tenant.id).first()
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        prov_id = provider.id
    else:
        # Default to first active provider
        prov = db.query(Provider).filter(Provider.tenant_id == tenant.id, Provider.active.is_(True)).first()
        if not prov:
            return {"ok": True, "data": []}
        prov_id = prov.id

    slots = get_available_slots(
        db=db,
        service_duration=service.duration,
        provider_id=prov_id,
        date=query_in.date,
        service_id=service.id,
        service_mode=query_in.service_mode.value if hasattr(query_in.service_mode, "value") else str(query_in.service_mode),
        client_suburb=query_in.client_suburb,
        service_address=query_in.service_address,
        client_postcode=query_in.client_postcode,
    )

    formatted = []
    for slot in slots:
        item = {
            "start": slot["start"].isoformat(),
            "end": slot["end"].isoformat(),
            "provider_id": prov_id,
            "provider_name": getattr(provider if query_in.provider_id else prov, "name", None),
        }
        if "operational_window" in slot:
            item["operational_window"] = slot["operational_window"]
        formatted.append(item)

    return {"ok": True, "data": formatted}
