"""Authentication routes.

This router exposes endpoints for obtaining access tokens for both
administrative and public access. Administrative tokens include the
user's ID and role, while public tokens encode only the tenant subdomain.
"""

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_admin, get_current_tenant, get_current_user
from ...core.config import settings
from ...core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from ...models.user import User
from ...models.tenant import Tenant
from ...models.invitation import TenantInvitation
from ...models.provider import Provider
from ...schemas.user import UserCreate, UserResponse
from ...schemas.invitation import InvitationAccept


router = APIRouter()


class AdminAuthRequest(BaseModel):
    company: str  # Kept for backward compatibility but validated against active tenant
    login: str
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    company: Optional[str] = None


class PublicAuthRequest(BaseModel):
    company: str  # Kept for backward compatibility but validated against active tenant
    key: str


class TokenResponse(BaseModel):
    ok: bool
    data: Dict[str, Any]


@router.post("/admin/auth", response_model=TokenResponse, tags=["auth"])
async def admin_login(
    body: AdminAuthRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Authenticate an admin or staff user and return a signed token."""
    # Ensure the requested company matches the resolved subdomain tenant
    if body.company.lower() != tenant.subdomain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested company '{body.company}' does not match the active tenant subdomain '{tenant.subdomain}'."
        )

    user = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.login == body.login)
        .first()
    )
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "provider_id": user.provider_id,
        "tenant_id": user.tenant_id,
    })

    chatwoot_sso_url = None
    if tenant.chatwoot_account_id:
        try:
            from ...services.auth.chatwoot_sso import sync_user_to_chatwoot_platform, generate_chatwoot_sso_url
            chatwoot_uid = await sync_user_to_chatwoot_platform(user, tenant.chatwoot_account_id)
            if chatwoot_uid:
                if user.chatwoot_user_id != chatwoot_uid:
                    user.chatwoot_user_id = chatwoot_uid
                    db.commit()
                chatwoot_sso_url = await generate_chatwoot_sso_url(chatwoot_uid)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Chatwoot SSO link generation skipped: %s", exc)

    return {
        "ok": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "chatwoot_sso_url": chatwoot_sso_url,
        }
    }


def _is_expired(dt: datetime | None) -> bool:
    if dt is None:
        return False
    if dt.tzinfo is not None:
        return dt < datetime.now(timezone.utc)
    return dt < datetime.utcnow()


@router.post("/admin/auth/google", response_model=TokenResponse, tags=["auth"])
async def google_login(
    body: GoogleAuthRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Authenticate an admin or staff user via Google OAuth2/OIDC ID token."""
    if body.company and body.company.lower() != tenant.subdomain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested company '{body.company}' does not match the active tenant subdomain '{tenant.subdomain}'."
        )

    from ...services.auth.google_oidc import verify_google_id_token
    from ...services.auth.chatwoot_sso import sync_user_to_chatwoot_platform, generate_chatwoot_sso_url

    try:
        claims = verify_google_id_token(body.id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}"
        )

    google_sub = claims.get("sub")
    email = claims.get("email")
    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token missing sub or email"
        )

    user = (
        db.query(User)
        .filter(
            User.tenant_id == tenant.id,
            (User.google_sub == google_sub) | (User.email == email) | (User.login == email)
        )
        .first()
    )

    if not user:
        invitation = (
            db.query(TenantInvitation)
            .filter(
                TenantInvitation.tenant_id == tenant.id,
                TenantInvitation.email == email.lower(),
                TenantInvitation.status == "pending",
            )
            .first()
        )
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: No account or pending invitation found for '{email}' in tenant '{tenant.subdomain}'."
            )
        now_utc = datetime.now(timezone.utc)
        if _is_expired(invitation.expires_at):
            invitation.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invitation has expired. Please request a new invitation."
            )

        role = invitation.role
        name_parts = (claims.get("name") or "").split(" ", 1)
        first_name = claims.get("given_name") or (name_parts[0] if name_parts else "")
        last_name = claims.get("family_name") or (name_parts[1] if len(name_parts) > 1 else "")
        user = User(
            tenant_id=tenant.id,
            login=email,
            email=email,
            google_sub=google_sub,
            password_hash="[SSO_MANAGED]",
            role=role,
            first_name=first_name,
            last_name=last_name,
            avatar_url=claims.get("picture"),
            is_active=True,
        )
        db.add(user)
        invitation.status = "accepted"
        invitation.accepted_at = now_utc
        db.commit()
        db.refresh(user)
    else:
        dirty = False
        if not user.google_sub:
            user.google_sub = google_sub
            dirty = True
        if not user.email:
            user.email = email
            dirty = True
        if claims.get("picture") and user.avatar_url != claims.get("picture"):
            user.avatar_url = claims.get("picture")
            dirty = True
        if dirty:
            db.commit()
            db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "provider_id": user.provider_id,
        "tenant_id": user.tenant_id,
    })

    chatwoot_sso_url = None
    if tenant.chatwoot_account_id:
        try:
            chatwoot_uid = await sync_user_to_chatwoot_platform(user, tenant.chatwoot_account_id)
            if chatwoot_uid:
                if user.chatwoot_user_id != chatwoot_uid:
                    user.chatwoot_user_id = chatwoot_uid
                    db.commit()
                chatwoot_sso_url = await generate_chatwoot_sso_url(chatwoot_uid)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Chatwoot SSO link generation skipped: %s", exc)

    return {
        "ok": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "chatwoot_sso_url": chatwoot_sso_url,
            "user": {
                "id": user.id,
                "login": user.login,
                "email": user.email,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
            }
        }
    }


