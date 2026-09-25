"""Client Self-Service Portal & Dispute Center API router.

Provides endpoints for:
- Client passwordless OTP authentication & token issuance
- Client profile inspection
- Client booking overview, 1-tap reschedule, and 1-tap cancellation
- Client invoice and receipt lookup
- Client quality dispute lodging & status tracking
- Admin dispute triage and resolution
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.redis import get_redis_client
from ...core.security import create_access_token
from ...core.state_machine import BookingStatus
from ...db.database import get_db
from ...models.booking import Booking
from ...models.client import Client
from ...models.client_dispute import ClientDispute
from ...models.checkout import Invoice
from ...models.provider import Provider
from ...models.service import Service
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.client_portal import (
    ClientOtpSendRequest,
    ClientOtpVerifyRequest,
    ClientProfile,
    ClientPortalAuthResponse,
    ClientPortalAuthData,
    ClientBookingItem,
    ClientRescheduleRequest,
    ClientCancelRequest,
    ClientInvoiceItem,
    ClientInvoiceLineItem,
    ClientDisputeCreate,
    ClientDisputeResponse,
    AdminDisputeResolveRequest,
)
from ..deps import get_current_tenant, get_current_client, get_current_admin


router = APIRouter(tags=["client_portal"])

OTP_TTL_SECONDS = 600
OTP_RATE_LIMIT_MAX = 3

VERIFY_AND_DELETE_LUA = """
local current = redis.call('get', KEYS[1])
if current and current == ARGV[1] then
    redis.call('del', KEYS[1])
    return 1
else
    return 0
end
"""

# Resilient in-memory fallback stores if Redis is temporarily unreachable
_OTP_FALLBACK: Dict[str, Dict[str, any]] = {}
_OTP_RATE_FALLBACK: Dict[str, List[datetime]] = {}


def _normalize_target(target: str) -> str:
    cleaned = target.strip().lower()
    # If phone digits
    digits = "".join(c for c in cleaned if c.isdigit())
    if len(digits) >= 8 and "@" not in cleaned:
        return digits
    return cleaned


@router.post("/api/portal/auth/send-otp")
def send_client_otp(
    payload: ClientOtpSendRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Generate and dispatch a 6-digit OTP code for client portal authentication."""
    raw_target = payload.phone_or_email.strip()
    if not raw_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number or email is required.",
        )

    norm = _normalize_target(raw_target)
    phone_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    cache_key = f"fb:otp:{tenant.id}:{phone_hash}"
    rate_key = f"fb:otp_rate:{tenant.id}:{phone_hash}"
    code = f"{random.randint(100000, 999999)}"

    # Redis rate limit and store with resilient fallback
    try:
        r = get_redis_client()
        count = r.incr(rate_key)
        if count == 1:
            r.expire(rate_key, OTP_TTL_SECONDS)
        if count > OTP_RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait 10 minutes before trying again.",
            )
        r.set(cache_key, code, ex=OTP_TTL_SECONDS)
    except HTTPException:
        raise
    except Exception:
        now = datetime.now(timezone.utc)
        rate_history = [
            t for t in _OTP_RATE_FALLBACK.get(rate_key, [])
            if (now - t).total_seconds() < OTP_TTL_SECONDS
        ]
        if len(rate_history) >= OTP_RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait 10 minutes before trying again.",
            )
        rate_history.append(now)
        _OTP_RATE_FALLBACK[rate_key] = rate_history
        _OTP_FALLBACK[cache_key] = {
            "code": code,
            "expires_at": now + timedelta(seconds=OTP_TTL_SECONDS),
        }

    # Find client by phone or email if already registered
    client = (
        db.query(Client)
        .filter(
            Client.tenant_id == tenant.id,
            or_(
                func.lower(Client.email) == raw_target.lower(),
                Client.phone == raw_target,
                Client.phone == norm,
            ),
        )
        .first()
    )

    is_prod = settings.APP_ENV.lower() in ("production", "prod")
    resp = {
        "ok": True,
        "message": f"Verification code sent to {raw_target}",
        "client_exists": client is not None,
    }
    if not is_prod:
        resp["demo_code"] = "123456"
        resp["active_code"] = code

    return resp


