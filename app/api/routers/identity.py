"""Identity Router for Logto integration, token exchange, and organization mapping (WP1).

Exposes endpoints for:
1. POST /api/identity/exchange: Linking/exchanging Logto identity tokens for internal sessions.
2. GET /api/identity/me: Inspecting current identity mapping, external subject, and tenant memberships.
3. GET /api/identity/organizations: Listing linked organizations and tenants for the user.
4. POST /api/identity/webhook: Ingesting identity lifecycle events from Logto.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user, get_current_tenant
from ...core.security import create_access_token
from ...models.user import User
from ...models.tenant import Tenant
from ...models.external_identity import ExternalIdentityLink, ExternalOrganizationLink
from ...schemas.identity import (
    LogtoTokenExchangeRequest,
    IdentityLinkResponse,
    IdentityMeResponse,
    IdentityMeOrganization,
    OrganizationListResponse,
    LogtoWebhookPayload,
)
from ...services.identity import (
    logto_validator,
    LogtoValidationError,
    identity_service,
    IdentityProvisioningError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identity", tags=["identity"])


def _extract_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None, alias="X-Token"),
) -> Optional[str]:
    """Extract raw bearer token or custom header from request."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization
    return x_token


@router.post("/exchange", response_model=IdentityLinkResponse)
@router.post("/logto/link", response_model=IdentityLinkResponse)
async def exchange_logto_token(
    body: LogtoTokenExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None, alias="X-Token"),
):
    """Exchange a Logto OIDC token to establish or claim an internal user session.

    If an invitation token is provided, redeems the invitation and links the external
    identity to the invited tenant and role.
    If the external identity is already linked, returns an internal session token.
    If an internal user is already authenticated, links this external identity.
    Otherwise, rejects uninvited external logins with 403 Forbidden.
    """
    raw_token = body.token or body.id_token or body.access_token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Logto token (provide token, id_token, or access_token).",
        )

    # 1. Validate Logto token
    try:
        claims = logto_validator.validate_token(raw_token, verify_aud=False)
    except LogtoValidationError as exc:
        logger.warning("Logto token validation failed: %s (%s)", exc.code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc.message}",
        )

    external_sub = claims.get("sub")
    email = claims.get("email")
    first_name = claims.get("given_name") or claims.get("name")
    last_name = claims.get("family_name")

    # 2. Case A: Linking via Tenant Invitation
    if body.invitation_token:
        try:
            user, link = identity_service.link_identity_via_invitation(
                db=db,
                invitation_token=body.invitation_token,
                provider="logto",
                external_subject_id=external_sub,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            # Fetch tenant subdomain
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_subdomain = tenant.subdomain if tenant else None

            session_token = create_access_token({
                "sub": str(user.id),
                "role": user.role,
                "tenant_id": user.tenant_id,
                "provider_id": user.provider_id,
            })

            return {
                "ok": True,
                "user_id": user.id,
                "external_subject_id": external_sub,
                "provider": "logto",
                "tenant_id": user.tenant_id,
                "tenant_subdomain": tenant_subdomain,
                "access_token": session_token,
                "token_type": "bearer",
            }
        except IdentityProvisioningError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            )

    # 3. Case B: Existing external identity link
    existing_user = identity_service.get_user_by_external_identity(
        db=db,
        provider="logto",
        external_subject_id=external_sub,
    )
    if existing_user:
        if not existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        tenant = db.query(Tenant).filter(Tenant.id == existing_user.tenant_id).first() if existing_user.tenant_id else None
        session_token = create_access_token({
            "sub": str(existing_user.id),
            "role": existing_user.role,
            "tenant_id": existing_user.tenant_id,
            "provider_id": existing_user.provider_id,
        })
        return {
            "ok": True,
            "user_id": existing_user.id,
            "external_subject_id": external_sub,
            "provider": "logto",
            "tenant_id": existing_user.tenant_id,
            "tenant_subdomain": tenant.subdomain if tenant else None,
            "access_token": session_token,
            "token_type": "bearer",
        }

    # 4. Case C: User is already authenticated via internal token, linking account
    caller_token = _extract_token_from_request(request, authorization, x_token)
    if caller_token:
        from ...core.security import decode_access_token
        payload = decode_access_token(caller_token)
        if payload and "sub" in payload:
            try:
                authed_user_id = int(payload["sub"])
                authed_user = db.query(User).filter(User.id == authed_user_id).first()
                if authed_user and authed_user.is_active:
                    link = identity_service.link_identity(
                        db=db,
                        provider="logto",
                        external_subject_id=external_sub,
                        user_id=authed_user.id,
                        email=email,
                    )
                    tenant = db.query(Tenant).filter(Tenant.id == authed_user.tenant_id).first() if authed_user.tenant_id else None
                    session_token = create_access_token({
                        "sub": str(authed_user.id),
                        "role": authed_user.role,
                        "tenant_id": authed_user.tenant_id,
                        "provider_id": authed_user.provider_id,
                    })
                    return {
                        "ok": True,
                        "user_id": authed_user.id,
                        "external_subject_id": external_sub,
                        "provider": "logto",
                        "tenant_id": authed_user.tenant_id,
                        "tenant_subdomain": tenant.subdomain if tenant else None,
                        "access_token": session_token,
                        "token_type": "bearer",
                    }
            except Exception as exc:
                logger.warning("Failed linking to authenticated caller: %s", exc)

    # 5. Strict rejection: No uninvited auto-provisioning
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Identity not linked. An active tenant invitation or existing user account is required.",
    )