@router.post("/public/auth/token", response_model=TokenResponse, tags=["auth"])
def public_login(
    body: PublicAuthRequest,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Obtain a token for the public booking widget.

    The provided key must match the ``PUBLIC_API_KEY`` configured in
    the application settings. The returned token encodes the tenant
    subdomain name as its subject.
    """
    if body.company.lower() != tenant.subdomain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested company '{body.company}' does not match the active tenant subdomain '{tenant.subdomain}'."
        )

    if body.key != settings.PUBLIC_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    token = create_access_token({"sub": tenant.subdomain})
    return {"ok": True, "data": {"access_token": token, "token_type": "bearer"}}


@router.get("/public/auth/config", tags=["auth"])
def get_public_auth_config():
    """Return public authentication configuration for frontend clients."""
    from ...core.config import Settings
    current_settings = Settings()
    return {
        "ok": True,
        "data": {
            "google_client_id": current_settings.GOOGLE_CLIENT_ID or "",
            "google_sso_enabled": True,
            "chatwoot_enabled": bool(current_settings.CHATWOOT_BASE_URL),
        },
    }


@router.get("/admin/auth/me", tags=["auth"])
@router.get("/admin/me", tags=["auth"])
def get_auth_me(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Retrieve details of current authenticated user session."""
    return {
        "ok": True,
        "data": {
            "id": current_user.id,
            "login": current_user.login,
            "email": current_user.email,
            "role": current_user.role,
            "provider_id": current_user.provider_id,
            "tenant_id": current_user.tenant_id,
            "company": tenant.subdomain,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "avatar_url": current_user.avatar_url,
            "chatwoot_user_id": current_user.chatwoot_user_id,
        },
    }


@router.get("/admin/auth/chatwoot-sso", tags=["auth"])
async def get_chatwoot_sso_link(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Generate a single-use SSO link for the current authenticated user into Chatwoot."""
    if not tenant.chatwoot_account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chatwoot is not connected for this tenant."
        )
    from ...services.auth.chatwoot_sso import sync_user_to_chatwoot_platform, generate_chatwoot_sso_url
    chatwoot_uid = await sync_user_to_chatwoot_platform(current_user, tenant.chatwoot_account_id)
    if not chatwoot_uid:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to synchronize user to Chatwoot platform."
        )
    if current_user.chatwoot_user_id != chatwoot_uid:
        current_user.chatwoot_user_id = chatwoot_uid
        db.commit()
    url = await generate_chatwoot_sso_url(chatwoot_uid)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate Chatwoot SSO link."
        )
    return {"ok": True, "data": {"chatwoot_sso_url": url}}


@router.post("/admin/users", response_model=UserResponse, tags=["auth"])
def create_user(
    user_in: UserCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new user. Only administrators can create other users."""
    if user_in.company.lower() != tenant.subdomain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User company must match active tenant subdomain."
        )

    # Enforce permissions: only owners can create owner/admin accounts
    if user_in.role in {"owner", "admin"} and current_user.role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners have permission to create owner accounts.",
        )

    # If role is provider, validate provider_id if supplied
    if user_in.provider_id is not None:
        prov = db.query(Provider).filter(Provider.id == user_in.provider_id, Provider.tenant_id == tenant.id).first()
        if not prov:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider {user_in.provider_id} not found in this tenant.")

    # Ensure login is unique within the tenant
    existing = db.query(User).filter(User.tenant_id == tenant.id, User.login == user_in.login).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login already exists")
    
    user = User(
        tenant_id=tenant.id,
        login=user_in.login,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        provider_id=user_in.provider_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "ok": True,
        "data": {
            "id": user.id,
            "company": tenant.subdomain,
            "login": user.login,
            "role": user.role,
            "provider_id": user.provider_id,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        },
    }


