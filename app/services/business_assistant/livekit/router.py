"""FastAPI router for LiveKit voice assistant token issuance, transport routing, and dispatch."""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import DatabaseId, get_current_owner, get_current_staff, get_current_tenant, get_db
from app.core.config import settings
from app.core.operator_controls import (
    ConcurrencyLimitExceeded,
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
from app.services.business_assistant.livekit.token_service import (
    LiveKitConfigurationError,
    LiveKitNetworkError,
    LiveKitQuotaExhaustedError,
    LiveKitTokenError,
    LiveKitTokenService,
)
from app.services.business_assistant.service import BusinessAssistantService

router = APIRouter(prefix="/business-assistant/voice", tags=["Business Assistant Voice"])

TransportType = Literal["xai_grok_voice", "direct_gpt_live", "local_livekit", "cloud_livekit", "livekit_gpt_live"]


class VoiceTransportRead(BaseModel):
    """Authoritative server transport configuration."""

    transport: str
    available_transports: List[str]
    agent_name: str
    active_target: Optional[str] = None
    cloud_livekit_url: Optional[str] = None
    cloud_livekit_api_key_masked: Optional[str] = None
    cloud_livekit_api_secret_masked: Optional[str] = None
    cloud_configured: bool = False


class VoiceTransportUpdate(BaseModel):
    """Payload to mutate authoritative voice transport mode and credentials."""

    transport: Optional[str] = Field(None, description="Transport toggle ('direct_gpt_live', 'local_livekit', 'cloud_livekit')")
    cloud_livekit_url: Optional[str] = Field(None, description="LiveKit Cloud URL")
    cloud_livekit_api_key: Optional[str] = Field(None, description="LiveKit Cloud API Key")
    cloud_livekit_api_secret: Optional[str] = Field(None, description="LiveKit Cloud API Secret")


class VoiceSessionCreateRequest(BaseModel):
    """Voice session initiation request with transport selector and optional SDP."""

    transport: Optional[TransportType] = Field(
        None,
        description="Transport selector. If omitted, uses server authoritative setting.",
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
    """Unified voice session response supporting both LiveKit room token and direct WebRTC."""

    transport: str
    session_id: str
    livekit_url: Optional[str] = None
    token: Optional[str] = None
    room_name: Optional[str] = None
    participant_identity: Optional[str] = None
    agent_name: Optional[str] = None
    expires_in: Optional[int] = None
    sdp: Optional[str] = None
    endpoint: Optional[str] = None


class VoiceTokenRefreshRequest(BaseModel):
    """Optional payload to supply conversation_id during session token refresh."""

    conversation_id: Optional[DatabaseId] = Field(
        None,
        description="Associated conversation ID. If omitted, validated from active session context.",
    )


class VoiceTokenRefreshResponse(BaseModel):
    """Refreshed room token response with updated validity window."""

    transport: str = "local_livekit"
    session_id: str
    token: str
    livekit_url: str
    room_name: str
    participant_identity: str
    agent_name: str
    expires_in: int


def get_token_service() -> LiveKitTokenService:
    """Dependency provider for LiveKit token issuance."""
    operator_controls = get_operator_controls_service()
    url, key, secret = operator_controls.get_livekit_target_for_mode()
    return LiveKitTokenService(api_key=key, api_secret=secret, livekit_url=url)


@router.get("/transport", response_model=VoiceTransportRead)
def get_voice_transport() -> VoiceTransportRead:
    """Return the authoritative server transport selector and available options."""
    operator_controls = get_operator_controls_service()
    settings_data = operator_controls.get_settings()
    active_target = settings_data.active_livekit_url
    if settings_data.transport == "direct_gpt_live":
        active_target = "/api/admin/business-assistant/voice/realtime"
    elif settings_data.transport == "xai_grok_voice":
        active_target = f"wss://api.x.ai/v1/realtime?agent_id={settings.XAI_REALTIME_AGENT_ID}"

    return VoiceTransportRead(
        transport=settings_data.transport,
        available_transports=settings_data.available_transports,
        agent_name=settings.LIVEKIT_DEFAULT_AGENT_NAME,
        active_target=active_target,
        cloud_livekit_url=settings_data.cloud_livekit_url,
        cloud_livekit_api_key_masked=settings_data.cloud_livekit_api_key_masked,
        cloud_livekit_api_secret_masked=settings_data.cloud_livekit_api_secret_masked,
        cloud_configured=settings_data.cloud_configured,
    )


class XAIRealtimeTokenResponse(BaseModel):
    agent_id: str
    url: str
    api_key: str
    relay_url: str


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
            "error": {"message": "XAI_API_KEY is not configured on the server."}
        })
        await websocket.close()
        return

    import aiohttp
    import asyncio
    from starlette.websockets import WebSocketDisconnect, WebSocketState

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


