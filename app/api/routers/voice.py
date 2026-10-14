"""Authenticated, tenant-scoped HTTP and WebSocket boundary for Direct Realtime Voice Engines.

Supports direct real-time engines:
1. OpenAI GPT-Live WebRTC ('direct_gpt_live')
2. xAI Grok Voice Realtime WebSocket ('xai_grok_voice')

LiveKit is permanently decommissioned.
"""

import asyncio
from typing import List, Literal, Optional
import uuid

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.api.deps import DatabaseId, get_current_owner, get_current_staff, get_current_tenant, get_db
from app.core.config import settings
from app.core.operator_controls import (
    ConcurrencyLimitExceeded,
    InvalidTransportError,
    OperatorSettingsUpdate,
    get_operator_controls_service,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.gpt_live.router import (
    GPTLiveConfigurationError,
    GPTLiveInvalidSdpError,
    GPTLiveProviderUnavailableError,
    get_gpt_live_runtime,
)
from app.services.business_assistant.gpt_live.runtime import (
    build_gpt_live_session_config,
)
from app.services.business_assistant.service import BusinessAssistantService

router = APIRouter(prefix="/business-assistant/voice", tags=["Business Assistant Voice"])

DirectTransportType = Literal["xai_grok_voice", "direct_gpt_live"]
AVAILABLE_DIRECT_TRANSPORTS: list[str] = ["xai_grok_voice", "direct_gpt_live"]


class VoiceTransportRead(BaseModel):
    """Authoritative server transport configuration for direct engines."""

    transport: str
    available_transports: List[str]
    agent_name: str
    active_target: Optional[str] = None


class VoiceTransportUpdate(BaseModel):
    """Payload to mutate authoritative voice transport mode."""

    transport: Optional[str] = Field(
        None,
        description="Transport toggle: 'direct_gpt_live' or 'xai_grok_voice'",
    )


class VoiceSessionCreateRequest(BaseModel):
    """Voice session initiation request with transport selector and optional SDP offer."""

    transport: Optional[str] = Field(
        None,
        description="Transport selector ('direct_gpt_live' or 'xai_grok_voice'). If omitted, uses server authoritative setting.",
    )
    sdp: Optional[str] = Field(
        None,
        description="Browser WebRTC SDP offer, required only for 'direct_gpt_live' transport when establishing SDP.",
        max_length=500_000,
    )
    force_restart: Optional[bool] = Field(
        False,
        description="If True, immediately terminates any prior active voice session for this conversation.",
    )


class VoiceSessionResponse(BaseModel):
    """Voice session response supporting direct WebRTC and xAI Grok Voice."""

    transport: str
    session_id: str
    token: Optional[str] = None
    agent_name: Optional[str] = None
    expires_in: Optional[int] = None
    sdp: Optional[str] = None
    endpoint: Optional[str] = None
    livekit_url: Optional[str] = None


class XAIRealtimeTokenResponse(BaseModel):
    agent_id: str
    url: str
    api_key: str
    relay_url: str


@router.get("/transport", response_model=VoiceTransportRead)
def get_voice_transport() -> VoiceTransportRead:
    """Return the authoritative server transport selector and available options."""
    operator_controls = get_operator_controls_service()
    settings_data = operator_controls.get_settings()
    current_transport = settings_data.transport
    if current_transport not in AVAILABLE_DIRECT_TRANSPORTS:
        current_transport = "xai_grok_voice"

    if current_transport == "direct_gpt_live":
        active_target = "/api/admin/business-assistant/voice/realtime"
    else:
        active_target = f"wss://api.x.ai/v1/realtime?agent_id={settings.XAI_REALTIME_AGENT_ID}"

    return VoiceTransportRead(
        transport=current_transport,
        available_transports=list(AVAILABLE_DIRECT_TRANSPORTS),
        agent_name="bookings-business-assistant",
        active_target=active_target,
    )


@router.patch("/transport", response_model=VoiceTransportRead)
def update_voice_transport(
    payload: VoiceTransportUpdate,
    user: User = Depends(get_current_owner),
) -> VoiceTransportRead:
    """Update active voice transport mode dynamically."""
    operator_controls = get_operator_controls_service()
    if payload.transport and payload.transport not in AVAILABLE_DIRECT_TRANSPORTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_TRANSPORT",
                "message": f"Transport '{payload.transport}' is not supported. Active direct transports: {AVAILABLE_DIRECT_TRANSPORTS}",
            },
        )
    try:
        operator_controls.update_settings(OperatorSettingsUpdate(transport=payload.transport))
    except (InvalidTransportError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_TRANSPORT", "message": str(exc)},
        ) from exc

    return get_voice_transport()


