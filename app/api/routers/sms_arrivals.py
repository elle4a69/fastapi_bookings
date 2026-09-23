"""Public arrival capability and tenant-scoped staff arrival operations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.sms_arrival import (
    ArrivalAcknowledgeResponse,
    ArrivalCheckInRequest,
    ArrivalCheckInResponse,
    ArrivalListItem,
)
from ...services.sms.arrival_service import (
    ArrivalExpiredError,
    ArrivalNotFoundError,
    ArrivalStateError,
    acknowledge_arrival as acknowledge_arrival_service,
    arrival_expires_at,
    list_tenant_arrivals,
    mark_customer_arrived,
)

router = APIRouter(prefix="/sms/arrivals", tags=["sms-arrivals"])

_INVALID_CAPABILITY_DETAIL = "Arrival session is invalid or expired."


@router.post(
    "/public/arrive",
    response_model=ArrivalCheckInResponse,
    status_code=status.HTTP_200_OK,
)
async def client_arrive(
    payload: ArrivalCheckInRequest,
    db: Session = Depends(get_db),
) -> ArrivalCheckInResponse:
    """Consume an arrival capability supplied in the request body.

    The bearer value is intentionally excluded from paths, query strings,
    responses, logs and audit event metadata.
    """

    try:
        mutation = mark_customer_arrived(db, payload.token.get_secret_value())
    except (ArrivalNotFoundError, ArrivalExpiredError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_INVALID_CAPABILITY_DETAIL,
        ) from None
    except ArrivalStateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Arrival is not available for this booking.",
        ) from None
    db.commit()
    return ArrivalCheckInResponse(
        status="arrived" if mutation.changed else "already_arrived",
        arrived_at=mutation.scoped.session.arrived_at,
    )


@router.post(
    "/{arrival_id}/acknowledge",
    response_model=ArrivalAcknowledgeResponse,
    status_code=status.HTTP_200_OK,
)
async def acknowledge_arrival(
    arrival_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ArrivalAcknowledgeResponse:
    """Acknowledge and close an arrived session in the active tenant."""

    try:
        mutation = acknowledge_arrival_service(
            db,
            tenant_id=tenant.id,
            arrival_id=arrival_id,
            actor_user_id=admin.id,
        )
    except ArrivalNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arrival session not found.",
        ) from None
    except ArrivalStateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Arrival must be recorded before acknowledgement.",
        ) from None
    db.commit()
    return ArrivalAcknowledgeResponse(
        status="acknowledged" if mutation.changed else "already_acknowledged",
        acknowledged_at=mutation.scoped.session.acknowledged_at,
    )


@router.get("", response_model=list[ArrivalListItem])
async def list_arrivals(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[ArrivalListItem]:
    """List structural arrival state without bearer tokens or customer PII."""

    now = datetime.now(timezone.utc)
    results: list[ArrivalListItem] = []
    for scoped in list_tenant_arrivals(db, tenant_id=tenant.id):
        expires_at = arrival_expires_at(scoped.session, scoped.booking)
        if scoped.session.acknowledged_at is not None:
            lifecycle_state = "acknowledged"
        elif expires_at <= now:
            lifecycle_state = "expired"
        elif scoped.session.arrived_at is not None:
            lifecycle_state = "arrived"
        else:
            lifecycle_state = "invited"
        results.append(
            ArrivalListItem(
                id=scoped.session.id,
                booking_id=scoped.booking.id,
                conversation_id=scoped.conversation.id,
                provider_id=scoped.booking.provider_id,
                sms_account_id=scoped.account.id,
                service_id=scoped.booking.service_id,
                location_id=scoped.booking.location_id,
                state=lifecycle_state,
                arrived_at=scoped.session.arrived_at,
                acknowledged_at=scoped.session.acknowledged_at,
                created_at=scoped.session.created_at,
                expires_at=expires_at,
                booking_time=scoped.booking.start_time,
            )
        )
    return results
