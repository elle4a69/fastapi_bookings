from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob, SmsAiJob, SmsNote
from ...models.client import Client
from ...schemas.sms_conversation import (
    SmsConversationResponse,
    SmsConversationControlsUpdate,
    SmsDraftReviewRequest,
    SmsConversationActionRequest,
    SmsInternalNoteCreate,
    SmsCorrectionCreate,
    SmsBulkDraftDiscardRequest,
    SmsBulkDraftDiscardResponse,
    SmsCorrectionResponse,
    SmsDraftQueueItem,
    SmsInternalNoteResponse,
    SmsOperationResponse,
    SmsOutboundJobResponse,
)
from ...schemas.sms_message import SmsMessageCreate, SmsMessageResponse
from ...services.sms.outbound_service import (
    enqueue_outbound_message_transactional,
    is_outbound_body_safe,
)
from ...services.sms.operations_service import (
    SmsOperationConflict,
    cancel_pending_ai_jobs,
    ensure_customer_send_allowed,
    get_scoped_account,
    get_scoped_conversation,
    has_enabled_delivery_target,
    null_safe_message_account_scope,
    record_event,
    scoped_drafts,
    timeline_items,
    transition_conversation,
)

router = APIRouter(prefix="/sms/conversations", tags=["sms-conversations"])