@router.get("/realtime/xai-token", response_model=XAIRealtimeTokenResponse)
def get_xai_realtime_token() -> XAIRealtimeTokenResponse:
    """Return xAI Realtime token and WebSocket connection endpoints."""
    return XAIRealtimeTokenResponse(
        agent_id=settings.XAI_REALTIME_AGENT_ID,
        url=f"{settings.XAI_REALTIME_URL}?agent_id={settings.XAI_REALTIME_AGENT_ID}",
        api_key=settings.XAI_API_KEY,
        relay_url="/api/admin/business-assistant/voice/realtime/xai-ws",
    )


@router.websocket("/realtime/xai-ws")
async def websocket_xai_relay(websocket: WebSocket, conversation_id: Optional[int] = None):
    """Secure browser connection relay to xAI Realtime WebSocket API."""
    await websocket.accept()
    if not settings.XAI_API_KEY:
        await websocket.send_json({
            "type": "error",
            "error": {"message": "XAI_API_KEY is not configured on the server."},
        })
        await websocket.close()
        return

    target_url = f"{settings.XAI_REALTIME_URL}?agent_id={settings.XAI_REALTIME_AGENT_ID}"
    headers = {"Authorization": f"Bearer {settings.XAI_API_KEY}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(target_url, headers=headers) as upstream_ws:
                async def client_to_upstream():
                    try:
                        while True:
                            msg_text = await websocket.receive_text()
                            if upstream_ws.closed:
                                break
                            await upstream_ws.send_str(msg_text)
                    except (WebSocketDisconnect, asyncio.CancelledError):
                        pass
                    except Exception:
                        pass
                    finally:
                        if not upstream_ws.closed:
                            try:
                                await upstream_ws.close()
                            except Exception:
                                pass

                async def upstream_to_client():
                    try:
                        async for msg in upstream_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                if websocket.client_state == WebSocketState.CONNECTED:
                                    await websocket.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                if websocket.client_state == WebSocketState.CONNECTED:
                                    await websocket.send_bytes(msg.data)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR):
                                break
                    except (asyncio.CancelledError, WebSocketDisconnect):
                        pass
                    except Exception:
                        pass

                client_task = asyncio.create_task(client_to_upstream())
                upstream_task = asyncio.create_task(upstream_to_client())

                done, pending = await asyncio.wait(
                    [client_task, upstream_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
    except Exception as exc:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"type": "error", "error": {"message": str(exc)}})
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        except Exception:
            pass


