"""Plugin state and GDPR consent routes.

Plugin states allow admins to toggle feature flags at runtime without
redeploying.  GDPR consent logs record each client consent decision
with an IP address for compliance auditing.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.general_systems import GdprConsent, PluginState
from ...models.client import Client
from ...schemas.general_systems import (
    GdprConsentCreate,
    GdprConsentListResponse,
    GdprConsentOut,
    GdprConsentResponse,
    PluginStateCreate,
    PluginStateListResponse,
    PluginStateOut,
    PluginStateResponse,
    PluginStateUpdate,
)

router = APIRouter(tags=["system"])
public_router = APIRouter(tags=["public-gdpr"])


# ─── Plugin States ────────────────────────────────────────────────────────────

@router.get("/api/admin/plugin-states", response_model=PluginStateListResponse)
def list_plugin_states(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> dict:
    """Return all plugin state toggles."""
    states = db.query(PluginState).order_by(PluginState.name.asc()).all()
    return {"ok": True, "data": states}


@router.post("/api/admin/plugin-states", response_model=PluginStateResponse, status_code=status.HTTP_201_CREATED)
def upsert_plugin_state(
    state_in: PluginStateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Create or update a plugin state toggle."""
    existing = db.query(PluginState).filter(PluginState.name == state_in.name).first()
    if existing:
        existing.is_enabled = state_in.is_enabled
        db.commit()
        db.refresh(existing)
        return {"ok": True, "data": existing}
    state = PluginState(**state_in.dict())
    db.add(state)
    db.commit()
    db.refresh(state)
    return {"ok": True, "data": state}


@router.put("/api/admin/plugin-states/{name}", response_model=PluginStateResponse)
def toggle_plugin_state(
    name: str,
    update: PluginStateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Toggle a plugin on or off by name."""
    state = db.query(PluginState).filter(PluginState.name == name).first()
    if not state:
        raise HTTPException(status_code=404, detail="Plugin state not found")
    state.is_enabled = update.is_enabled
    db.commit()
    db.refresh(state)
    return {"ok": True, "data": state}


# ─── GDPR Consent ─────────────────────────────────────────────────────────────

@public_router.post("/api/public/gdpr-consent", response_model=GdprConsentResponse, status_code=status.HTTP_201_CREATED)
def record_gdpr_consent(
    consent_in: GdprConsentCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Record a client's GDPR or privacy consent decision.

    The IP address is taken from the incoming request if not supplied.
    """
    client = db.query(Client).filter(Client.id == consent_in.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    ip = consent_in.ip_address or (request.client.host if request.client else "unknown")
    consent = GdprConsent(
        client_id=consent_in.client_id,
        consent_type=consent_in.consent_type,
        is_approved=consent_in.is_approved,
        ip_address=ip,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return {"ok": True, "data": consent}


@router.get("/api/admin/gdpr-consents", response_model=GdprConsentListResponse)
def list_gdpr_consents(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> dict:
    """Return all GDPR consent log entries (admin only)."""
    consents = db.query(GdprConsent).order_by(GdprConsent.created_at.desc()).all()
    return {"ok": True, "data": consents}


@router.get("/api/admin/gdpr-consents/{client_id}", response_model=GdprConsentListResponse)
def list_gdpr_consents_for_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Return all GDPR consent entries for a specific client."""
    consents = (
        db.query(GdprConsent)
        .filter(GdprConsent.client_id == client_id)
        .order_by(GdprConsent.created_at.desc())
        .all()
    )
    return {"ok": True, "data": consents}
