"""Travel and out-call routing API router.

Exposes public and administrative endpoints for:
1. Suburb/Postcode travel fee estimation: POST /api/public/travel/estimate
2. Exact street address travel quote: POST /api/public/travel/quote
3. Operational transit segment calculation: POST /api/public/travel/transit
4. Suburb / Postcode autocomplete typeahead: GET /api/public/travel/suburbs
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_tenant, get_db
from ...models.provider import Provider
from ...models.tenant import Tenant
from ...schemas.travel import (
    AddressAutocompleteItem,
    ChargeableTravelQuote,
    OperationalTransitRequest,
    OperationalTravelSegment,
    SuburbAutocompleteItem,
    TravelEstimateRequest,
    TravelQuoteRequest,
)
from ...services.routing.geocoding import search_addresses, search_au_suburbs
from ...services.routing.travel_service import TravelCalculationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/travel", tags=["travel"])


async def _resolve_tenant_and_provider(
    request: Request,
    provider_id: int,
    db: Session,
) -> tuple[Tenant, Provider]:
    """Resolve tenant and provider, ensuring multi-tenant isolation."""
    # 1. Attempt to resolve tenant from host / X-Tenant header
    request_tenant: Optional[Tenant] = None
    try:
        request_tenant = await get_current_tenant(request, db)
    except HTTPException:
        request_tenant = None

    # 2. Query provider
    query = db.query(Provider).filter(Provider.id == provider_id, Provider.deleted_at.is_(None))
    if request_tenant is not None:
        query = query.filter(Provider.tenant_id == request_tenant.id)

    provider = query.first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found.",
        )

    # 3. Resolve active tenant
    active_tenant = request_tenant or provider.tenant
    if not active_tenant:
        active_tenant = db.query(Tenant).filter(Tenant.id == provider.tenant_id).first()

    if not active_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant for provider not found.",
        )

    return active_tenant, provider


@router.get(
    "/addresses",
    response_model=list[AddressAutocompleteItem],
    summary="Autocomplete and standardize physical addresses with verification",
)
async def autocomplete_addresses(
    q: str = Query(..., min_length=2, description="Address search query prefix"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
) -> list[AddressAutocompleteItem]:
    """Instant lookup and standardization of Australian physical addresses with verification metadata."""
    raw_results = await search_addresses(query=q, limit=limit)
    return [AddressAutocompleteItem(**item) for item in raw_results]


@router.get(
    "/suburbs",
    response_model=list[SuburbAutocompleteItem],
    summary="Autocomplete Australian suburbs and postcodes for typeahead",
)
def autocomplete_suburbs(
    q: str = Query(..., min_length=1, description="Search query prefix (suburb name or postcode)"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
) -> list[SuburbAutocompleteItem]:
    """Instant lookup of Australian localities for frontend address autocomplete."""
    raw_results = search_au_suburbs(query=q, limit=limit)
    return [SuburbAutocompleteItem(**item) for item in raw_results]



@router.post(
    "/estimate",
    response_model=ChargeableTravelQuote,
    summary="Estimate out-call travel fee for suburb and optional postcode",
)
async def estimate_travel_fee(
    req: TravelEstimateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChargeableTravelQuote:
    """Calculate an estimated chargeable travel fee based on suburb/postcode centroid.

    Returns a ChargeableTravelQuote marked with is_estimate=True and contextual disclaimer.
    """
    tenant, provider = await _resolve_tenant_and_provider(request, req.provider_id, db)
    service = TravelCalculationService()
    try:
        quote = await service.estimate_suburb_travel(
            tenant=tenant,
            provider=provider,
            suburb=req.suburb,
            postcode=req.postcode,
        )
        return quote
    finally:
        await service.close()


@router.post(
    "/quote",
    response_model=ChargeableTravelQuote,
    summary="Calculate exact out-call travel fee for a destination address",
)
async def quote_travel_fee(
    req: TravelQuoteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChargeableTravelQuote:
    """Calculate the exact chargeable travel fee for a destination address.

    Honors tenant travel charge policy (ALWAYS_FROM_BASE or ACTUAL_ORIGIN)
    and validates provider out-call radius.
    """
    tenant, provider = await _resolve_tenant_and_provider(request, req.provider_id, db)
    service = TravelCalculationService()
    try:
        quote = await service.calculate_chargeable_travel(
            tenant=tenant,
            provider=provider,
            client_destination=req.service_address,
            is_estimate=False,
            previous_location=req.previous_booking_address,
        )
        return quote
    finally:
        await service.close()


@router.post(
    "/transit",
    response_model=OperationalTravelSegment,
    summary="Calculate operational transit distance and duration between waypoints",
)
async def calculate_operational_transit(
    req: OperationalTransitRequest,
) -> OperationalTravelSegment:
    """Calculate operational transit duration and distance between two waypoints.

    Used strictly for scheduling, calendar blocking, and turnaround buffers.
    """
    service = TravelCalculationService()
    try:
        segment = await service.calculate_operational_travel(
            origin_waypoint=req.origin,
            destination_waypoint=req.destination,
        )
        return segment
    finally:
        await service.close()