@router.post(
    "/conversations/{conversation_id}/session",
    response_model=VoiceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_session(
    conversation_id: DatabaseId,
    payload: VoiceSessionCreateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> VoiceSessionResponse:
    """Issue authenticated voice session matching direct WebRTC or xAI Grok Voice."""
    service = BusinessAssistantService(db, tenant.id, user.id)
    service.verify_rollout_access(tenant=tenant, user=user)

    try:
        service.get_conversation(conversation_id=conversation_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc

    operator_controls = get_operator_controls_service()
    requested_transport = payload.transport
    active_transport = operator_controls.get_settings().transport
    effective_transport = requested_transport or active_transport

    # 1. Reject obsolete LiveKit transports
    if effective_transport in ("local_livekit", "cloud_livekit", "livekit_gpt_live"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "DECOMMISSIONED_TRANSPORT",
                "message": f"Transport '{effective_transport}' has been decommissioned. Please select 'direct_gpt_live' or 'xai_grok_voice'.",
            },
        )

    # 2. Route: xAI Grok Voice Realtime WebSocket transport
    if effective_transport == "xai_grok_voice":
        if not settings.XAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "XAI_CONFIGURATION_REQUIRED",
                    "message": "xAI Grok Voice is not configured. Server administrator must set XAI_API_KEY.",
                },
            )
        xai_sess_id = f"xai_{uuid.uuid4().hex}"
        try:
            operator_controls.acquire_session(
                session_id=xai_sess_id,
                tenant_id=tenant.id,
                user_id=user.id,
                conversation_id=conversation_id,
                ttl_seconds=600,
                force_restart=bool(payload.force_restart),
                transport="xai_grok_voice",
            )
        except ConcurrencyLimitExceeded as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="CONCURRENCY_LIMIT_EXCEEDED",
                message=str(exc),
                conversation_id=conversation_id,
                transport="xai_grok_voice",
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": str(exc),
                },
            ) from exc

        return VoiceSessionResponse(
            transport="xai_grok_voice",
            session_id=xai_sess_id,
            livekit_url=f"{settings.XAI_REALTIME_URL}?agent_id={settings.XAI_REALTIME_AGENT_ID}",
            token=settings.XAI_API_KEY,
            agent_name=settings.XAI_REALTIME_AGENT_ID,
            expires_in=600,
            endpoint="/api/admin/business-assistant/voice/realtime/xai-ws",
        )

    # 3. Route: Direct WebRTC (OpenAI GPT-Live)
    if effective_transport == "direct_gpt_live":
        if not payload.sdp:
            direct_sess_id = f"direct_{uuid.uuid4().hex}"
            try:
                operator_controls.acquire_session(
                    session_id=direct_sess_id,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    conversation_id=conversation_id,
                    ttl_seconds=600,
                    force_restart=bool(payload.force_restart),
                    transport="direct_gpt_live",
                )
            except ConcurrencyLimitExceeded as exc:
                service.record_assistant_error(
                    source="operator_controls",
                    error_code="CONCURRENCY_LIMIT_EXCEEDED",
                    message=str(exc),
                    conversation_id=conversation_id,
                    transport="direct_gpt_live",
                    route="/conversations/{conversation_id}/session",
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                        "message": str(exc),
                    },
                ) from exc

            return VoiceSessionResponse(
                transport="direct_gpt_live",
                session_id=direct_sess_id,
                endpoint="/api/admin/business-assistant/voice/realtime",
            )

        try:
            diag_mode = service.get_diagnostic_mode()
            session_config = build_gpt_live_session_config(diagnostic_mode=diag_mode)
            runtime = get_gpt_live_runtime()
            try:
                created = runtime.create_session(payload.sdp, session_config=session_config)
            except TypeError:
                created = runtime.create_session(payload.sdp)
        except GPTLiveConfigurationError as exc:
            service.record_assistant_error(
                source="gpt_live",
                error_code="GPT_LIVE_CONFIGURATION_REQUIRED",
                message=str(exc),
                conversation_id=conversation_id,
                transport="direct_gpt_live",
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "GPT_LIVE_CONFIGURATION_REQUIRED",
                    "message": "Voice setup is incomplete. Server administrator must configure OPENAI_API_KEY.",
                },
            ) from exc
        except GPTLiveInvalidSdpError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "GPT_LIVE_INVALID_SDP",
                    "message": "The browser could not create a valid voice offer.",
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

        try:
            operator_controls.acquire_session(
                session_id=created.session_id,
                tenant_id=tenant.id,
                user_id=user.id,
                conversation_id=conversation_id,
                ttl_seconds=600,
                force_restart=bool(payload.force_restart),
                transport="direct_gpt_live",
            )
        except ConcurrencyLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": str(exc),
                },
            ) from exc

        return VoiceSessionResponse(
            transport="direct_gpt_live",
            session_id=created.session_id,
            sdp=created.sdp,
            endpoint="/api/admin/business-assistant/voice/realtime",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported transport: '{effective_transport}'. Supported: {AVAILABLE_DIRECT_TRANSPORTS}",
    )


@router.post(
    "/sessions/{session_id}/heartbeat",
    response_model=dict,
)
def heartbeat_voice_session_endpoint(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
) -> dict:
    """Record client heartbeat to keep voice session active and prevent idle expiration."""
    if not session_id or session_id.lower() in ("null", "undefined", "none", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_SESSION_ID",
                "message": "A valid session ID is required.",
            },
        )
    operator_controls = get_operator_controls_service()
    if not operator_controls.heartbeat_session(session_id=session_id, tenant_id=tenant.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "VOICE_SESSION_NOT_FOUND",
                "message": "Voice session is inactive or not found.",
            },
        )
    return {"ok": True}


@router.post(
    "/sessions/prune",
    response_model=dict,
)
def prune_tenant_voice_sessions_endpoint(
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
) -> dict:
    """Prune expired and stale voice sessions for current tenant."""
    operator_controls = get_operator_controls_service()
    reaped = operator_controls.reap_stale_sessions()
    return {
        "ok": True,
        "reaped": reaped,
        "active_sessions_tenant": operator_controls.active_session_count(tenant.id),
        "active_sessions_global": operator_controls.active_session_count(),
    }


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def release_voice_session_endpoint(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
) -> None:
    """Release an active voice session concurrency slot upon shutdown or disconnect."""
    if not session_id or session_id.lower() in ("null", "undefined", "none", ""):
        return
    operator_controls = get_operator_controls_service()
    operator_controls.release_session(session_id)