@router.patch("/transport", response_model=VoiceTransportRead)
def update_voice_transport(
    payload: VoiceTransportUpdate,
    user: User = Depends(get_current_owner),
) -> VoiceTransportRead:
    """Update active voice transport mode and optional cloud configuration dynamically."""
    operator_controls = get_operator_controls_service()
    try:
        from app.core.operator_controls import InvalidTransportError, OperatorSettingsUpdate
        operator_controls.update_settings(
            OperatorSettingsUpdate(
                transport=payload.transport,
                cloud_livekit_url=payload.cloud_livekit_url,
                cloud_livekit_api_key=payload.cloud_livekit_api_key,
                cloud_livekit_api_secret=payload.cloud_livekit_api_secret,
            )
        )
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

    return get_voice_transport()


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
    token_service: LiveKitTokenService = Depends(get_token_service),
) -> VoiceSessionResponse:
    """Issue authenticated voice session matching the selected or configured transport."""
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
    target_transport = "local_livekit" if effective_transport == "livekit_gpt_live" else effective_transport
    response_transport = requested_transport or effective_transport

    # Route: LiveKit transport (local or cloud)
    if target_transport in ("local_livekit", "cloud_livekit"):
        target_url, api_key, api_secret = operator_controls.get_livekit_target_for_mode(target_transport)
        if target_transport == "cloud_livekit" and (not target_url or not api_key or not api_secret):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "LIVEKIT_CLOUD_CONFIGURATION_REQUIRED",
                    "message": "LiveKit Cloud credentials not configured. Server administrator must set Cloud URL, API Key, and Secret.",
                },
            )
        if target_transport == "local_livekit" and (not target_url or not api_key or not api_secret):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "LIVEKIT_CONFIGURATION_REQUIRED",
                    "message": "LiveKit local credentials not configured. Server administrator must set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.",
                },
            )

        token_svc = (
            token_service
            if (
                token_service.api_key == api_key
                and token_service.livekit_url == target_url
                and token_service.api_secret == api_secret
            )
            else LiveKitTokenService(api_key=api_key, api_secret=api_secret, livekit_url=target_url)
        )
        try:
            token_result = token_svc.create_room_token(
                tenant_id=tenant.id,
                user_id=user.id,
                conversation_id=conversation_id,
                transport=response_transport,
            )
        except LiveKitConfigurationError as exc:
            service.record_assistant_error(
                source="livekit",
                error_code="LIVEKIT_CONFIGURATION_REQUIRED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "LIVEKIT_CONFIGURATION_REQUIRED",
                    "message": "LiveKit voice setup is incomplete. An administrator must configure server credentials.",
                },
            ) from exc
        except LiveKitQuotaExhaustedError as exc:
            service.record_assistant_error(
                source="livekit",
                error_code="LIVEKIT_QUOTA_EXHAUSTED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "LIVEKIT_QUOTA_EXHAUSTED",
                    "message": "LiveKit voice provider rate limit or quota exhausted. Please try again later, switch to direct WebRTC, or continue in text.",
                    "details": {"fallback_transport": "direct_gpt_live"},
                },
            ) from exc
        except LiveKitNetworkError as exc:
            service.record_assistant_error(
                source="livekit",
                error_code="LIVEKIT_NETWORK_DISCONNECTED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "LIVEKIT_NETWORK_DISCONNECTED",
                    "message": "Connection to LiveKit media server failed. Please check network connectivity, retry, or switch to direct WebRTC.",
                    "details": {"fallback_transport": "direct_gpt_live"},
                },
            ) from exc
        except (LiveKitTokenError, ValueError) as exc:
            service.record_assistant_error(
                source="livekit",
                error_code="LIVEKIT_TOKEN_GENERATION_FAILED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "LIVEKIT_TOKEN_GENERATION_FAILED",
                    "message": f"Failed to issue LiveKit room token: {str(exc)}",
                },
            ) from exc
        except Exception as exc:
            service.record_assistant_error(
                source="livekit",
                error_code="LIVEKIT_TOKEN_GENERATION_ERROR",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "LIVEKIT_TOKEN_GENERATION_ERROR",
                    "message": "An error occurred while generating the voice session token.",
                },
            ) from exc

        try:
            operator_controls.acquire_session(
                session_id=token_result.session_id,
                tenant_id=tenant.id,
                user_id=user.id,
                conversation_id=conversation_id,
                ttl_seconds=token_result.expires_in,
                force_restart=bool(payload.force_restart),
            )
        except ConcurrencyLimitExceeded as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="CONCURRENCY_LIMIT_EXCEEDED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": str(exc),
                },
            ) from exc
        except Exception as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="SESSION_ACQUISITION_FAILED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "SESSION_ACQUISITION_FAILED",
                    "message": f"Failed to acquire voice session slot: {str(exc)}",
                },
            ) from exc

        return VoiceSessionResponse(
            transport=response_transport,
            session_id=token_result.session_id,
            livekit_url=token_result.livekit_url,
            token=token_result.token,
            room_name=token_result.room_name,
            participant_identity=token_result.participant_identity,
            agent_name=token_result.agent_name,
            expires_in=token_result.expires_in,
        )

    # Route: xAI Grok Voice Realtime WebSocket transport
    if target_transport == "xai_grok_voice":
        if not settings.XAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "XAI_CONFIGURATION_REQUIRED",
                    "message": "xAI Grok Voice is not configured. Server administrator must set XAI_API_KEY.",
                },
            )
        import uuid
        xai_sess_id = f"xai_{uuid.uuid4().hex}"
        try:
            operator_controls.acquire_session(
                session_id=xai_sess_id,
                tenant_id=tenant.id,
                user_id=user.id,
                conversation_id=conversation_id,
                ttl_seconds=600,
                force_restart=bool(payload.force_restart),
            )
        except ConcurrencyLimitExceeded as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="CONCURRENCY_LIMIT_EXCEEDED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": str(exc),
                },
            ) from exc
        except Exception as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="SESSION_ACQUISITION_FAILED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "SESSION_ACQUISITION_FAILED",
                    "message": f"Failed to acquire voice session slot: {str(exc)}",
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

    # Route: Direct WebRTC transport
    if target_transport == "direct_gpt_live":
        if not payload.sdp:
            import uuid
            direct_sess_id = f"direct_{uuid.uuid4().hex}"
            try:
                operator_controls.acquire_session(
                    session_id=direct_sess_id,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    conversation_id=conversation_id,
                    ttl_seconds=600,
                    force_restart=bool(payload.force_restart),
                )
            except ConcurrencyLimitExceeded as exc:
                service.record_assistant_error(
                    source="operator_controls",
                    error_code="CONCURRENCY_LIMIT_EXCEEDED",
                    message=str(exc),
                    conversation_id=conversation_id,
                    transport=response_transport,
                    route="/conversations/{conversation_id}/session",
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                        "message": str(exc),
                    },
                ) from exc
            except Exception as exc:
                service.record_assistant_error(
                    source="operator_controls",
                    error_code="SESSION_ACQUISITION_FAILED",
                    message=str(exc),
                    conversation_id=conversation_id,
                    transport=response_transport,
                    route="/conversations/{conversation_id}/session",
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error_code": "SESSION_ACQUISITION_FAILED",
                        "message": f"Failed to acquire voice session slot: {str(exc)}",
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
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "GPT_LIVE_CONFIGURATION_REQUIRED",
                    "message": "Voice setup is incomplete. An administrator must configure the server-side OpenAI project key.",
                },
            ) from exc
        except GPTLiveInvalidSdpError as exc:
            service.record_assistant_error(
                source="gpt_live",
                error_code="GPT_LIVE_INVALID_SDP",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "GPT_LIVE_INVALID_SDP",
                    "message": "The browser could not create a valid voice offer. Please try again or continue in text.",
                },
            ) from exc
        except GPTLiveProviderUnavailableError as exc:
            service.record_assistant_error(
                source="gpt_live",
                error_code="GPT_LIVE_PROVIDER_UNAVAILABLE",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            details = {}
            if exc.provider_status is not None:
                details["provider_status"] = exc.provider_status
            if exc.provider_code is not None:
                details["provider_code"] = exc.provider_code
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "GPT_LIVE_PROVIDER_UNAVAILABLE",
                    "message": "The voice provider could not start the session. Please try again later or continue in text.",
                    "details": details,
                },
            ) from exc
        except Exception as exc:
            service.record_assistant_error(
                source="gpt_live",
                error_code="GPT_LIVE_PROVIDER_ERROR",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "GPT_LIVE_PROVIDER_ERROR",
                    "message": f"Direct WebRTC session creation failed: {str(exc)}",
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
            )
        except ConcurrencyLimitExceeded as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="CONCURRENCY_LIMIT_EXCEEDED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": str(exc),
                },
            ) from exc
        except Exception as exc:
            service.record_assistant_error(
                source="operator_controls",
                error_code="SESSION_ACQUISITION_FAILED",
                message=str(exc),
                conversation_id=conversation_id,
                transport=response_transport,
                route="/conversations/{conversation_id}/session",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "SESSION_ACQUISITION_FAILED",
                    "message": f"Failed to acquire voice session slot: {str(exc)}",
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
        detail=f"Unsupported transport: '{effective_transport}'",
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



@router.post(
    "/sessions/{session_id}/refresh",
    response_model=VoiceTokenRefreshResponse,
)
def refresh_voice_session_endpoint(
    session_id: str,
    payload: Optional[VoiceTokenRefreshRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
    token_service: LiveKitTokenService = Depends(get_token_service),
) -> VoiceTokenRefreshResponse:
    """Revalidate tenant authorization and re-issue short-lived room token for active session."""
    if not session_id or session_id.lower() in ("null", "undefined", "none", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_SESSION_ID",
                "message": "A valid session ID is required for token refresh.",
            },
        )
    service = BusinessAssistantService(db, tenant.id, user.id)
    service.verify_rollout_access(tenant=tenant, user=user)

    conv_id = payload.conversation_id if payload and payload.conversation_id else None
    if conv_id is not None:
        try:
            service.get_conversation(conversation_id=conv_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            ) from exc

    operator_controls = get_operator_controls_service()
    if not operator_controls.is_session_active(session_id=session_id, tenant_id=tenant.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "VOICE_SESSION_REVOKED",
                "message": "Voice session is revoked or inactive. Re-authentication rejected.",
            },
        )
    operator_controls.heartbeat_session(session_id=session_id, tenant_id=tenant.id)

    try:
        active_transport = operator_controls.get_settings().transport
        if active_transport == "livekit_gpt_live":
            active_transport = "local_livekit"

        token_result = token_service.create_room_token(
            tenant_id=tenant.id,
            user_id=user.id,
            conversation_id=conv_id or 1,
            transport=active_transport,
        )
    except LiveKitConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LIVEKIT_CONFIGURATION_REQUIRED",
                "message": "LiveKit voice setup is incomplete.",
            },
        ) from exc
    except LiveKitQuotaExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "LIVEKIT_QUOTA_EXHAUSTED",
                "message": "Voice quota exhausted during token refresh.",
            },
        ) from exc
    except LiveKitNetworkError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "LIVEKIT_NETWORK_DISCONNECTED",
                "message": "Connection to LiveKit media server failed.",
            },
        ) from exc
    except (LiveKitTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LIVEKIT_TOKEN_GENERATION_FAILED",
                "message": f"Failed to issue LiveKit room token: {str(exc)}",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LIVEKIT_TOKEN_GENERATION_ERROR",
                "message": "An error occurred while generating the voice session token.",
            },
        ) from exc

    return VoiceTokenRefreshResponse(
        transport=token_result.transport,
        session_id=session_id,
        token=token_result.token,
        livekit_url=token_result.livekit_url,
        room_name=token_result.room_name,
        participant_identity=token_result.participant_identity,
        agent_name=token_result.agent_name,
        expires_in=token_result.expires_in,
    )


@router.post(
    "/conversations/{conversation_id}/session/refresh",
    response_model=VoiceTokenRefreshResponse,
)
def refresh_conversation_session_endpoint(
    conversation_id: DatabaseId,
    payload: VoiceTokenRefreshRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
    token_service: LiveKitTokenService = Depends(get_token_service),
) -> VoiceTokenRefreshResponse:
    """Alternative convenience endpoint to refresh token by conversation and session ID."""
    session_id = payload.conversation_id if payload and isinstance(payload.conversation_id, str) else None
    if not session_id or str(session_id).lower() in ("null", "undefined", "none", ""):
        session_id = f"sess_conv_{conversation_id}"
    return refresh_voice_session_endpoint(
        session_id=session_id,
        payload=payload,
        tenant=tenant,
        user=user,
        db=db,
        token_service=token_service,
    )