@router.post("/api/portal/auth/verify-otp", response_model=ClientPortalAuthResponse)
def verify_client_otp(
    payload: ClientOtpVerifyRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Verify the 6-digit OTP code and return signed JWT client portal access token."""
    raw_target = payload.phone_or_email.strip()
    submitted_code = payload.code.strip()

    if not raw_target or not submitted_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both target identifier and OTP code are required.",
        )

    norm = _normalize_target(raw_target)
    phone_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    cache_key = f"fb:otp:{tenant.id}:{phone_hash}"

    is_valid = False
    is_prod = settings.APP_ENV.lower() in ("production", "prod")

    # In non-production environments only, allow demo code for local/frictionless testing
    if not is_prod and submitted_code in ("123456", "000000"):
        is_valid = True
    else:
        # Atomic verification and consumption via Redis Lua script
        try:
            r = get_redis_client()
            result = r.eval(VERIFY_AND_DELETE_LUA, 1, cache_key, submitted_code)
            if result == 1:
                is_valid = True
        except Exception:
            cached = _OTP_FALLBACK.get(cache_key)
            if (
                cached
                and cached["code"] == submitted_code
                and cached["expires_at"] > datetime.now(timezone.utc)
            ):
                is_valid = True
                _OTP_FALLBACK.pop(cache_key, None)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    # Locate existing client
    client = (
        db.query(Client)
        .filter(
            Client.tenant_id == tenant.id,
            or_(
                func.lower(Client.email) == raw_target.lower(),
                Client.phone == raw_target,
                Client.phone == norm,
            ),
        )
        .first()
    )

    # If client does not exist, provision a guest record
    if not client:
        is_email = "@" in raw_target
        client = Client(
            tenant_id=tenant.id,
            name=raw_target.split("@")[0].title() if is_email else f"Client {raw_target[-4:]}",
            email=raw_target.lower() if is_email else None,
            phone=raw_target if not is_email else None,
            active=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)

    token = create_access_token(
        {
            "sub": str(client.id),
            "role": "client",
            "tenant_id": tenant.id,
            "name": client.name,
        }
    )

    return ClientPortalAuthResponse(
        ok=True,
        message="Client verified successfully",
        data=ClientPortalAuthData(
            access_token=token,
            token_type="bearer",
            client=ClientProfile.model_validate(client),
        ),
    )


@router.get("/api/portal/me", response_model=ClientProfile)
def get_client_profile(
    client: Client = Depends(get_current_client),
):
    """Return authenticated client profile details."""
    return ClientProfile.model_validate(client)


@router.get("/api/portal/bookings", response_model=List[ClientBookingItem])
def list_client_bookings(
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """List all appointments belonging to the authenticated client."""
    bookings = (
        db.query(Booking)
        .filter(
            Booking.tenant_id == tenant.id,
            Booking.client_id == client.id,
        )
        .order_by(Booking.start_time.asc())
        .all()
    )

    # Preload disputes for client
    disputes = (
        db.query(ClientDispute)
        .filter(
            ClientDispute.tenant_id == tenant.id,
            ClientDispute.client_id == client.id,
        )
        .all()
    )
    dispute_by_booking = {d.booking_id: d for d in disputes if d.booking_id}

    items = []
    now = datetime.now(timezone.utc)
    for b in bookings:
        service_name = b.service.name if b.service else "Service"
        provider_name = b.provider.name if b.provider else "Staff"
        location_name = b.location.name if b.location else "Main Center"
        price = float(b.service.price) if (b.service and b.service.price) else 0.0
        duration = b.service.duration if (b.service and b.service.duration) else int((b.end_time - b.start_time).total_seconds() / 60)

        # Status string
        status_val = b.status.value if hasattr(b.status, "value") else str(b.status)
        is_active = status_val.lower() in ("pending", "confirmed")
        st = b.start_time
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        is_upcoming = st > now

        disp = dispute_by_booking.get(b.id)


        item = ClientBookingItem(
            id=b.id,
            tenant_id=b.tenant_id,
            client_id=b.client_id,
            provider_id=b.provider_id,
            service_id=b.service_id,
            location_id=b.location_id,
            start_time=b.start_time,
            end_time=b.end_time,
            status=status_val,
            notes=b.notes,
            service_name=service_name,
            provider_name=provider_name,
            location_name=location_name,
            price=price,
            duration=duration,
            can_reschedule=is_active and is_upcoming,
            can_cancel=is_active,
            has_dispute=disp is not None,
            dispute_id=disp.id if disp else None,
            dispute_status=disp.status if disp else None,
        )
        items.append(item)

    return items


@router.post("/api/portal/bookings/{booking_id}/reschedule", response_model=ClientBookingItem)
def client_reschedule_booking(
    booking_id: int,
    payload: ClientRescheduleRequest,
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """1-Tap Reschedule an upcoming appointment to a new start time."""
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.tenant_id == tenant.id,
        )
        .first()
    )

    if not booking or booking.client_id != client.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or not authorized for this client.",
        )

    current_status = booking.status.value if hasattr(booking.status, "value") else str(booking.status)
    if current_status.lower() in ("cancelled", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule a booking with status '{current_status}'.",
        )

    # Compute duration
    b_end = booking.end_time.replace(tzinfo=timezone.utc) if booking.end_time.tzinfo is None else booking.end_time
    b_start = booking.start_time.replace(tzinfo=timezone.utc) if booking.start_time.tzinfo is None else booking.start_time
    duration = b_end - b_start
    new_start = payload.start_time
    if new_start.tzinfo is None:
        new_start = new_start.replace(tzinfo=timezone.utc)
    new_end = new_start + duration


    # Check provider conflicting bookings
    conflict = (
        db.query(Booking)
        .filter(
            Booking.tenant_id == tenant.id,
            Booking.provider_id == booking.provider_id,
            Booking.id != booking.id,
            Booking.status.notin_([BookingStatus.CANCELLED, "cancelled", "CANCELLED"]),
            Booking.start_time < new_end,
            Booking.end_time > new_start,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested time slot conflicts with an existing provider booking.",
        )

    booking.start_time = new_start
    booking.end_time = new_end
    booking.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)

    service_name = booking.service.name if booking.service else "Service"
    provider_name = booking.provider.name if booking.provider else "Staff"
    location_name = booking.location.name if booking.location else "Main Center"
    price = float(booking.service.price) if (booking.service and booking.service.price) else 0.0
    duration_mins = int((booking.end_time - booking.start_time).total_seconds() / 60)

    return ClientBookingItem(
        id=booking.id,
        tenant_id=booking.tenant_id,
        client_id=booking.client_id,
        provider_id=booking.provider_id,
        service_id=booking.service_id,
        location_id=booking.location_id,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status=booking.status.value if hasattr(booking.status, "value") else str(booking.status),
        notes=booking.notes,
        service_name=service_name,
        provider_name=provider_name,
        location_name=location_name,
        price=price,
        duration=duration_mins,
        can_reschedule=True,
        can_cancel=True,
        has_dispute=False,
    )


@router.post("/api/portal/bookings/{booking_id}/cancel")
def client_cancel_booking(
    booking_id: int,
    payload: Optional[ClientCancelRequest] = None,
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """1-Tap Cancel an appointment with an optional cancellation note."""
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.tenant_id == tenant.id,
        )
        .first()
    )

    if not booking or booking.client_id != client.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or not authorized for this client.",
        )

    booking.status = BookingStatus.CANCELLED
    booking.updated_at = datetime.now(timezone.utc)
    if payload and payload.reason:
        reason_line = f"Client cancellation reason: {payload.reason.strip()}"
        booking.notes = f"{booking.notes}\n{reason_line}" if booking.notes else reason_line

    db.commit()
    return {"ok": True, "message": "Booking cancelled successfully."}


@router.get("/api/portal/invoices", response_model=List[ClientInvoiceItem])
def list_client_invoices(
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Retrieve billing history and receipts for the authenticated client."""
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant.id,
            Invoice.client_id == client.id,
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )

    result = []
    for inv in invoices:
        service_name = None
        if inv.booking and inv.booking.service:
            service_name = inv.booking.service.name

        lines = [
            ClientInvoiceLineItem(
                id=line.id,
                description=line.description or "Service charge",
                quantity=line.quantity,
                unit_price=float(line.unit_price),
                total=float(line.total),
            )
            for line in (inv.lines or [])
        ]

        result.append(
            ClientInvoiceItem(
                id=inv.id,
                tenant_id=inv.tenant_id,
                booking_id=inv.booking_id,
                service_name=service_name,
                subtotal=float(inv.subtotal),
                discount_total=float(inv.discount_total),
                tax_total=float(inv.tax_total),
                tip_total=float(inv.tip_total),
                total=float(inv.total),
                amount_paid=float(inv.amount_paid),
                status=inv.status,
                currency=inv.currency,
                notes=inv.notes,
                created_at=inv.created_at,
                lines=lines,
            )
        )

    return result