@router.get("/me", response_model=IdentityMeResponse)
async def get_identity_me(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None, alias="X-Token"),
):
    """Retrieve identity mappings and tenant memberships for the current caller."""
    raw_token = _extract_token_from_request(request, authorization, x_token)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token.",
        )

    user: Optional[User] = None
    external_sub: Optional[str] = None
    provider: Optional[str] = None

    # Check if RS256 Logto token
    try:
        claims = logto_validator.validate_token(raw_token, verify_aud=False)
        external_sub = claims.get("sub")
        provider = "logto"
        user = identity_service.get_user_by_external_identity(
            db=db,
            provider="logto",
            external_subject_id=external_sub,
        )
    except LogtoValidationError:
        # Fall back to internal JWT decoding
        from ...core.security import decode_access_token
        payload = decode_access_token(raw_token)
        if payload and "sub" in payload:
            try:
                user_id = int(payload["sub"])
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    link = (
                        db.query(ExternalIdentityLink)
                        .filter(ExternalIdentityLink.user_id == user.id)
                        .first()
                    )
                    if link:
                        external_sub = link.external_subject_id
                        provider = link.provider
            except (ValueError, TypeError):
                pass

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated or account deactivated.",
        )

    # Resolve organizations
    orgs_data = identity_service.get_user_accessible_tenants(db=db, user=user)
    organizations = [IdentityMeOrganization(**org) for org in orgs_data]

    tenant_subdomain = None
    if user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant:
            tenant_subdomain = tenant.subdomain

    return {
        "ok": True,
        "user_id": user.id,
        "login": user.login,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "is_platform_owner": bool(
            getattr(user, "is_platform_owner", False)
            or getattr(user, "is_superuser", False)
            or (user.role or "").lower() == "platform_owner"
        ),
        "tenant_id": user.tenant_id,
        "tenant_subdomain": tenant_subdomain,
        "external_subject_id": external_sub,
        "provider": provider,
        "organizations": organizations,
    }


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_user_organizations(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None, alias="X-Token"),
):
    """List linked tenant organizations accessible to the current user."""
    me_resp = await get_identity_me(request=request, db=db, authorization=authorization, x_token=x_token)
    return {"ok": True, "data": me_resp["organizations"]}


@router.post("/webhook")
async def logto_webhook_receiver(
    payload: LogtoWebhookPayload,
    db: Session = Depends(get_db),
):
    """Receive and record Logto webhook events."""
    logger.info("Received Logto webhook: %s", payload.event)
    return {"ok": True, "received": payload.event}
