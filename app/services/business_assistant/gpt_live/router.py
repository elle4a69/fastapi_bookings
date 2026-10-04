"""Authenticated, tenant-scoped HTTP boundary for the isolated GPT-Live app."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....api.deps import DatabaseId, get_current_owner, get_current_tenant, get_db
from ....models.tenant import Tenant
from ....models.user import User
from ..service import BusinessAssistantService
from .runtime import (
    GPTLiveConfigurationError,
    GPTLiveInvalidSdpError,
    GPTLiveProviderUnavailableError,
    GPTLiveRuntime,
)

router = APIRouter(prefix="/gpt-live", tags=["GPT-Live"])


class GPTLiveSessionCreate(BaseModel):
    """Only the browser SDP reaches this boundary; no API credential is accepted."""

    sdp: str = Field(min_length=1, max_length=500_000)


class GPTLiveSessionRead(BaseModel):
    """Opaque provider ID and SDP answer required to finish local WebRTC setup."""

    session_id: str
    sdp: str


def get_gpt_live_runtime() -> GPTLiveRuntime:
    return GPTLiveRuntime.from_settings()


@router.post(
    "/conversations/{conversation_id}/sessions",
    response_model=GPTLiveSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_gpt_live_session(
    conversation_id: DatabaseId,
    payload: GPTLiveSessionCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> GPTLiveSessionRead:
    """Create one server-authorised GPT-Live WebRTC session for an owned conversation."""
    service = BusinessAssistantService(db, tenant.id, user.id)
    service.verify_rollout_access(tenant=tenant, user=user)
    try:
        service.get_conversation(conversation_id=conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc

    try:
        created = get_gpt_live_runtime().create_session(payload.sdp)
    except GPTLiveConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "GPT_LIVE_CONFIGURATION_REQUIRED",
                "message": "Voice setup is incomplete. An administrator must configure the server-side OpenAI project key.",
            },
        ) from exc
    except GPTLiveInvalidSdpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "GPT_LIVE_INVALID_SDP",
                "message": "The browser could not create a valid voice offer. Please try again or continue in text.",
            },
        ) from exc
    except GPTLiveProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "GPT_LIVE_PROVIDER_UNAVAILABLE",
                "message": "The voice provider could not start the session. Please try again later or continue in text.",
            },
        ) from exc

    return GPTLiveSessionRead(session_id=created.session_id, sdp=created.sdp)