@router.post("/api/portal/disputes", response_model=ClientDisputeResponse)
def lodge_client_dispute(
    payload: ClientDisputeCreate,
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Lodge a quality or billing dispute for a service booking."""
    booking = None
    booking_service_name = None
    booking_start_time = None

    if payload.booking_id:
        booking = (
            db.query(Booking)
            .filter(
                Booking.id == payload.booking_id,
                Booking.tenant_id == tenant.id,
            )
            .first()
        )
        if not booking or booking.client_id != client.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or does not belong to the current client.",
            )
        if booking.service:
            booking_service_name = booking.service.name
        booking_start_time = booking.start_time

    dispute = ClientDispute(
        tenant_id=tenant.id,
        client_id=client.id,
        booking_id=payload.booking_id,
        status="submitted",
        reason=payload.reason,
        description=payload.description.strip(),
        preferred_resolution=payload.preferred_resolution,
        photos=payload.photos or [],
        created_at=datetime.now(timezone.utc),
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return ClientDisputeResponse(
        id=dispute.id,
        tenant_id=dispute.tenant_id,
        client_id=dispute.client_id,
        client_name=client.name,
        client_phone=client.phone,
        client_email=client.email,
        booking_id=dispute.booking_id,
        booking_service_name=booking_service_name,
        booking_start_time=booking_start_time,
        status=dispute.status,
        reason=dispute.reason,
        description=dispute.description,
        preferred_resolution=dispute.preferred_resolution,
        resolution_notes=dispute.resolution_notes,
        photos=dispute.photos,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )


@router.get("/api/portal/disputes", response_model=List[ClientDisputeResponse])
def list_client_disputes(
    client: Client = Depends(get_current_client),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Retrieve all dispute cases filed by the authenticated client."""
    disputes = (
        db.query(ClientDispute)
        .filter(
            ClientDispute.tenant_id == tenant.id,
            ClientDispute.client_id == client.id,
        )
        .order_by(ClientDispute.created_at.desc())
        .all()
    )

    items = []
    for d in disputes:
        booking_service_name = None
        booking_start_time = None
        if d.booking:
            if d.booking.service:
                booking_service_name = d.booking.service.name
            booking_start_time = d.booking.start_time

        items.append(
            ClientDisputeResponse(
                id=d.id,
                tenant_id=d.tenant_id,
                client_id=d.client_id,
                client_name=client.name,
                client_phone=client.phone,
                client_email=client.email,
                booking_id=d.booking_id,
                booking_service_name=booking_service_name,
                booking_start_time=booking_start_time,
                status=d.status,
                reason=d.reason,
                description=d.description,
                preferred_resolution=d.preferred_resolution,
                resolution_notes=d.resolution_notes,
                photos=d.photos,
                created_at=d.created_at,
                resolved_at=d.resolved_at,
            )
        )
    return items


# ==========================================
# ADMIN DISPUTE RESOLUTION ENDPOINTS
# ==========================================


@router.get("/api/admin/disputes", response_model=List[ClientDisputeResponse])
def admin_list_disputes(
    status_filter: Optional[str] = None,
    admin: User = Depends(get_current_admin),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """List all client disputes for the tenant with optional status filter."""
    query = (
        db.query(ClientDispute)
        .filter(ClientDispute.tenant_id == tenant.id)
    )
    if status_filter:
        query = query.filter(ClientDispute.status == status_filter.lower())

    disputes = query.order_by(ClientDispute.created_at.desc()).all()

    items = []
    for d in disputes:
        client_name = d.client.name if d.client else f"Client #{d.client_id}"
        client_phone = d.client.phone if d.client else None
        client_email = d.client.email if d.client else None

        booking_service_name = None
        booking_start_time = None
        if d.booking:
            if d.booking.service:
                booking_service_name = d.booking.service.name
            booking_start_time = d.booking.start_time

        items.append(
            ClientDisputeResponse(
                id=d.id,
                tenant_id=d.tenant_id,
                client_id=d.client_id,
                client_name=client_name,
                client_phone=client_phone,
                client_email=client_email,
                booking_id=d.booking_id,
                booking_service_name=booking_service_name,
                booking_start_time=booking_start_time,
                status=d.status,
                reason=d.reason,
                description=d.description,
                preferred_resolution=d.preferred_resolution,
                resolution_notes=d.resolution_notes,
                photos=d.photos,
                created_at=d.created_at,
                resolved_at=d.resolved_at,
            )
        )
    return items


@router.put("/api/admin/disputes/{dispute_id}/resolve", response_model=ClientDisputeResponse)
def admin_resolve_dispute(
    dispute_id: int,
    payload: AdminDisputeResolveRequest,
    admin: User = Depends(get_current_admin),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Review and update the status of a dispute (under_review, resolved, rejected)."""
    dispute = (
        db.query(ClientDispute)
        .filter(
            ClientDispute.id == dispute_id,
            ClientDispute.tenant_id == tenant.id,
        )
        .first()
    )

    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispute not found.",
        )

    dispute.status = payload.status.lower()
    if payload.resolution_notes is not None:
        dispute.resolution_notes = payload.resolution_notes

    if payload.status.lower() in ("resolved", "rejected"):
        dispute.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(dispute)

    client_name = dispute.client.name if dispute.client else f"Client #{dispute.client_id}"
    client_phone = dispute.client.phone if dispute.client else None
    client_email = dispute.client.email if dispute.client else None

    booking_service_name = None
    booking_start_time = None
    if dispute.booking:
        if dispute.booking.service:
            booking_service_name = dispute.booking.service.name
        booking_start_time = dispute.booking.start_time

    return ClientDisputeResponse(
        id=dispute.id,
        tenant_id=dispute.tenant_id,
        client_id=dispute.client_id,
        client_name=client_name,
        client_phone=client_phone,
        client_email=client_email,
        booking_id=dispute.booking_id,
        booking_service_name=booking_service_name,
        booking_start_time=booking_start_time,
        status=dispute.status,
        reason=dispute.reason,
        description=dispute.description,
        preferred_resolution=dispute.preferred_resolution,
        resolution_notes=dispute.resolution_notes,
        photos=dispute.photos,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )
