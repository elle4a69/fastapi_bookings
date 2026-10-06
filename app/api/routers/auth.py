"""Authentication routes.

This router exposes endpoints for obtaining access tokens for both
administrative and public access. Administrative tokens include the
user's ID and role, while public tokens encode only the tenant subdomain.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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
from ...models.provider import Provider
from ...schemas.user import UserCreate, UserResponse


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
        user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        role = "owner" if user_count == 0 else "admin"
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
    return {
        "ok": True,
        "data": {
            "google_client_id": settings.GOOGLE_CLIENT_ID or "",
            "google_sso_enabled": True,
            "chatwoot_enabled": bool(settings.CHATWOOT_BASE_URL),
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