"""Authenticated text conversation API for the internal Business Assistant."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_current_owner, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.business_assistant import (
    BusinessAssistantConversationCreate,
    BusinessAssistantConversationRead,
    BusinessAssistantMessageRead,
    BusinessAssistantRealtimeTurnCreate,
    BusinessAssistantRealtimeTurnRead,
    BusinessAssistantOnboardingProgressRead,
    BusinessAssistantOnboardingProgressUpdate,
    BusinessAssistantOnboardingRead,
    BusinessAssistantProductContextRead,
    BusinessAssistantSetupCountsRead,
    BusinessAssistantTextTurnCreate,
    BusinessAssistantTextTurnRead,
    SupportTicketCreate,
    SupportTicketCreateRead,
    SupportTicketEventRead,
    SupportTicketRead,
)
from ...services.business_assistant import (
    BusinessAssistantService,
    BusinessAssistantStorageUnavailableError,
    BusinessAssistantTextRuntime,
    TextModelClientUnavailableError,
    TextModelConfigurationError,
    TextModelExecutionError,
    TextModelProviderRequestError,
    TextTurnInProgressError,
    TicketContentSafetyError,
    IdempotencyKeyConflictError,
    BusinessAssistantRealtimeRuntime,
    RealtimeConfigurationError,
    RealtimeInvalidSdpError,
    RealtimeProviderUnavailableError,
)

router = APIRouter(prefix="/business-assistant", tags=["Business Assistant"])


def get_text_turn_runtime() -> BusinessAssistantTextRuntime:
    """Create the bounded provider runtime from validated server configuration."""
    return BusinessAssistantTextRuntime.from_settings()


def get_realtime_runtime() -> BusinessAssistantRealtimeRuntime:
    """Create the server-held realtime exchange client from validated configuration."""
    return BusinessAssistantRealtimeRuntime.from_settings()


def _service(db: Session, tenant: Tenant, user: User) -> BusinessAssistantService:
    return BusinessAssistantService(db, tenant.id, user.id)


def _onboarding_response(service: BusinessAssistantService) -> BusinessAssistantOnboardingRead:
    """Build an onboarding response from only scoped durable progress and live native reads."""
    progress = service.get_onboarding_progress()
    context = service.read_product_context()
    setup_counts = None
    if context.availability == "available":
        setup_counts = BusinessAssistantSetupCountsRead(
            active_services=context.active_services or 0,
            active_providers=context.active_providers or 0,
            active_locations=context.active_locations or 0,
        )
    return BusinessAssistantOnboardingRead(
        progress=BusinessAssistantOnboardingProgressRead(
            status=progress.status if progress else "not_started",
            completed_steps=list(progress.completed_steps) if progress else [],
            updated_at=progress.updated_at if progress else None,
        ),
        product_context=BusinessAssistantProductContextRead(
            availability=context.availability,
            enabled_modules=list(context.enabled_modules),
            setup_counts=setup_counts,
        ),
    )


@router.get("/onboarding", response_model=BusinessAssistantOnboardingRead)
def get_onboarding(
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantOnboardingRead:
    """Return live read-only product context and owner-scoped onboarding progress."""
    return _onboarding_response(_service(db, tenant, user))


@router.put("/onboarding/progress", response_model=BusinessAssistantOnboardingRead)
def complete_onboarding_step(
    payload: BusinessAssistantOnboardingProgressUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantOnboardingRead:
    """Record a fixed personal milestone without mutating tenant business settings."""
    service = _service(db, tenant, user)
    service.complete_onboarding_step(step=payload.step)
    return _onboarding_response(service)


@router.get("/conversations", response_model=list[BusinessAssistantConversationRead])
def list_conversations(
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[BusinessAssistantConversationRead]:
    """List only conversations owned by the authenticated staff user."""
    service = _service(db, tenant, user)
    return [BusinessAssistantConversationRead.model_validate(item) for item in service.list_conversations()]


@router.post(
    "/conversations",
    response_model=BusinessAssistantConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: BusinessAssistantConversationCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantConversationRead:
    """Create one idempotent, authenticated staff conversation."""
    service = _service(db, tenant, user)
    try:
        conversation = service.create_or_get_conversation(title=payload.title, request_key=payload.request_key)
    except IdempotencyKeyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request key is already bound to a different conversation payload.",
        ) from exc
    except BusinessAssistantStorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business Assistant storage is unavailable. Please retry after the application migration is complete.",
        ) from exc
    return BusinessAssistantConversationRead.model_validate(conversation)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[BusinessAssistantMessageRead],
)
def list_messages(
    conversation_id: DatabaseId,
    limit: int = Query(default=100, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[BusinessAssistantMessageRead]:
    """Return chronological history only for the authenticated conversation owner."""
    service = _service(db, tenant, user)
    try:
        messages = service.list_messages(conversation_id=conversation_id, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    return [BusinessAssistantMessageRead.model_validate(item) for item in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=BusinessAssistantTextTurnRead,
)
def submit_text_turn(
    conversation_id: DatabaseId,
    payload: BusinessAssistantTextTurnCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantTextTurnRead:
    """Persist a user turn, then run exactly one bounded text generation request."""
    service = _service(db, tenant, user)
    try:
        result = service.submit_text_turn(
            conversation_id=conversation_id,
            content=payload.content,
            request_key=payload.request_key,
            runtime_factory=get_text_turn_runtime,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    except TextModelConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "TEXT_CONFIGURATION_REQUIRED",
                "message": "Text setup is incomplete. An administrator must configure a text model before replies can start. Your message was saved and can be retried later.",
            },
        ) from exc
    except TextModelClientUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "TEXT_CLIENT_UNAVAILABLE",
                "message": "The text response client is unavailable on this server. Your message was saved and can be retried later.",
            },
        ) from exc
    except TextModelProviderRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "TEXT_PROVIDER_REQUEST_REJECTED",
                "message": "The configured text provider rejected this response request. Your message was saved and can be retried after the server configuration is corrected.",
            },
        ) from exc
    except TextModelExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "TEXT_PROVIDER_UNAVAILABLE",
                "message": "The text provider could not generate a reply. Your message was saved and can be retried later.",
            },
        ) from exc
    except TextTurnInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A response for this message is already in progress. Refresh shortly before retrying.",
        ) from exc
    except IdempotencyKeyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request key is already bound to a different message payload.",
        ) from exc
    return BusinessAssistantTextTurnRead(
        user_message=BusinessAssistantMessageRead.model_validate(result.user_message),
        assistant_message=BusinessAssistantMessageRead.model_validate(result.assistant_message),
        duplicate_request=result.duplicate_request,
    )


@router.post("/conversations/{conversation_id}/realtime", response_class=Response)
async def exchange_realtime_sdp(
    conversation_id: DatabaseId,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> Response:
    """Exchange one authenticated browser SDP offer through server-held credentials."""
    service = _service(db, tenant, user)
    try:
        service.get_conversation(conversation_id=conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/sdp":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Realtime voice requires an application/sdp offer.")
    offer = await request.body()
    try:
        answer = get_realtime_runtime().exchange_sdp(offer)
    except RealtimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "REALTIME_CONFIGURATION_REQUIRED",
                "message": "Voice setup is incomplete. An administrator must configure a realtime model before voice can start.",
            },
        ) from exc
    except RealtimeInvalidSdpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "REALTIME_INVALID_SDP",
                "message": "The browser could not create a valid voice offer. Please try voice again or continue in text.",
            },
        ) from exc
    except RealtimeProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "REALTIME_PROVIDER_UNAVAILABLE",
                "message": "The voice provider is temporarily unavailable. Please try again later or continue in text.",
            },
        ) from exc
    return Response(
        content=answer,
        media_type="application/sdp",
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/conversations/{conversation_id}/realtime/turns",
    response_model=BusinessAssistantRealtimeTurnRead,
)
def persist_realtime_turn(
    conversation_id: DatabaseId,
    payload: BusinessAssistantRealtimeTurnCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantRealtimeTurnRead:
    """Persist one completed, ordered realtime transcript pair with no realtime tools."""
    try:
        result = _service(db, tenant, user).persist_realtime_turn(
            conversation_id=conversation_id,
            session_id=str(payload.session_id),
            user_item_id=payload.user_item_id,
            assistant_response_id=payload.assistant_response_id,
            user_transcript=payload.user_transcript,
            assistant_transcript=payload.assistant_transcript,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    except TextTurnInProgressError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A voice transcript event is already being persisted.") from exc
    return BusinessAssistantRealtimeTurnRead(
        user_message=BusinessAssistantMessageRead.model_validate(result.user_message),
        assistant_message=BusinessAssistantMessageRead.model_validate(result.assistant_message),
        duplicate_turn=result.duplicate_turn,
    )


@router.get("/tickets", response_model=list[SupportTicketRead])
def list_tickets(
    limit: int = Query(default=100, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[SupportTicketRead]:
    """List only user-safe tickets created by the authenticated staff user."""
    service = _service(db, tenant, user)
    return [SupportTicketRead.model_validate(ticket) for ticket in service.list_tickets(limit=limit)]


@router.post("/tickets", response_model=SupportTicketCreateRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: SupportTicketCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> SupportTicketCreateRead:
    """Persist a sanitised ticket without sending it to an engineering worker."""
    service = _service(db, tenant, user)
    try:
        result = service.create_or_get_ticket(
            category=payload.category,
            severity=payload.severity,
            title=payload.title,
            description=payload.description,
            request_key=payload.request_key,
            conversation_id=payload.conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    except TicketContentSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IdempotencyKeyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request key is already bound to a different ticket payload.",
        ) from exc
    return SupportTicketCreateRead(
        ticket=SupportTicketRead.model_validate(result.ticket),
        duplicate_ticket=result.duplicate_ticket,
    )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketRead)
def get_ticket(
    ticket_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> SupportTicketRead:
    """Read one ticket only within its authenticated tenant and creator scope."""
    try:
        ticket = _service(db, tenant, user).get_ticket(ticket_id=ticket_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
    return SupportTicketRead.model_validate(ticket)


@router.get("/tickets/{ticket_id}/events", response_model=list[SupportTicketEventRead])
def list_ticket_events(
    ticket_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[SupportTicketEventRead]:
    """Read append-only user-safe lifecycle events for one authorised ticket."""
    try:
        events = _service(db, tenant, user).list_ticket_events(ticket_id=ticket_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
    return [SupportTicketEventRead.model_validate(event) for event in events]
