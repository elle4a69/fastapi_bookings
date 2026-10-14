"""Admin and Operator API routes for voice assistant controls, settings, and health checks."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.operator_controls import (
    ConcurrencyLimitExceeded,
    InvalidTransportError,
    LiveKitHealthResponse,
    OperatorControlError,
    OperatorSettingsRead,
    OperatorSettingsUpdate,
    UnauthorizedModelOrVoiceError,
    get_operator_controls_service,
)
from app.models.user import User

router = APIRouter(prefix="/api/admin/operator", tags=["Operator Controls"])
operator_alias_router = router  # Backwards compatibility alias


@router.get("/health", response_model=LiveKitHealthResponse)
def get_voice_health(
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> LiveKitHealthResponse:
    """Return worker readiness, voice engine connectivity, and quota readiness without leaking secrets."""
    return service.check_health()


@router.get("/settings", response_model=OperatorSettingsRead)
def get_operator_settings(
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> OperatorSettingsRead:
    """Retrieve the current operator controls configuration."""
    return service.get_settings()


@router.patch("/settings", response_model=OperatorSettingsRead)
def update_operator_settings(
    payload: OperatorSettingsUpdate,
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> OperatorSettingsRead:
    """Update operator controls configuration.

    Enforces whitelists for models, voices, and transports. Rejects unapproved substitutions.
    """
    try:
        return service.update_settings(payload)
    except UnauthorizedModelOrVoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "UNAUTHORIZED_MODEL_OR_VOICE", "message": str(exc)},
        ) from exc
    except InvalidTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_TRANSPORT", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SETTINGS_VALUE", "message": str(exc)},
        ) from exc


@router.post("/sessions/{session_id}/release", response_model=Dict[str, bool])
def release_voice_session(
    session_id: str,
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> Dict[str, bool]:
    """Manually or lifecycle-release an active voice session concurrency slot."""
    released = service.release_session(session_id)
    return {"released": released}


@router.post("/sessions/prune", response_model=Dict[str, Any])
def prune_stale_voice_sessions(
    tenant_id: Optional[int] = None,
    force_all: bool = False,
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> Dict[str, Any]:
    """Prune expired and idle voice sessions across tenants or clear sessions for a tenant."""
    reaped = service.prune_sessions(tenant_id=tenant_id, force_all=force_all)
    return {
        "ok": True,
        "reaped": reaped,
        "active_sessions_global": service.active_session_count(),
        "active_sessions_tenant": service.active_session_count(tenant_id) if tenant_id is not None else None,
    }


@router.get("/sessions", response_model=List[Dict[str, Any]])
def list_active_voice_sessions(
    tenant_id: Optional[int] = None,
    current_admin: User = Depends(get_current_admin),
    service=Depends(get_operator_controls_service),
) -> List[Dict[str, Any]]:
    """List active voice sessions and their lifecycle timing metadata."""
    return service.list_active_sessions(tenant_id=tenant_id)