@router.post("/auth/invitations/accept", response_model=TokenResponse, tags=["auth"])
@router.post("/invitations/accept", response_model=TokenResponse, tags=["auth"])
def accept_invitation(
    body: InvitationAccept,
    db: Session = Depends(get_db),
):
    """Redeem a tenant invitation token to activate or provision an account."""
    invitation = (
        db.query(TenantInvitation)
        .filter(TenantInvitation.token == body.token.strip())
        .first()
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation token not found."
        )

    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation has already been {invitation.status}."
        )

    if _is_expired(invitation.expires_at):
        invitation.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired."
        )

    tenant = db.query(Tenant).filter(Tenant.id == invitation.tenant_id).first()
    if not tenant or getattr(tenant, "status", "active") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant organization is inactive or suspended."
        )

    # Check if a user with this email/login already exists for this tenant
    user = (
        db.query(User)
        .filter(
            User.tenant_id == tenant.id,
            (User.email == invitation.email) | (User.login == invitation.email)
        )
        .first()
    )

    if not user:
        pwd_hash = get_password_hash(body.password) if body.password else "[INVITATION_CLAIMED]"
        user = User(
            tenant_id=tenant.id,
            login=invitation.email,
            email=invitation.email,
            password_hash=pwd_hash,
            role=invitation.role,
            first_name=body.first_name,
            last_name=body.last_name,
            is_active=True,
        )
        db.add(user)
    else:
        user.role = invitation.role
        user.is_active = True
        if body.password:
            user.password_hash = get_password_hash(body.password)
        if body.first_name:
            user.first_name = body.first_name
        if body.last_name:
            user.last_name = body.last_name

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "provider_id": user.provider_id,
        "tenant_id": user.tenant_id,
    })

    return {
        "ok": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "login": user.login,
                "email": user.email,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "tenant_id": user.tenant_id,
                "tenant_subdomain": tenant.subdomain,
            }
        }
    }


