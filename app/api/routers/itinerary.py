"""Admin and Operational routes for Provider Itinerary Recalculation & Conflict Sentinel."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..deps import get_current_staff, get_db
from ...schemas.itinerary import (
    ItineraryConflictListResponse,
    ItineraryRecalculateRequest,
    ItineraryRecalculationResult,
)
from ...services.booking.itinerary_service import (
    get_provider_itinerary_conflicts,
    recalculate_provider_itinerary,
)

router = APIRouter(tags=["itinerary"])


@router.get(
    "/itinerary/conflicts",
    response_model=ItineraryConflictListResponse,
    summary="List provider itinerary conflicts",
)
@router.get(
    "/api/admin/itinerary/conflicts",
    response_model=ItineraryConflictListResponse,
    include_in_schema=False,
)
def get_itinerary_conflicts(
    provider_id: Optional[int] = Query(None, description="Filter by provider ID"),
    date_from: Optional[date] = Query(None, description="Filter conflicts on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter conflicts on or before this date"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_staff),
) -> ItineraryConflictListResponse:
    """Retrieve operational itinerary conflicts flagged across active provider schedules."""
    # Scope provider if caller is a provider
    eff_provider_id = current_user.provider_id if current_user.role == "provider" else provider_id

    conflicts = get_provider_itinerary_conflicts(
        db,
        provider_id=eff_provider_id,
        tenant_id=current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    return ItineraryConflictListResponse(
        ok=True,
        conflicts=conflicts,
        total=len(conflicts),
    )


@router.post(
    "/itinerary/recalculate",
    response_model=ItineraryRecalculationResult,
    summary="Trigger dynamic itinerary recalculation",
)
@router.post(
    "/api/admin/itinerary/recalculate",
    response_model=ItineraryRecalculationResult,
    include_in_schema=False,
)
def trigger_itinerary_recalculation(
    payload: ItineraryRecalculateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_staff),
) -> ItineraryRecalculationResult:
    """Dynamically recalculate operational windows and 15-minute slot allocations for a provider and date."""
    target_provider_id = payload.provider_id
    if current_user.role == "provider" and target_provider_id != current_user.provider_id:
        target_provider_id = current_user.provider_id

    result = recalculate_provider_itinerary(
        db,
        provider_id=target_provider_id,
        target_date=payload.target_date,
    )
    db.commit()
    return result
