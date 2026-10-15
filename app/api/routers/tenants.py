"""Tenants API Router.

Provides endpoints for creating, managing, and retrieving Tenants,
with lifecycle hooks, subscription management, tenant isolation gates,
and automated Chatwoot multi-tenant provisioning.
"""

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, require_platform_owner
from ...core.config import settings
from ...core.security import decode_access_token
from ...models.tenant import Tenant
from ...models.user import User
from ...models.invitation import TenantInvitation
from ...models.audit import AuditLog
from ...schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantOut,
    TenantSuspendRequest,
)
from ...schemas.invitation import InvitationCreate, InvitationResponse, InvitationOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Create a new tenant, initial owner invitation, and optionally auto-provision Chatwoot infrastructure.

    Strictly protected: requires platform owner privileges.
    """
    # Enforce subdomain uniqueness
    existing_subdomain = db.query(Tenant).filter(
        Tenant.subdomain == payload.subdomain.lower().strip()
    ).first()
    if existing_subdomain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant subdomain '{payload.subdomain}' is already taken.",
        )

    existing_name = db.query(Tenant).filter(
        Tenant.name == payload.name.strip()
    ).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant name '{payload.name}' already exists.",
        )

    tenant_data = payload.model_dump()
    tenant = Tenant(
        name=tenant_data["name"].strip(),
        subdomain=tenant_data["subdomain"].lower().strip(),
        status="active",
        timezone=tenant_data.get("timezone", "UTC"),
        country=tenant_data.get("country"),
        email=tenant_data.get("email"),
        phone=tenant_data.get("phone"),
        website=tenant_data.get("website"),
        public_address_visibility=tenant_data.get("public_address_visibility", "visible"),
        max_advance_days=tenant_data.get("max_advance_days", 60),
        address=tenant_data.get("address"),
        latitude=tenant_data.get("latitude"),
        longitude=tenant_data.get("longitude"),
        logo_url=tenant_data.get("logo_url"),
        allow_in_call=tenant_data.get("allow_in_call", True),
        allow_out_call=tenant_data.get("allow_out_call", True),
        travel_charge_origin=(
            tenant_data["travel_charge_origin"].value
            if hasattr(tenant_data.get("travel_charge_origin"), "value")
            else str(tenant_data.get("travel_charge_origin", "ALWAYS_FROM_BASE"))
        ),
        subscription_tier=tenant_data.get("subscription_tier", "starter"),
        chatwoot_account_id=tenant_data.get("chatwoot_account_id"),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # Issue initial owner invitation if owner_email or tenant email provided
    target_owner_email = payload.owner_email or payload.email
    invitation_token = None
    if target_owner_email:
        raw_token = secrets.token_urlsafe(32)
        invitation = TenantInvitation(
            tenant_id=tenant.id,
            email=target_owner_email.lower().strip(),
            role="owner",
            token=raw_token,
            invited_by_user_id=platform_owner.id,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invitation)
        db.commit()
        invitation_token = raw_token

    # Audit log
    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=platform_owner.id,
        action="tenant_created",
        target_type="tenant",
        target_id=tenant.id,
        details=f"Tenant '{tenant.name}' ({tenant.subdomain}) created with tier '{tenant.subscription_tier}'. Owner invite: {target_owner_email or 'none'}",
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()

    # Lifecycle Hook: Auto-provision Chatwoot if configured
    if getattr(settings, "CHATWOOT_AUTO_PROVISION", False):
        try:
            from ...services.sms.chatwoot_provisioning_service import provision_tenant_chatwoot

            provision_result = provision_tenant_chatwoot(db=db, tenant_id=tenant.id)
            if not provision_result.success:
                logger.warning(
                    f"Chatwoot auto-provisioning pending/failed for tenant {tenant.id} ({tenant.subdomain}): {provision_result.error_message}"
                )
            else:
                logger.info(
                    f"Chatwoot successfully auto-provisioned for tenant {tenant.id}: account_id={provision_result.chatwoot_account_id}"
                )
        except Exception as e:
            logger.warning(
                f"Fail-safe: Chatwoot auto-provisioning encountered an exception for tenant {tenant.id}: {e}"
            )

    tenant_out = TenantOut.model_validate(tenant)
    tenant_out.invitation_token = invitation_token
    return TenantResponse(ok=True, data=tenant_out)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    x_token: Optional[str] = Header(None, alias="X-Token"),
    db: Session = Depends(get_db),
):
    """Retrieve tenant details by ID.

    Protected: Requires platform owner or authenticated member of the target tenant.
    """
    if not x_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    payload = decode_access_token(x_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    is_platform = (
        bool(getattr(user, "is_platform_owner", False))
        or bool(getattr(user, "is_superuser", False))
        or (getattr(user, "role", "") or "").lower() == "platform_owner"
    )
    if not is_platform and user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot access other tenant accounts.",
        )

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    return TenantResponse(ok=True, data=tenant)


@router.post("/{tenant_id}/suspend", response_model=TenantResponse)
def suspend_tenant(
    tenant_id: int,
    payload: Optional[TenantSuspendRequest] = None,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Suspend a tenant organization and revoke operational access."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    tenant.status = "suspended"
    tenant.suspended_at = datetime.now(timezone.utc)
    tenant.suspension_reason = payload.reason if payload and payload.reason else "Administrative suspension"
    db.add(tenant)

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=platform_owner.id,
        action="tenant_suspended",
        target_type="tenant",
        target_id=tenant.id,
        details=f"Tenant suspended. Reason: {tenant.suspension_reason}",
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(tenant)

    return TenantResponse(ok=True, data=tenant)


@router.post("/{tenant_id}/reactivate", response_model=TenantResponse)
def reactivate_tenant(
    tenant_id: int,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Reactivate a suspended tenant organization."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    tenant.status = "active"
    tenant.suspended_at = None
    tenant.suspension_reason = None
    db.add(tenant)

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=platform_owner.id,
        action="tenant_reactivated",
        target_type="tenant",
        target_id=tenant.id,
        details="Tenant reactivated by platform owner.",
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(tenant)

    return TenantResponse(ok=True, data=tenant)


@router.post("/{tenant_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_invitation(
    tenant_id: int,
    payload: InvitationCreate,
    x_token: Optional[str] = Header(None, alias="X-Token"),
    db: Session = Depends(get_db),
):
    """Create a new invitation token for a tenant organization.

    Allowed for platform owners or tenant owners of the target tenant.
    """
    if not x_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    token_payload = decode_access_token(x_token)
    if not token_payload or "sub" not in token_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = int(token_payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    is_platform = (
        bool(getattr(user, "is_platform_owner", False))
        or bool(getattr(user, "is_superuser", False))
        or (getattr(user, "role", "") or "").lower() == "platform_owner"
    )
    is_tenant_owner = (user.tenant_id == tenant_id and (user.role or "").lower() in {"owner", "admin"})

    if not (is_platform or is_tenant_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only platform owners or tenant owners can create invitations.",
        )

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    raw_token = secrets.token_urlsafe(32)
    invitation = TenantInvitation(
        tenant_id=tenant.id,
        email=payload.email.lower().strip(),
        role=payload.role,
        token=raw_token,
        invited_by_user_id=user.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=user.id,
        action="invitation_created",
        target_type="invitation",
        target_id=invitation.id,
        details=f"Invitation created for '{invitation.email}' with role '{invitation.role}'.",
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()

    return InvitationResponse(ok=True, data=invitation)
