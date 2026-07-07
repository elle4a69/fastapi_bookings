"""Authentication routes.

This router exposes endpoints for obtaining access tokens for both
administrative and public access. Administrative tokens include the
user's ID and role, while public tokens encode only the tenant subdomain.
"""

from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_admin, get_current_tenant
from ...core.config import settings
from ...core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from ...models.user import User
from ...models.tenant import Tenant
from ...schemas.user import UserCreate, UserResponse


router = APIRouter()


class AdminAuthRequest(BaseModel):
    company: str  # Kept for backward compatibility but validated against active tenant
    login: str
    password: str


class PublicAuthRequest(BaseModel):
    company: str  # Kept for backward compatibility but validated against active tenant
    key: str


class TokenResponse(BaseModel):
    ok: bool
    data: Dict[str, Any]


@router.post("/admin/auth", response_model=TokenResponse, tags=["auth"])
def admin_login(
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
    
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"ok": True, "data": {"access_token": token, "token_type": "bearer"}}


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

    # Ensure login is unique within the tenant
    existing = db.query(User).filter(User.tenant_id == tenant.id, User.login == user_in.login).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login already exists")
    
    user = User(
        tenant_id=tenant.id,
        login=user_in.login,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "data": user}