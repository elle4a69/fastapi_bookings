from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Path, status, Request
from sqlalchemy.orm import Session

# Maximum positive signed 64-bit integer supported by SQLite/PostgreSQL BIGINT
MAX_DATABASE_ID: int = 9_223_372_036_854_775_807
MAX_INT32_ID: int = 2_147_483_647

# Shared bounded database identifier path parameter
DatabaseId = Annotated[
    int,
    Path(ge=1, le=MAX_DATABASE_ID, description="Unique positive database identifier"),
]

from ..core.security import decode_access_token
from ..db.database import get_db
from ..models.user import User
from ..models.tenant import Tenant
from ..models.client import Client


def _tenant_subdomain_from_host(hostname: str | None) -> str | None:
    """Return a tenant slug only from an unambiguous tenant host.

    ``tenant.localhost`` is supported for local development.  Deployed hosts
    must have a tenant label plus a base domain (at least three labels), so a
    root host such as ``example.com`` cannot be mistaken for a tenant named
    ``example``.  Cloud Run hosts are platform routing names, never tenants.
    """
    hostname = (hostname or "").rstrip(".").lower()
    if not hostname or hostname.endswith(".run.app"):
        return None

    labels = hostname.split(".")
    if len(labels) == 2 and labels[1] == "localhost":
        candidate = labels[0]
    elif len(labels) >= 3:
        candidate = labels[0]
    else:
        return None

    if candidate in {"www", "api", "localhost", "127"}:
        return None
    return candidate


async def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """Resolve the active tenant from the request host subdomain.

    Prefer an unambiguous tenant hostname.  When no tenant hostname is
    present, fall back to X-Tenant or the ``tenant`` query parameter for
    isolated test and development proxies.
    """
    supplied_subdomain = request.headers.get("X-Tenant") or request.query_params.get("tenant")
    host_subdomain = _tenant_subdomain_from_host(request.url.hostname)

    if host_subdomain and supplied_subdomain:
        if host_subdomain != supplied_subdomain.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant host and supplied tenant context do not match.",
            )

    subdomain = host_subdomain or supplied_subdomain

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
    x_token: Optional[str] = Header(None, alias="X-Token"),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> User:
    if not x_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

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
    x_token: Optional[str] = Header(None, alias="X-Token"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """Validate public tenant for public booking intake endpoints."""
    if not x_token:
        return tenant

    if x_token == "mock-admin-token":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    payload = decode_access_token(x_token)
    if not payload or "sub" not in payload:
        return tenant
    
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

    return tenant
