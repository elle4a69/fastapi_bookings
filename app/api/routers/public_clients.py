"""Public client portal endpoints.

Register, login, profile lookup/update, terms text and password
reset placeholders.  Prepares the front-end contract without adding
external identity providers.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_tenant
from ...models.tenant import Tenant
from ...core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from ...models.client import Client as ClientModel
from ...schemas.client import (
    ClientAuthResponse,
    ClientCreate,
    ClientResponse,
    ClientIdentifyResponse,
    ClientIdentifyData,
    PublicClientLogin,
    PublicClientProfileUpdate,
    PublicClientRegister,
)


router = APIRouter(prefix="/api/public/clients", tags=["public-clients"])


def get_public_client_from_token(
    x_client_token: str | None = Header(default=None, alias="X-Client-Token"),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ClientModel:
    """Resolve a public client from an X-Client-Token header."""
    if not x_client_token:
        raise HTTPException(status_code=401, detail="Missing X-Client-Token")
    payload = decode_access_token(x_client_token)
    if not payload or not str(payload.get("sub", "")).startswith("client:"):
        raise HTTPException(status_code=401, detail="Invalid client token")
    try:
        client_id = int(str(payload["sub"]).split(":", 1)[1])
    except (ValueError, KeyError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid client token")
    client = db.query(ClientModel).filter(
        ClientModel.id == client_id,
        ClientModel.tenant_id == tenant.id,
        ClientModel.active.is_(True),
        ClientModel.deleted_at.is_(None)
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=ClientResponse)
def create_public_client_contact(
    client_in: ClientCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Backward-compatible public contact creation endpoint."""
    client = ClientModel(
        tenant_id=tenant.id,
        **client_in.dict()
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"ok": True, "data": client}


@router.post("/identify", response_model=ClientIdentifyResponse)
def identify_or_create_client(
    phone: str | None = None,
    email: str | None = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Find an existing client by phone or email, or create a minimal record.

    Used by the AI agent to resolve client identity from a messaging channel.
    Returns the client plus a `created` flag indicating whether a new record
    was created.
    """
    if not phone and not email:
        raise HTTPException(status_code=400, detail="Supply phone or email")
    client = None
    if phone:
        client = db.query(ClientModel).filter(
            ClientModel.phone == phone,
            ClientModel.tenant_id == tenant.id,
            ClientModel.deleted_at.is_(None)
        ).first()
    if not client and email:
        client = db.query(ClientModel).filter(
            ClientModel.email == email,
            ClientModel.tenant_id == tenant.id,
            ClientModel.deleted_at.is_(None)
        ).first()
    created = False
    if not client:
        client = ClientModel(tenant_id=tenant.id, phone=phone, email=email, active=True)
        db.add(client)
        db.commit()
        db.refresh(client)
        created = True
    client_data = ClientIdentifyData.model_validate(client)
    client_data.created = created
    return {"ok": True, "data": client_data}


@router.post("/register", response_model=ClientAuthResponse)
def register_client(
    client_in: PublicClientRegister,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Register a new client account."""
    existing = db.query(ClientModel).filter(
        ClientModel.email == client_in.email,
        ClientModel.tenant_id == tenant.id,
        ClientModel.deleted_at.is_(None)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Client email already exists")
    client = ClientModel(
        tenant_id=tenant.id,
        name=client_in.name,
        email=client_in.email,
        phone=client_in.phone,
        password_hash=get_password_hash(client_in.password) if client_in.password else None,
        address_line1=client_in.address_line1,
        address_line2=client_in.address_line2,
        city=client_in.city,
        state=client_in.state,
        postcode=client_in.postcode,
        country=client_in.country,
        timezone=client_in.timezone,
        accepts_marketing=client_in.accepts_marketing,
        terms_accepted_at=datetime.utcnow() if client_in.accept_terms else None,
        privacy_accepted_at=datetime.utcnow() if client_in.accept_privacy else None,
        active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    token = create_access_token({"sub": f"client:{client.id}", "scope": "client"})
    client_pydantic = ClientResponse.model_validate({"ok": True, "data": client}).data
    return {"ok": True, "data": {"client": client_pydantic, "client_id": client.id, "access_token": token, "token_type": "bearer"}}


@router.post("/login", response_model=ClientAuthResponse)
def login_client(
    login: PublicClientLogin,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Login a client using email and password."""
    client = db.query(ClientModel).filter(
        ClientModel.email == login.email,
        ClientModel.tenant_id == tenant.id,
        ClientModel.active.is_(True),
        ClientModel.deleted_at.is_(None)
    ).first()
    if not client or not client.password_hash:
        raise HTTPException(status_code=401, detail="Invalid client login")
    if not login.password or not verify_password(login.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid client login")
    token = create_access_token({"sub": f"client:{client.id}", "scope": "client"})
    client_pydantic = ClientResponse.model_validate({"ok": True, "data": client}).data
    return {"ok": True, "data": {"client": client_pydantic, "client_id": client.id, "access_token": token, "token_type": "bearer"}}


@router.get("/me", response_model=ClientResponse)
def get_my_profile(client: ClientModel = Depends(get_public_client_from_token)) -> dict:
    """Return the current public client profile."""
    return {"ok": True, "data": client}


@router.put("/me", response_model=ClientResponse)
def update_my_profile(
    profile_in: PublicClientProfileUpdate,
    db: Session = Depends(get_db),
    client: ClientModel = Depends(get_public_client_from_token),
) -> dict:
    """Update the current public client profile."""
    for field, value in profile_in.dict(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return {"ok": True, "data": client}


@router.post("/password-reset/request")
def request_password_reset(
    login: PublicClientLogin,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> dict:
    """Password reset request placeholder.  Actual dispatch wired to notification system later."""
    client = db.query(ClientModel).filter(
        ClientModel.email == login.email,
        ClientModel.tenant_id == tenant.id,
        ClientModel.deleted_at.is_(None)
    ).first()
    return {"ok": True, "data": {"message": "If the account exists, a reset link will be sent."}}


@router.get("/terms")
def get_client_terms() -> dict:
    """Return legal text placeholders for client registration."""
    return {
        "ok": True,
        "data": {
            "terms": "Terms of service placeholder.",
            "privacy": "Privacy policy placeholder.",
            "cancellation": "Cancellation policy placeholder.",
        },
    }
