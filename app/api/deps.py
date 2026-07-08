"""Dependency injection functions for FastAPI routes."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..core.security import decode_access_token
from ..db.database import get_db
from ..models.user import User
from ..models.tenant import Tenant
from ..models.client import Client


async def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """Resolve the active tenant from the request host subdomain.

    Extracts subdomain from the HTTP Host header. If no subdomain exists,
    falls back to the X-Tenant header or 'tenant' query parameter.
    """
    host = request.headers.get("host", "")
    parts = host.split(":")
    hostname = parts[0]

    subdomain = None
    host_parts = hostname.split(".")
    # If e.g., company.localhost or company.api.com
    if len(host_parts) > 1:
        first_part = host_parts[0]
        # Ignore common non-tenant prefixes
        if first_part.lower() not in ("www", "api", "localhost", "127"):
            subdomain = first_part

    # Fallback to custom headers or query params (useful for direct API calls/tests)
    if not subdomain:
        subdomain = request.headers.get("X-Tenant")
    if not subdomain:
        subdomain = request.query_params.get("tenant")

    if not subdomain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant subdomain is missing or invalid. Please access via [subdomain].localhost or provide X-Tenant header.",
        )

    tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain.lower()).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{subdomain}' not found.",
        )
    return tenant


async def get_current_user(
    x_token: str = Header(..., alias="X-Token"),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> User:
    """Retrieve the current authenticated user from the X-Token header.

    The token must be a valid JWT containing a ``sub`` claim that
    corresponds to a user ID. Scopes the lookup to the active tenant to
    ensure proper multi-tenant boundary isolation.
    """
    payload = decode_access_token(x_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    # Query user within active tenant scope
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found in this tenant")
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has an administrative role."""
    if current_user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    return current_user


async def get_current_company(
    tenant: Tenant = Depends(get_current_tenant),
) -> str:
    """Retrieve the active tenant subdomain slug."""
    return tenant.subdomain


async def get_public_tenant(
    x_token: str = Header(..., alias="X-Token"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """Validate public access token for public booking endpoints.

    Requires X-Token header. Decodes and verifies it belongs to the active tenant
    (either as a public token, client token, or admin token).
    """
    payload = decode_access_token(x_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token."
        )
    
    sub = payload["sub"]
    # 1. If it's a public token, sub is the tenant subdomain
    if isinstance(sub, str) and sub.lower() == tenant.subdomain.lower():
        return tenant
        
    # 2. If it's a user/admin token, sub is user_id
    try:
        user_id = int(sub)
        user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant.id).first()
        if user:
            return tenant
    except (TypeError, ValueError):
        pass

    # 3. If it's a client token, sub is client_id
    try:
        client_id = int(sub)
        client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant.id).first()
        if client:
            return tenant
    except (TypeError, ValueError):
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Access token is not authorized for this tenant."
    )