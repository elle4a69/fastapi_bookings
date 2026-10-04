"""Authenticated text conversation API for the internal Business Assistant."""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_current_owner, get_current_staff, get_current_tenant, get_db
from ...core.config import settings
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
    CampaignAudienceCriteriaInput,
    CampaignAudiencePreviewRead,
    CampaignProposalApproveRequest,
    CampaignProposalCreate,
    CampaignProposalRead,
    CampaignProposalResponse,
    CustomerConversationMessageRead,
    CustomerConversationSummaryRead,
    CustomerConversationThreadRead,
    CustomerMessageDraftCreate,
    CustomerMessageDraftRead,
    CustomerMessageDraftResponse,
    SupportTicketApprovalRequest,
    SupportTicketApprovalResponse,
    SupportTicketCreate,
    SupportTicketCreateRead,
    SupportTicketEventRead,
    SupportTicketRead,
    BusinessAssistantToolExecutionRequest,
    BusinessAssistantToolExecutionResponse,
    BusinessRuleActivateRequest,
    BusinessRuleDraftCreate,
    BusinessRuleDraftResponse,
    BusinessRuleRead,
    CuratorQuestionRead,
    CuratorQuestionResolveRequest,
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
    ConfirmationError,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    ConfirmationSignatureError,
    DynamicFactRejectedError,
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