@router.get("", response_model=List[SmsConversationResponse])
async def list_conversations(
    provider_id: Optional[int] = None,
    sms_account_id: Optional[int] = None,
    unread_only: bool = False,
    state: Optional[str] = None,
    pinned_only: bool = False,
    search: Optional[str] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(SmsConversation).filter(SmsConversation.tenant_id == tenant.id)

    if provider_id is not None:
        query = query.filter(SmsConversation.provider_id == provider_id)
    if sms_account_id is not None:
        query = query.filter(SmsConversation.sms_account_id == sms_account_id)
    if unread_only:
        query = query.filter(SmsConversation.unread_count > 0)
    if state:
        query = query.filter(SmsConversation.state == state)
    if pinned_only:
        query = query.filter(SmsConversation.is_pinned.is_(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.outerjoin(Client, Client.id == SmsConversation.client_id).filter(
            or_(
                SmsConversation.customer_address.ilike(term),
                Client.name.ilike(term),
            )
        )

    # Sort pinned conversations first, then by last activity
    conversations = query.order_by(
        SmsConversation.is_pinned.desc(),
        SmsConversation.last_activity_at.desc(),
    ).all()

    # Map to response format
    result = []
    for conv in conversations:
        if get_scoped_conversation(
            db, tenant_id=tenant.id, conversation_id=conv.id
        ) is None:
            continue
        client_name = conv.client.name if conv.client else None
        result.append(
            SmsConversationResponse(
                id=conv.id,
                tenant_id=conv.tenant_id,
                provider_id=conv.provider_id,
                sms_account_id=conv.sms_account_id,
                customer_address=conv.customer_address,
                client_id=conv.client_id,
                client_name=client_name,
                state=conv.state,
                unread_count=conv.unread_count,
                is_pinned=bool(conv.is_pinned),
                is_blocked=bool(conv.is_blocked),
                ai_enabled=bool(conv.ai_enabled),
                last_activity_at=conv.last_activity_at,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return result


@router.get("/jobs", response_model=List[SmsOutboundJobResponse])
async def list_outbound_jobs(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    candidates = (
        db.query(SmsOutboundJob)
        .join(SmsMessage, SmsMessage.id == SmsOutboundJob.message_id)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            null_safe_message_account_scope(),
            or_(
                SmsOutboundJob.sms_account_id == SmsMessage.sms_account_id,
                and_(
                    SmsOutboundJob.sms_account_id.is_(None),
                    SmsMessage.sms_account_id.is_(None),
                ),
            ),
        )
        .order_by(SmsOutboundJob.created_at.desc())
        .limit(50)
        .all()
    )
    jobs = [
        job
        for job in candidates
        if get_scoped_conversation(
            db,
            tenant_id=tenant.id,
            conversation_id=job.message.conversation_id,
        )
        is not None
    ]

    return [
        {
            "id": job.id,
            "message_id": job.message_id,
            "sms_account_id": job.sms_account_id,
            "status": job.status,
            "retry_count": job.retry_count,
            "has_error": bool(job.error_log),
            "created_at": job.created_at,
        }
        for job in jobs
    ]


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_200_OK,
    response_model=SmsOperationResponse,
)
async def retry_outbound_job(
    job_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    job = (
        db.query(SmsOutboundJob)
        .join(SmsMessage, SmsMessage.id == SmsOutboundJob.message_id)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsOutboundJob.id == job_id,
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            or_(
                SmsOutboundJob.sms_account_id == SmsMessage.sms_account_id,
                and_(
                    SmsOutboundJob.sms_account_id.is_(None),
                    SmsMessage.sms_account_id.is_(None),
                ),
            ),
            SmsMessage.provider_id == SmsConversation.provider_id,
            null_safe_message_account_scope(),
        )
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Outbound job not found.")
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail="Only failed outbound jobs can be retried.")
    conversation = get_scoped_conversation(
        db,
        tenant_id=tenant.id,
        conversation_id=job.message.conversation_id,
    )
    if conversation is None or not has_enabled_delivery_target(db, conversation):
        raise HTTPException(status_code=409, detail="The delivery channel is unavailable.")
    try:
        ensure_customer_send_allowed(conversation)
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not is_outbound_body_safe(job.message.body):
        raise HTTPException(status_code=409, detail="The message failed outbound safety validation.")

    job.status = "PENDING"
    job.retry_count = 0
    job.error_log = None

    # Also reset the message status to queued
    message = db.query(SmsMessage).filter(SmsMessage.id == job.message_id).first()
    if message:
        message.status = "queued"

    record_event(
        db,
        conversation_id=job.message.conversation_id,
        event_type="outbound_retry_requested",
        actor_id=admin_user.id,
        metadata={"message_id": job.message_id},
    )

    db.commit()
    return {"status": "success", "detail": "Job marked for retry."}


# --- Draft Messages Review Queue ---


@router.get("/drafts/queue", response_model=List[SmsDraftQueueItem])
async def list_drafts_queue(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all pending AI draft messages across conversations for this tenant."""
    drafts = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(SmsConversation.tenant_id == tenant.id, SmsMessage.status == "draft")
        .filter(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            null_safe_message_account_scope(),
        )
        .order_by(SmsMessage.occurred_at.desc())
        .all()
    )

    results = []
    for d in drafts:
        conv = d.conversation
        if get_scoped_conversation(
            db, tenant_id=tenant.id, conversation_id=conv.id
        ) is None:
            continue
        client_name = conv.client.name if (conv and conv.client) else None
        results.append(
            {
                "id": d.id,
                "message_id": d.id,
                "conversation_id": d.conversation_id,
                "customer_address": conv.customer_address if conv else "",
                "client_name": client_name,
                "body": d.body,
                "direction": d.direction,
                "author_type": d.author_type,
                "status": d.status,
                "occurred_at": d.occurred_at,
                "received_at": d.received_at,
            }
        )
    return results


def _scoped_message_query(db: Session, *, tenant_id: int, message_id: int):
    return (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.id == message_id,
            SmsMessage.tenant_id == tenant_id,
            SmsConversation.tenant_id == tenant_id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            null_safe_message_account_scope(),
        )
    )


def _verified_approved_draft_winner(
    db: Session, *, tenant_id: int, message_id: int
) -> SmsMessage | None:
    message = _scoped_message_query(
        db, tenant_id=tenant_id, message_id=message_id
    ).first()
    if message is None or message.status not in {"queued", "sending", "sent", "delivered"}:
        return None
    job = db.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == message.id,
        SmsOutboundJob.sms_account_id == message.sms_account_id,
    ).first()
    return message if job is not None else None


def _verified_manual_send_winner(
    db: Session,
    *,
    tenant_id: int,
    provider_id: int,
    conversation_id: int,
    sms_account_id: int | None,
    client_request_id: str,
    body: str,
) -> SmsMessage | None:
    message = db.query(SmsMessage).filter(
        SmsMessage.tenant_id == tenant_id,
        SmsMessage.provider_id == provider_id,
        SmsMessage.conversation_id == conversation_id,
        SmsMessage.sms_account_id == sms_account_id,
        SmsMessage.client_request_id == client_request_id,
        SmsMessage.author_type == "staff",
        SmsMessage.body == body,
        SmsMessage.status.in_(("queued", "sending", "sent", "delivered")),
    ).first()
    if message is None:
        return None
    job = db.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == message.id,
        SmsOutboundJob.sms_account_id == sms_account_id,
    ).first()
    return message if job is not None else None


def _approve_locked_draft(
    db: Session,
    *,
    message: SmsMessage,
    tenant_id: int,
    actor_id: int,
) -> SmsMessage:
    if message.status in {"queued", "sending", "sent", "delivered"}:
        winner = _verified_approved_draft_winner(
            db, tenant_id=tenant_id, message_id=message.id
        )
        if winner is not None:
            return winner
        raise HTTPException(status_code=409, detail="Draft approval state is inconsistent.")
    if message.status != "draft":
        raise HTTPException(status_code=409, detail="Only pending drafts can be approved.")

    conversation = get_scoped_conversation(
        db, tenant_id=tenant_id, conversation_id=message.conversation_id
    )
    if conversation is None or not has_enabled_delivery_target(db, conversation):
        raise HTTPException(status_code=409, detail="The delivery channel is unavailable.")
    try:
        ensure_customer_send_allowed(conversation)
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not is_outbound_body_safe(message.body):
        record_event(
            db,
            conversation_id=message.conversation_id,
            event_type="draft_approval_blocked",
            actor_id=actor_id,
            metadata={"message_id": message.id, "reason": "outbound_safety"},
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="The draft failed outbound safety validation.",
        )

    message.direction = "outbound"
    message.status = "queued"
    existing_job = db.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == message.id
    ).first()
    if existing_job is None:
        db.add(
            SmsOutboundJob(
                message_id=message.id,
                sms_account_id=message.sms_account_id,
                status="PENDING",
                retry_count=0,
                created_at=datetime.now(timezone.utc),
            )
        )
    record_event(
        db,
        conversation_id=message.conversation_id,
        event_type="draft_approved",
        actor_id=actor_id,
        metadata={"message_id": message.id},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = _verified_approved_draft_winner(
            db, tenant_id=tenant_id, message_id=message.id
        )
        if winner is None:
            raise HTTPException(
                status_code=409,
                detail="Concurrent draft approval could not be verified.",
            ) from exc
        return winner
    db.refresh(message)
    return message


@router.post(
    "/drafts/{draft_id}/review",
    response_model=SmsMessageResponse,
    responses={409: {"description": "Draft state, delivery, or safety conflict."}},
)
async def review_draft_message(
    draft_id: DatabaseId,
    payload: SmsDraftReviewRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Review a draft message: approve, discard, or edit."""
    message = _scoped_message_query(
        db, tenant_id=tenant.id, message_id=draft_id
    ).with_for_update().first()

    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")
    if get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=message.conversation_id
    ) is None:
        raise HTTPException(status_code=404, detail="Draft message not found.")
    if get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=message.conversation_id
    ) is None:
        raise HTTPException(status_code=404, detail="Draft message not found.")

    new_text = payload.text or payload.body

    if payload.action == "edit":
        if message.status != "draft":
            raise HTTPException(status_code=409, detail="Only pending drafts can be edited.")
        if not new_text:
            raise HTTPException(status_code=422, detail="Edited draft text is required.")
        message.body = new_text.strip()
        message.normalized_body = message.body.lower()
        record_event(
            db,
            conversation_id=message.conversation_id,
            event_type="draft_edited",
            actor_id=admin_user.id,
            metadata={"message_id": message.id},
        )
        db.commit()
        db.refresh(message)
        return message

    elif payload.action == "discard":
        if message.status != "draft":
            raise HTTPException(status_code=409, detail="Only pending drafts can be discarded.")
        message.status = "discarded"
        record_event(
            db,
            conversation_id=message.conversation_id,
            event_type="draft_discarded",
            actor_id=admin_user.id,
            metadata={"message_id": message.id},
        )
        db.commit()
        db.refresh(message)
        return message

    if new_text:
        message.body = new_text.strip()
        message.normalized_body = message.body.lower()
    return _approve_locked_draft(
        db,
        message=message,
        tenant_id=tenant.id,
        actor_id=admin_user.id,
    )


@router.post(
    "/drafts/bulk/discard", response_model=SmsBulkDraftDiscardResponse
)
async def bulk_discard_drafts(
    payload: SmsBulkDraftDiscardRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Explicitly discard selected drafts and audit each affected conversation."""

    drafts = scoped_drafts(db, tenant_id=tenant.id, message_ids=payload.message_ids)
    drafts = [
        draft
        for draft in drafts
        if get_scoped_conversation(
            db, tenant_id=tenant.id, conversation_id=draft.conversation_id
        )
        is not None
    ]
    if len(drafts) != len(set(payload.message_ids)):
        raise HTTPException(
            status_code=409,
            detail="Every selected message must be a pending draft owned by this tenant.",
        )

    by_conversation: dict[int, int] = {}
    for draft in drafts:
        draft.status = "discarded"
        by_conversation[draft.conversation_id] = by_conversation.get(draft.conversation_id, 0) + 1

    for conversation_id, discarded_count in by_conversation.items():
        record_event(
            db,
            conversation_id=conversation_id,
            event_type="drafts_bulk_discarded",
            actor_id=admin_user.id,
            metadata={
                "discarded_count": discarded_count,
                "reason": payload.reason.strip(),
            },
        )
    db.commit()
    return {"discarded_count": len(drafts)}


@router.post(
    "/messages/{message_id}/approve",
    response_model=SmsMessageResponse,
    responses={409: {"description": "Draft state, delivery, or safety conflict."}},
)
async def approve_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Retrieve message, checking tenant boundary
    message = _scoped_message_query(
        db, tenant_id=tenant.id, message_id=message_id
    ).with_for_update().first()

    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")
    if get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=message.conversation_id
    ) is None:
        raise HTTPException(status_code=404, detail="Draft message not found.")

    return _approve_locked_draft(
        db,
        message=message,
        tenant_id=tenant.id,
        actor_id=admin_user.id,
    )


@router.post("/messages/{message_id}/discard", response_model=SmsMessageResponse)
async def discard_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    message = _scoped_message_query(
        db, tenant_id=tenant.id, message_id=message_id
    ).with_for_update().first()

    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")

    if message.status != "draft":
        raise HTTPException(
            status_code=400, detail="Only draft messages can be discarded."
        )

    message.status = "discarded"

    record_event(
        db,
        conversation_id=message.conversation_id,
        event_type="draft_discarded",
        actor_id=admin_user.id,
        metadata={"message_id": message.id},
    )
    db.commit()
    db.refresh(message)

    return message


@router.post("/seed-scenarios", status_code=status.HTTP_409_CONFLICT)
async def reject_production_scenario_seeding(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
):
    """Keep destructive synthetic scenario creation outside production operations."""

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Scenario seeding is disabled on the production operations API; use the isolated SMS simulator.",
    )


@router.get("/{conversation_id}", response_model=SmsConversationResponse)
async def get_conversation(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Mark as read when opening details
    if conv.unread_count > 0:
        conv.unread_count = 0
        db.commit()

    return SmsConversationResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        customer_address=conv.customer_address,
        client_id=conv.client_id,
        client_name=conv.client.name if conv.client else None,
        state=conv.state,
        unread_count=conv.unread_count,
        is_pinned=bool(conv.is_pinned),
        is_blocked=bool(conv.is_blocked),
        ai_enabled=bool(conv.ai_enabled),
        last_activity_at=conv.last_activity_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.post(
    "/{conversation_id}/answer-info-request",
    status_code=status.HTTP_409_CONFLICT,
)
async def reject_direct_knowledge_ingestion(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Require reusable answers to pass through governed curator review."""

    conversation = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Direct knowledge ingestion is disabled; submit a governed curator proposal.",
    )


@router.get("/{conversation_id}/timeline", response_model=List[dict])
async def get_conversation_timeline(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conversation = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return timeline_items(db, conversation)


@router.post(
    "/{conversation_id}/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=SmsInternalNoteResponse,
)
async def add_internal_note(
    conversation_id: DatabaseId,
    payload: SmsInternalNoteCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conversation = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    note = SmsNote(
        conversation_id=conversation.id,
        author_id=admin_user.id,
        text=payload.text.strip(),
    )
    db.add(note)
    db.flush()
    record_event(
        db,
        conversation_id=conversation.id,
        event_type="internal_note_added",
        actor_id=admin_user.id,
        metadata={"note_id": note.id},
    )
    db.commit()
    return {"id": note.id, "created_at": note.created_at}


@router.post(
    "/{conversation_id}/corrections",
    status_code=status.HTTP_201_CREATED,
    response_model=SmsCorrectionResponse,
)
async def record_ai_correction(
    conversation_id: DatabaseId,
    payload: SmsCorrectionCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retain correction evidence without changing reusable AI knowledge."""

    conversation = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    message = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.id == payload.message_id,
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.author_type == "ai",
        )
        .first()
    )
    if message is None:
        raise HTTPException(status_code=404, detail="AI message not found.")
    record_event(
        db,
        conversation_id=conversation.id,
        event_type="ai_correction_recorded",
        actor_id=admin_user.id,
        metadata={
            "message_id": message.id,
            "reason": payload.reason.strip(),
            "corrected_wording": (
                payload.corrected_wording.strip() if payload.corrected_wording else None
            ),
            "contains_dynamic_facts": payload.contains_dynamic_facts,
        },
    )
    db.commit()
    return {"status": "recorded", "knowledge_changed": False}


async def _transition_endpoint(
    *,
    conversation_id: int,
    action: str,
    payload: SmsConversationActionRequest,
    tenant: Tenant,
    admin_user: User,
    db: Session,
) -> SmsConversation:
    conversation = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        transition_conversation(
            db,
            conversation=conversation,
            action=action,
            actor_id=admin_user.id,
            reason=payload.reason,
        )
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post("/{conversation_id}/escalate", response_model=SmsConversationResponse)
async def escalate_conversation(
    conversation_id: DatabaseId,
    payload: SmsConversationActionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await _transition_endpoint(
        conversation_id=conversation_id,
        action="escalate",
        payload=payload,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.post("/{conversation_id}/resolve", response_model=SmsConversationResponse)
async def resolve_conversation(
    conversation_id: DatabaseId,
    payload: SmsConversationActionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await _transition_endpoint(
        conversation_id=conversation_id,
        action="resolve",
        payload=payload,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.post("/{conversation_id}/release", response_model=SmsConversationResponse)
async def release_conversation(
    conversation_id: DatabaseId,
    payload: SmsConversationActionRequest = SmsConversationActionRequest(),
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await _transition_endpoint(
        conversation_id=conversation_id,
        action="release",
        payload=payload,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.post("/{conversation_id}/review-state/clear", response_model=SmsConversationResponse)
async def clear_review_state(
    conversation_id: DatabaseId,
    payload: SmsConversationActionRequest = SmsConversationActionRequest(),
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await _transition_endpoint(
        conversation_id=conversation_id,
        action="clear_review",
        payload=payload,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.post("/{conversation_id}/reopen", response_model=SmsConversationResponse)
async def reopen_conversation(
    conversation_id: DatabaseId,
    payload: SmsConversationActionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await _transition_endpoint(
        conversation_id=conversation_id,
        action="reopen",
        payload=payload,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.patch("/{conversation_id}/controls", response_model=SmsConversationResponse)
async def update_conversation_controls(
    conversation_id: DatabaseId,
    payload: SmsConversationControlsUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update conversation assistant UI controls (ai_enabled, is_pinned, is_blocked)."""
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    resulting_blocked = (
        payload.is_blocked if payload.is_blocked is not None else bool(conv.is_blocked)
    )
    if payload.ai_enabled is True:
        account = get_scoped_account(db, conversation=conv, require_enabled=True)
        if resulting_blocked:
            raise HTTPException(status_code=409, detail="Blocked conversations cannot enable AI.")
        if conv.state in {"needs-review", "escalated", "resolved"}:
            raise HTTPException(
                status_code=409,
                detail="This conversation state must be cleared through its audited workflow before enabling AI.",
            )
        if conv.state != "auto-reply":
            raise HTTPException(
                status_code=409,
                detail="Use the audited release workflow to return this conversation to automation.",
            )
        if account is None or not account.ai_enabled or account.ai_mode not in {"draft", "autopilot"}:
            raise HTTPException(status_code=409, detail="The bound SMS line is not enabled for AI handling.")

    if payload.ai_enabled is not None:
        conv.ai_enabled = payload.ai_enabled
        if not payload.ai_enabled:
            if conv.state == "auto-reply":
                conv.state = "paused"
            cancel_pending_ai_jobs(db, conv.id)

    if payload.is_pinned is not None:
        conv.is_pinned = payload.is_pinned

    if payload.is_blocked is not None:
        conv.is_blocked = payload.is_blocked
        if payload.is_blocked:
            conv.ai_enabled = False
            if conv.state in {"auto-reply", "taken-over"}:
                conv.state = "paused"
            cancel_pending_ai_jobs(db, conv.id)

    record_event(
        db,
        conversation_id=conv.id,
        event_type="controls_updated",
        actor_id=admin_user.id,
        metadata={
            "ai_enabled": conv.ai_enabled,
            "is_pinned": conv.is_pinned,
            "is_blocked": conv.is_blocked,
            "state": conv.state,
        },
    )
    db.commit()
    db.refresh(conv)

    return SmsConversationResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        customer_address=conv.customer_address,
        client_id=conv.client_id,
        client_name=conv.client.name if conv.client else None,
        state=conv.state,
        unread_count=conv.unread_count,
        is_pinned=bool(conv.is_pinned),
        is_blocked=bool(conv.is_blocked),
        ai_enabled=bool(conv.ai_enabled),
        last_activity_at=conv.last_activity_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )

@router.get("/{conversation_id}/messages", response_model=List[SmsMessageResponse])
async def list_conversation_messages(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Verify conversation belongs to tenant
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.conversation_id == conversation_id,
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.provider_id == conv.provider_id,
            SmsMessage.sms_account_id == conv.sms_account_id,
        )
        .order_by(
            SmsMessage.occurred_at.asc(),
            SmsMessage.received_at.asc(),
            SmsMessage.id.asc(),
        )
        .all()
    )

    return messages


@router.post(
    "/{conversation_id}/messages",
    response_model=SmsMessageResponse,
    responses={409: {"description": "Protected state, safety, or idempotency conflict."}},
)
async def send_manual_reply(
    conversation_id: DatabaseId,
    payload: SmsMessageCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        ensure_customer_send_allowed(conv)
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not has_enabled_delivery_target(db, conv):
        raise HTTPException(status_code=409, detail="The delivery channel is unavailable.")

    existing = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.provider_id == conv.provider_id,
            SmsMessage.conversation_id == conv.id,
            SmsMessage.sms_account_id == conv.sms_account_id,
            SmsMessage.client_request_id == payload.client_request_id,
        )
        .first()
    )
    if existing is not None:
        winner = _verified_manual_send_winner(
            db,
            tenant_id=tenant.id,
            provider_id=conv.provider_id,
            conversation_id=conv.id,
            sms_account_id=conv.sms_account_id,
            client_request_id=payload.client_request_id,
            body=payload.body,
        )
        if winner is None:
            raise HTTPException(
                status_code=409,
                detail="The idempotency key is already used for a different message.",
            )
        return winner

    account = get_scoped_account(db, conversation=conv, require_enabled=True)

    try:
        msg = enqueue_outbound_message_transactional(
            db=db,
            account=account,
            conversation=conv,
            body=payload.body,
            author_type="staff",
            author_id=admin_user.id,
            status="queued",
            client_request_id=payload.client_request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="The delivery channel is unavailable.") from exc
    if msg.status == "failed":
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="The message was blocked by the outbound safety policy.",
        )

    cancel_pending_ai_jobs(db, conv.id)

    # 3. Log event
    record_event(
        db,
        conversation_id=conv.id,
        event_type="staff_replied",
        actor_id=admin_user.id,
        metadata={"message_id": msg.id},
    )

    # Manual replies may claim ordinary automated/paused threads, but must not
    # erase stronger review or escalation states.
    if conv.state in {"auto-reply", "paused"}:
        transition_conversation(
            db,
            conversation=conv,
            action="takeover",
            actor_id=admin_user.id,
            reason=None,
        )
    elif conv.state in {"taken-over", "needs-review", "escalated"}:
        conv.ai_enabled = False

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = _verified_manual_send_winner(
            db,
            tenant_id=tenant.id,
            provider_id=conv.provider_id,
            conversation_id=conv.id,
            sms_account_id=conv.sms_account_id,
            client_request_id=payload.client_request_id,
            body=payload.body,
        )
        if winner is None:
            raise HTTPException(
                status_code=409,
                detail="Concurrent manual send could not be verified.",
            ) from exc
        return winner
    db.refresh(msg)
    return msg


@router.post("/{conversation_id}/takeover", response_model=SmsConversationResponse)
async def takeover_conversation(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    try:
        transition_conversation(
            db,
            conversation=conv,
            action="takeover",
            actor_id=admin_user.id,
            reason=None,
        )
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()

    return conv


@router.post("/{conversation_id}/auto-reply", response_model=SmsConversationResponse)
async def restore_auto_reply(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    try:
        transition_conversation(
            db,
            conversation=conv,
            action="release",
            actor_id=admin_user.id,
            reason=None,
        )
    except SmsOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()

    return conv
