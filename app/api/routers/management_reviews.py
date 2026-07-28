"""Management Review Request API routes.

Provides endpoints for restricted clients to submit review requests publicly,
and for administrators to list, view, and resolve them.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant, get_current_tenant, get_current_admin
from ...models.tenant import Tenant
from ...models.user import User
from ...models.client import Client as ClientModel
from ...models.service import Service as ServiceModel
from ...models.provider import Provider as ProviderModel
from ...models.location import Location as LocationModel
from ...models.management_review_request import ManagementReviewRequest as ReviewModel
from ...schemas.management_review_request import (
    ManagementReviewRequestCreate,
    ManagementReviewRequestUpdate,
    ManagementReviewRequestOut,
    ManagementReviewRequestListResponse,
    ManagementReviewRequestResponse,
)
from ...core.pagination import paginate_query, pagination_params

router = APIRouter()


@router.post("/api/public/management-reviews", response_model=ManagementReviewRequestResponse, tags=["management-reviews"])
def submit_review_request(
    payload: ManagementReviewRequestCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Submit a new management review request (public endpoint)."""
    # 1. Verify client belongs to active tenant
    client = db.query(ClientModel).filter(
        ClientModel.id == payload.client_id,
        ClientModel.tenant_id == tenant.id,
        ClientModel.deleted_at.is_(None)
    ).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # 2. Verify service, provider, location if provided
    if payload.service_id:
        if not db.query(ServiceModel).filter(ServiceModel.id == payload.service_id, ServiceModel.tenant_id == tenant.id, ServiceModel.deleted_at.is_(None)).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    if payload.provider_id:
        if not db.query(ProviderModel).filter(ProviderModel.id == payload.provider_id, ProviderModel.tenant_id == tenant.id, ProviderModel.deleted_at.is_(None)).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if payload.location_id:
        if not db.query(LocationModel).filter(LocationModel.id == payload.location_id, LocationModel.tenant_id == tenant.id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # 3. Check for active duplicates
    duplicate = None
    if payload.preferred_time:
        pending_requests = db.query(ReviewModel).filter(
            ReviewModel.tenant_id == tenant.id,
            ReviewModel.client_id == payload.client_id,
            ReviewModel.service_id == payload.service_id,
            ReviewModel.state == "pending"
        ).all()
        for req in pending_requests:
            if req.preferred_time:
                # Normalize timezones for comparison
                t1 = req.preferred_time.astimezone(timezone.utc) if req.preferred_time.tzinfo else req.preferred_time.replace(tzinfo=timezone.utc)
                t2 = payload.preferred_time.astimezone(timezone.utc) if payload.preferred_time.tzinfo else payload.preferred_time.replace(tzinfo=timezone.utc)
                if abs((t1 - t2).total_seconds()) < 1.0:
                    duplicate = req
                    break
    else:
        duplicate = db.query(ReviewModel).filter(
            ReviewModel.tenant_id == tenant.id,
            ReviewModel.client_id == payload.client_id,
            ReviewModel.service_id == payload.service_id,
            ReviewModel.preferred_time.is_(None),
            ReviewModel.state == "pending"
        ).first()

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending review request already exists for this slot."
        )

    # 4. Create request
    review = ReviewModel(
        tenant_id=tenant.id,
        client_id=payload.client_id,
        service_id=payload.service_id,
        provider_id=payload.provider_id,
        location_id=payload.location_id,
        preferred_time=payload.preferred_time,
        reason=payload.reason,
        state="pending",
        slot_reserved=False,
        payment_taken=False
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {"ok": True, "data": review}


@router.get("/api/admin/management-reviews", response_model=ManagementReviewRequestListResponse, tags=["management-reviews"])
def list_review_requests(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """List all review requests for the active tenant (admin endpoint)."""
    query = db.query(ReviewModel).filter(ReviewModel.tenant_id == tenant.id).order_by(ReviewModel.created_at.desc())
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.get("/api/admin/management-reviews/{review_id}", response_model=ManagementReviewRequestResponse, tags=["management-reviews"])
def get_review_request(
    review_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Retrieve details of a review request."""
    review = db.query(ReviewModel).filter(ReviewModel.id == review_id, ReviewModel.tenant_id == tenant.id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review request not found")
    return {"ok": True, "data": review}


@router.put("/api/admin/management-reviews/{review_id}/resolve", response_model=ManagementReviewRequestResponse, tags=["management-reviews"])
def resolve_review_request(
    review_id: int,
    payload: ManagementReviewRequestUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Resolve a review request (approve or reject)."""
    review = db.query(ReviewModel).filter(ReviewModel.id == review_id, ReviewModel.tenant_id == tenant.id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review request not found")
    if review.state != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review request has already been resolved")

    if payload.state:
        if payload.state not in ("approved", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target state")
        review.state = payload.state

    review.resolution_notes = payload.resolution_notes
    review.resolved_by_id = current_user.id
    review.resolved_at = datetime.now(timezone.utc)
    review.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(review)
    return {"ok": True, "data": review}