@router.get("/auth/invitations/{token}", tags=["auth"])
@router.get("/invitations/{token}", tags=["auth"])
def get_invitation_details(
    token: str,
    db: Session = Depends(get_db),
):
    """Retrieve public metadata for an invitation token."""
    invitation = (
        db.query(TenantInvitation)
        .filter(TenantInvitation.token == token.strip())
        .first()
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation token not found."
        )

    is_expired = _is_expired(invitation.expires_at)
    tenant = db.query(Tenant).filter(Tenant.id == invitation.tenant_id).first()
    tenant_name = tenant.name if tenant else "Workspace"
    tenant_subdomain = tenant.subdomain if tenant else ""
    is_active = tenant and getattr(tenant, "status", "active") == "active"

    return {
        "ok": True,
        "data": {
            "token": invitation.token,
            "email": invitation.email,
            "role": invitation.role,
            "status": "expired" if is_expired else invitation.status,
            "is_valid": invitation.status == "pending" and not is_expired and is_active,
            "tenant_id": invitation.tenant_id,
            "tenant_name": tenant_name,
            "tenant_subdomain": tenant_subdomain,
            "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        }
    }


@router.get("/public/check-subdomain", tags=["public"])
def check_subdomain_availability(
    subdomain: str = Query(..., min_length=2, max_length=50),
    db: Session = Depends(get_db),
):
    """Check if a tenant subdomain slug is available."""
    normalized = subdomain.lower().strip()
    reserved = {"admin", "api", "app", "dashboard", "billing", "portal", "system", "auth", "static", "docs"}
    if normalized in reserved:
        return {"ok": True, "data": {"subdomain": normalized, "available": False, "reason": "reserved"}}

    exists = db.query(Tenant).filter(Tenant.subdomain == normalized).first()
    return {
        "ok": True,
        "data": {
            "subdomain": normalized,
            "available": exists is None,
            "reason": "already_taken" if exists else "available"
        }
    }


class PublicSignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Business or workspace name")
    subdomain: str = Field(..., min_length=2, max_length=50, description="Unique subdomain slug")
    email: str = Field(..., description="Owner email address")
    password: str = Field(..., min_length=6, description="Password for owner account")
    first_name: Optional[str] = "Owner"
    last_name: Optional[str] = ""
    subscription_tier: Optional[str] = "starter"
    billing_cycle: Optional[str] = "monthly"
    phone: Optional[str] = None


@router.post("/public/signup", response_model=TokenResponse, tags=["public"])
def public_signup(
    body: PublicSignupRequest,
    db: Session = Depends(get_db),
):
    """Self-service registration for a new tenant and founding owner account."""
    subdomain_slug = body.subdomain.lower().strip()

    # 1. Enforce reserved and uniqueness checks
    reserved = {"admin", "api", "app", "dashboard", "billing", "portal", "system", "auth", "static", "docs"}
    if subdomain_slug in reserved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subdomain '{subdomain_slug}' is a reserved system keyword."
        )

    existing_tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain_slug).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subdomain '{subdomain_slug}' is already taken. Please choose another."
        )

    # 2. Determine tier and addon quota
    tier = body.subscription_tier.lower() if body.subscription_tier in {"starter", "growth", "unlimited"} else "starter"
    quota_map = {"starter": 0, "growth": 3, "unlimited": 999}
    addon_quota = quota_map.get(tier, 0)

    # Enabled modules based on tier
    enabled_modules = ["dashboard", "calendar", "bookings", "website"]
    if tier in {"growth", "unlimited"}:
        enabled_modules.extend(["sms_assistant", "locations", "providers", "multiple_providers", "categories"])
    if tier == "unlimited":
        enabled_modules.extend(["products", "addons", "packages", "relationship_matrix", "finance_invoicing", "media", "booking_forms", "reviews", "calcom_scheduling"])

    tenant = Tenant(
        name=body.name.strip(),
        subdomain=subdomain_slug,
        status="active",
        subscription_tier=tier,
        addon_quota=addon_quota,
        enabled_modules=enabled_modules,
        email=body.email.lower().strip(),
        phone=body.phone,
    )
    db.add(tenant)
    db.flush()

    # 3. Create founding owner user
    owner_user = User(
        tenant_id=tenant.id,
        login=body.email.lower().strip(),
        email=body.email.lower().strip(),
        password_hash=get_password_hash(body.password),
        role="owner",
        first_name=body.first_name or "Owner",
        last_name=body.last_name or "",
        is_active=True,
    )
    db.add(owner_user)
    db.flush()

    # 4. Initialize BillingAccount for tenant
    try:
        from ...models.platform_billing import BillingAccount, SubscriptionProjection
        billing_account = BillingAccount(
            tenant_id=tenant.id,
            flexprice_customer_id=f"cust_{tenant.subdomain}_{secrets.token_hex(4)}",
            billing_state="active",
        )
        db.add(billing_account)
        db.flush()

        # Create trial projection
        now_utc = datetime.now(timezone.utc)
        trial_sub = SubscriptionProjection(
            tenant_id=tenant.id,
            external_subscription_id=f"sub_{tenant.subdomain}_{secrets.token_hex(4)}",
            plan_id=tier,
            plan_version=1,
            status="trialing",
            trial_end=now_utc + timedelta(days=14),
            current_period_start=now_utc,
            current_period_end=now_utc + timedelta(days=14),
            last_event_timestamp=now_utc,
            last_event_sequence=0,
        )
        db.add(trial_sub)
    except Exception as exc:
        logging.getLogger(__name__).warning("Billing account init skipped or deferred: %s", exc)

    # 5. Audit Log
    try:
        from ...models.audit import AuditLog
        audit = AuditLog(
            tenant_id=tenant.id,
            user_id=owner_user.id,
            action="tenant_self_signup",
            target_type="tenant",
            target_id=tenant.id,
            details=f"Self-service tenant created for '{tenant.name}' ({tenant.subdomain}) on tier '{tier}' with owner '{owner_user.email}'.",
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
    except Exception as exc:
        logging.getLogger(__name__).warning("Audit log write skipped: %s", exc)

    db.commit()
    db.refresh(tenant)
    db.refresh(owner_user)

    # 6. Issue access token
    token = create_access_token({
        "sub": str(owner_user.id),
        "role": owner_user.role,
        "provider_id": owner_user.provider_id,
        "tenant_id": owner_user.tenant_id,
    })

    return {
        "ok": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "subdomain": tenant.subdomain,
                "subscription_tier": tenant.subscription_tier,
            },
            "user": {
                "id": owner_user.id,
                "login": owner_user.login,
                "email": owner_user.email,
                "role": owner_user.role,
                "first_name": owner_user.first_name,
                "last_name": owner_user.last_name,
                "tenant_id": owner_user.tenant_id,
                "tenant_subdomain": tenant.subdomain,
            }
        }
    }