def _validate_realtime_origin(request: Request) -> None:
    """Validate origin header against allowlisted frontend origins if present."""
    origin = request.headers.get("origin")
    if not origin:
        return
    clean_origin = origin.strip().rstrip("/").casefold()
    allowed_raw = [o.strip().rstrip("/").casefold() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
    if "*" in allowed_raw or clean_origin in allowed_raw:
        return
    host = request.headers.get("host")
    if host:
        clean_host = host.strip().casefold()
        if clean_origin in (f"http://{clean_host}", f"https://{clean_host}"):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cross-origin request to realtime voice session is not permitted.",
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
    _validate_realtime_origin(request)
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


@router.post(
    "/conversations/{conversation_id}/tools",
    response_model=BusinessAssistantToolExecutionResponse,
)
@router.post(
    "/conversations/{conversation_id}/realtime/tools",
    response_model=BusinessAssistantToolExecutionResponse,
)
def execute_tool(
    conversation_id: DatabaseId,
    payload: BusinessAssistantToolExecutionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessAssistantToolExecutionResponse:
    """Execute an allowlisted tool through the server-authoritative policy engine."""
    service = _service(db, tenant, user)
    try:
        result = service.execute_tool(
            conversation_id=conversation_id,
            name=payload.name,
            arguments=payload.arguments,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BusinessAssistantToolExecutionResponse(
        status=result.get("status", "ok"),
        result=result if result.get("status") == "ok" else None,
        reason=result.get("reason"),
    )


@router.get("/tickets", response_model=list[SupportTicketRead])
def list_tickets(
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[SupportTicketRead]:
    """List only user-safe tickets created by the authenticated staff user."""
    service = _service(db, tenant, user)
    return [
        SupportTicketRead.model_validate(ticket)
        for ticket in service.list_tickets(limit=limit, status=status, category=category)
    ]


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
            observed_behaviour=payload.observed_behaviour,
            affected_product_area=payload.affected_product_area,
            user_impact=payload.user_impact,
            acceptance_criteria=payload.acceptance_criteria,
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
        confirmation_token=result.confirmation_token,
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


@router.post("/tickets/{ticket_id}/approve", response_model=SupportTicketApprovalResponse)
def approve_ticket_dispatch(
    ticket_id: DatabaseId,
    payload: SupportTicketApprovalRequest = Body(default_factory=SupportTicketApprovalRequest),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> SupportTicketApprovalResponse:
    """Approve an elevated access or security ticket dispatch. Owner only."""
    service = _service(db, tenant, user)
    try:
        approved = service.approve_ticket_dispatch(
            ticket_id=ticket_id,
            confirmation_token=payload.confirmation_token,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (ConfirmationExpiredError, ConfirmationPayloadMismatchError, ConfirmationSignatureError, ConfirmationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SupportTicketApprovalResponse(
        ticket=SupportTicketRead.model_validate(approved),
        action="approved",
        status=approved.status,
    )


@router.post("/tickets/{ticket_id}/reject", response_model=SupportTicketApprovalResponse)
def reject_ticket_dispatch(
    ticket_id: DatabaseId,
    payload: SupportTicketApprovalRequest = Body(default_factory=SupportTicketApprovalRequest),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> SupportTicketApprovalResponse:
    """Reject an elevated access or security ticket dispatch. Owner only."""
    service = _service(db, tenant, user)
    try:
        rejected = service.reject_ticket_dispatch(
            ticket_id=ticket_id,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SupportTicketApprovalResponse(
        ticket=SupportTicketRead.model_validate(rejected),
        action="rejected",
        status=rejected.status,
    )


@router.post("/knowledge/rules/draft", response_model=BusinessRuleDraftResponse, status_code=status.HTTP_201_CREATED)
def draft_business_rule(
    payload: BusinessRuleDraftCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessRuleDraftResponse:
    """Draft a business rule, validate against dynamic facts, and return assistant interpretation with confirmation token."""
    service = _service(db, tenant, user)
    try:
        memory, interpretation, token, hash_val = service.draft_business_rule(
            memory_key=payload.memory_key,
            content=payload.content,
            category=payload.category,
            curator_item_id=payload.curator_item_id,
        )
    except DynamicFactRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "DYNAMIC_FACT_REJECTED",
                "message": str(exc),
                "detected_types": list(exc.detected_types),
            },
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BusinessRuleDraftResponse(
        rule=BusinessRuleRead.model_validate(memory),
        interpretation=interpretation,
        confirmation_token=token,
        payload_hash=hash_val,
    )


@router.get("/knowledge/rules", response_model=list[BusinessRuleRead])
def list_business_rules(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[BusinessRuleRead]:
    """List business rules scoped to the current tenant and user."""
    service = _service(db, tenant, user)
    rules = service.list_business_rules(status=status, limit=limit)
    return [BusinessRuleRead.model_validate(r) for r in rules]


@router.get("/knowledge/rules/{rule_identifier}", response_model=BusinessRuleRead)
def get_business_rule(
    rule_identifier: str,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessRuleRead:
    """Get a business rule by ID or memory_key within tenant scope."""
    service = _service(db, tenant, user)
    try:
        memory = service.get_business_rule(rule_identifier)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business rule not found.") from exc
    return BusinessRuleRead.model_validate(memory)


@router.post("/knowledge/rules/{rule_identifier}/activate", response_model=BusinessRuleRead)
def activate_business_rule(
    rule_identifier: str,
    payload: BusinessRuleActivateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> BusinessRuleRead:
    """Activate a drafted business rule after validating confirmation token binding."""
    service = _service(db, tenant, user)
    try:
        activated = service.activate_business_rule(
            id_or_key=rule_identifier,
            confirmation_token=payload.confirmation_token,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business rule not found.") from exc
    except ConfirmationExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation token has expired.") from exc
    except ConfirmationScopeMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (ConfirmationPayloadMismatchError, ConfirmationSignatureError, ConfirmationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BusinessRuleRead.model_validate(activated)


@router.get("/knowledge/curator/questions", response_model=list[CuratorQuestionRead])
def list_curator_questions(
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[CuratorQuestionRead]:
    """List reviewable curator questions strictly within tenant scope."""
    service = _service(db, tenant, user)
    questions = service.list_curator_questions(status=status, limit=limit)
    return [CuratorQuestionRead.model_validate(q) for q in questions]


@router.post("/knowledge/curator/questions/{question_id}/resolve", response_model=CuratorQuestionRead)
def resolve_curator_question(
    question_id: DatabaseId,
    payload: CuratorQuestionResolveRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> CuratorQuestionRead:
    """Resolve, dismiss, or reject a curator question within tenant scope."""
    service = _service(db, tenant, user)
    try:
        resolved = service.resolve_curator_question(
            curator_item_id=question_id,
            resolution=payload.resolution,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curator question not found.") from exc
    return CuratorQuestionRead.model_validate(resolved)


# ---------------------------------------------------------------------------
# WP5: Customer Operations, Drafts, and Campaign Proposals
# ---------------------------------------------------------------------------

@router.get("/customer/conversations", response_model=list[CustomerConversationSummaryRead])
def search_customer_conversations(
    query: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    provider_id: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> list[CustomerConversationSummaryRead]:
    """Search authorised customer conversations within tenant and provider boundary."""
    service = _service(db, tenant, user)
    try:
        convs = service.search_customer_conversations(
            query=query,
            status=status,
            provider_id=provider_id,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [CustomerConversationSummaryRead(**c) for c in convs]


@router.get("/customer/conversations/{conversation_id}", response_model=CustomerConversationThreadRead)
def get_customer_conversation_thread(
    conversation_id: DatabaseId,
    limit: int = Query(default=20, ge=1, le=50),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CustomerConversationThreadRead:
    """Inspect customer conversation thread, recent messages, and opt-in/opt-out status."""
    service = _service(db, tenant, user)
    try:
        thread = service.get_customer_conversation_thread(conversation_id, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return CustomerConversationThreadRead(**thread)


@router.post("/customer/conversations/{conversation_id}/draft", response_model=CustomerMessageDraftResponse)
def prepare_customer_message_draft(
    conversation_id: DatabaseId,
    payload: CustomerMessageDraftCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CustomerMessageDraftResponse:
    """Prepare a response message draft without live delivery side effects."""
    service = _service(db, tenant, user)
    try:
        draft, token, preview = service.prepare_customer_message_draft(
            conversation_id=conversation_id,
            content=payload.content,
            request_key=payload.request_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return CustomerMessageDraftResponse(
        draft=CustomerMessageDraftRead.model_validate(draft),
        confirmation_token=token,
        preview=preview,
    )


@router.get("/customer/drafts", response_model=list[CustomerMessageDraftRead])
def list_customer_message_drafts(
    conversation_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> list[CustomerMessageDraftRead]:
    """List prepared response message drafts in the active tenant."""
    service = _service(db, tenant, user)
    drafts = service.list_customer_message_drafts(
        conversation_id=conversation_id,
        status=status,
        limit=limit,
    )
    return [CustomerMessageDraftRead.model_validate(d) for d in drafts]


@router.get("/customer/drafts/{draft_id}", response_model=CustomerMessageDraftRead)
def get_customer_message_draft(
    draft_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CustomerMessageDraftRead:
    """Retrieve a prepared response message draft by ID."""
    service = _service(db, tenant, user)
    try:
        draft = service.get_customer_message_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CustomerMessageDraftRead.model_validate(draft)


@router.post("/campaigns/audience-preview", response_model=CampaignAudiencePreviewRead)
def preview_campaign_audience(
    criteria: CampaignAudienceCriteriaInput,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> CampaignAudiencePreviewRead:
    """Calculate and preview server-authoritative campaign audience with explainable criteria."""
    service = _service(db, tenant, user)
    result = service.preview_campaign_audience(
        marketing_opt_in_only=criteria.marketing_opt_in_only,
        active_only=criteria.active_only,
        exclude_pending_holds=criteria.exclude_pending_holds,
        min_completed_bookings=criteria.min_completed_bookings,
        provider_id=criteria.provider_id,
    )
    return CampaignAudiencePreviewRead(**result)


@router.post("/campaigns/proposals", response_model=CampaignProposalResponse)
def create_campaign_proposal(
    payload: CampaignProposalCreate,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> CampaignProposalResponse:
    """Create an explainable campaign proposal with exact recipient snapshot and confirmation token."""
    service = _service(db, tenant, user)
    try:
        proposal, token, summary = service.create_campaign_proposal(
            title=payload.title,
            content=payload.content,
            marketing_opt_in_only=payload.marketing_opt_in_only,
            active_only=payload.active_only,
            exclude_pending_holds=payload.exclude_pending_holds,
            min_completed_bookings=payload.min_completed_bookings,
            provider_id=payload.provider_id,
            request_key=payload.request_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return CampaignProposalResponse(
        proposal=CampaignProposalRead.model_validate(proposal),
        confirmation_token=token,
        summary=summary,
    )


@router.get("/campaigns/proposals", response_model=list[CampaignProposalRead])
def list_campaign_proposals(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> list[CampaignProposalRead]:
    """List campaign proposals scoped to the authenticated tenant."""
    service = _service(db, tenant, user)
    proposals = service.list_campaign_proposals(status=status, limit=limit)
    return [CampaignProposalRead.model_validate(p) for p in proposals]


@router.get("/campaigns/proposals/{proposal_id}", response_model=CampaignProposalRead)
def get_campaign_proposal(
    proposal_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> CampaignProposalRead:
    """Retrieve an explainable campaign proposal by ID."""
    service = _service(db, tenant, user)
    try:
        proposal = service.get_campaign_proposal(proposal_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CampaignProposalRead.model_validate(proposal)


@router.post("/campaigns/proposals/{proposal_id}/approve", response_model=CampaignProposalRead)
def approve_campaign_proposal(
    proposal_id: DatabaseId,
    payload: CampaignProposalApproveRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> CampaignProposalRead:
    """Approve a campaign proposal via confirmation token. Live sending remains strictly disabled."""
    service = _service(db, tenant, user)
    try:
        approved = service.approve_campaign_proposal(
            proposal_id=proposal_id,
            confirmation_token=payload.confirmation_token,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign proposal not found.") from exc
    except ConfirmationExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation token has expired.") from exc
    except ConfirmationScopeMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (ConfirmationPayloadMismatchError, ConfirmationSignatureError, ConfirmationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CampaignProposalRead.model_validate(approved)


