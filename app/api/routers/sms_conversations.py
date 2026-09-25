import hashlib
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob, SmsConversationEvent, SmsAiJob, SmsNote
from ...models.sms_quick_tool import SmsQuickTool
from ...models.curated_memory import KnowledgeProposal
from ...models.learning_event import LearningEvent, compute_text_diff
from ...models.client import Client
from ...services.sms.pii_scrubber import scrub_pii
from ...schemas.learning_event import LearningEventRead, LearningEventSummary
from ...schemas.sms_conversation import (
    SmsConversationResponse,
    SmsConversationControlsUpdate,
    SmsQuickToolItem,
    SmsQuickToolCreate,
    SmsAnswerInfoRequest,
    SmsDraftReviewRequest,
    SmsConversationActionRequest,
    SmsInternalNoteCreate,
    SmsCorrectionCreate,
    SmsBulkDraftDiscardRequest,
    SmsSimulateInboundRequest,
    SmsSeedScenariosRequest,
    SmsSeedScenariosResponse,
)
from ...schemas.sms_message import SmsMessageCreate, SmsMessageResponse
from ...services.sms.outbound_service import enqueue_outbound_message_transactional
from ...services.sms.operations_service import (
    SmsOperationConflict,
    cancel_pending_ai_jobs,
    get_scoped_account,
    get_scoped_conversation,
    record_event,
    scoped_drafts,
    timeline_items,
    transition_conversation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms/conversations", tags=["sms-conversations"])

DEFAULT_QUICK_TOOLS = [
    {
        "slot_index": 0,
        "label": "ADDR",
        "content": "Our address is available on our main profile. Please let us know if you need directions or transit instructions!",
    },
    {
        "slot_index": 1,
        "label": "HOURS",
        "content": "We are open Monday to Friday from 9:00 AM to 5:00 PM, and Saturday 10:00 AM to 3:00 PM.",
    },
    {
        "slot_index": 2,
        "label": "LINK",
        "content": "You can view our available services and manage your appointment online at our booking link.",
    },
    {
        "slot_index": 3,
        "label": "PARKING",
        "content": "Dedicated customer parking is available on-site, with additional street parking nearby.",
    },
    {
        "slot_index": 4,
        "label": "POLICIES",
        "content": "Please notify us at least 24 hours in advance if you need to reschedule or cancel your appointment.",
    },
]


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


@router.get("/jobs", response_model=List[dict])
async def list_outbound_jobs(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Fetch jobs that belong to the accounts of this tenant
    jobs = (
        db.query(SmsOutboundJob)
        .join(SmsAccount, SmsAccount.id == SmsOutboundJob.sms_account_id)
        .filter(SmsAccount.tenant_id == tenant.id)
        .order_by(SmsOutboundJob.created_at.desc())
        .limit(50)
        .all()
    )

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


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_200_OK)
async def retry_outbound_job(
    job_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    job = (
        db.query(SmsOutboundJob)
        .join(SmsMessage, SmsMessage.id == SmsOutboundJob.message_id)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .join(SmsAccount, SmsAccount.id == SmsOutboundJob.sms_account_id)
        .filter(
            SmsOutboundJob.id == job_id,
            SmsAccount.tenant_id == tenant.id,
            SmsAccount.is_enabled.is_(True),
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            SmsMessage.sms_account_id == SmsConversation.sms_account_id,
        )
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Outbound job not found.")
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail="Only failed outbound jobs can be retried.")
    if job.message.conversation.is_blocked:
        raise HTTPException(status_code=409, detail="Blocked conversations cannot retry delivery.")

    job.status = "PENDING"
    job.retry_count = 0
    job.error_log = None

    # Also reset the message status to queued
    message = db.query(SmsMessage).filter(SmsMessage.id == job.message_id).first()
    if message:
        message.status = "queued"

    db.commit()
    return {"status": "success", "detail": "Job marked for retry."}


# --- Draft Messages Review Queue ---


@router.get("/drafts/queue", response_model=List[dict])
async def list_drafts_queue(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all pending AI draft messages across conversations for this tenant."""
    drafts = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.status == "draft",
        )
        .order_by(SmsMessage.occurred_at.desc(), SmsMessage.id.desc())
        .all()
    )

    results = []
    for d in drafts:
        conv = d.conversation
        client_name = conv.client.name if (conv and conv.client) else None
        latest_inbound = (
            db.query(SmsMessage.body)
            .filter(
                SmsMessage.tenant_id == tenant.id,
                SmsMessage.conversation_id == d.conversation_id,
                SmsMessage.direction == "inbound",
                SmsMessage.occurred_at <= d.occurred_at,
            )
            .order_by(SmsMessage.occurred_at.desc(), SmsMessage.id.desc())
            .first()
        )
        inbound_snippet = latest_inbound[0] if latest_inbound else None

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
                "inbound_snippet": inbound_snippet,
            }
        )
    return results


@router.post("/drafts/{draft_id}/review", response_model=SmsMessageResponse)
async def review_draft_message(
    draft_id: DatabaseId,
    payload: SmsDraftReviewRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Review a draft message: approve, discard, or edit."""
    message = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.id == draft_id,
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            SmsMessage.sms_account_id == SmsConversation.sms_account_id,
        )
        .first()
    )

    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")

    original_text = message.body or ""
    new_text = payload.text or payload.body

    if payload.action == "edit":
        if message.status != "draft":
            raise HTTPException(status_code=409, detail="Only pending drafts can be edited.")
        if not new_text:
            raise HTTPException(status_code=422, detail="Edited draft text is required.")

        clean_new = new_text.strip()
        if original_text and clean_new != original_text.strip():
            diff_payload = compute_text_diff(original_text, clean_new)
            learning_event = LearningEvent(
                tenant_id=tenant.id,
                provider_id=message.provider_id,
                conversation_id=str(message.conversation_id),
                message_id=str(message.id),
                event_type="draft_edit",
                source="production_messages",
                original_ai_content=scrub_pii(original_text),
                human_content=scrub_pii(clean_new),
                diff_payload=diff_payload,
                status="pending",
                confidence_score=0.5,
                created_at=datetime.now(timezone.utc),
            )
            db.add(learning_event)

        message.body = clean_new
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

    elif payload.action == "approve":
        if message.status != "draft":
            return message

        now = datetime.now(timezone.utc)
        clean_new = new_text.strip() if new_text else None
        if clean_new and original_text and clean_new != original_text.strip():
            diff_payload = compute_text_diff(original_text, clean_new)
            learning_event = LearningEvent(
                tenant_id=tenant.id,
                provider_id=message.provider_id,
                conversation_id=str(message.conversation_id),
                message_id=str(message.id),
                event_type="draft_edit",
                source="production_messages",
                original_ai_content=scrub_pii(original_text),
                human_content=scrub_pii(clean_new),
                diff_payload=diff_payload,
                status="pending",
                confidence_score=0.5,
                created_at=now,
            )
            db.add(learning_event)
            message.body = clean_new
            message.normalized_body = message.body.lower()
        else:
            learning_event = LearningEvent(
                tenant_id=tenant.id,
                provider_id=message.provider_id,
                conversation_id=str(message.conversation_id),
                message_id=str(message.id),
                event_type="approved_draft",
                source="production_messages",
                original_ai_content=scrub_pii(original_text) if original_text else None,
                human_content=scrub_pii(original_text) if original_text else None,
                status="pending",
                confidence_score=0.2,
                created_at=now,
            )
            db.add(learning_event)

        conversation = message.conversation
        account = get_scoped_account(db, conversation=conversation, require_enabled=True)
        if account is None or conversation.is_blocked:
            raise HTTPException(status_code=409, detail="The bound SMS line cannot send this draft.")

        message.direction = "outbound"
        message.status = "queued"

        existing_job = db.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == message.id).first()
        if existing_job is None:
            db.add(
                SmsOutboundJob(
                    message_id=message.id,
                    sms_account_id=message.sms_account_id,
                    status="PENDING",
                    retry_count=0,
                    created_at=now,
                )
            )

        record_event(
            db,
            conversation_id=message.conversation_id,
            event_type="draft_approved",
            actor_id=admin_user.id,
            metadata={"message_id": message.id},
        )
        db.commit()
        db.refresh(message)
        return message


@router.post("/drafts/bulk/discard")
async def bulk_discard_drafts(
    payload: SmsBulkDraftDiscardRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Explicitly discard selected drafts and audit each affected conversation."""

    drafts = scoped_drafts(db, tenant_id=tenant.id, message_ids=payload.message_ids)
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


@router.post("/messages/{message_id}/approve", response_model=SmsMessageResponse)
async def approve_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Retrieve message, checking tenant boundary
    message = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.id == message_id,
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            SmsMessage.sms_account_id == SmsConversation.sms_account_id,
        )
        .first()
    )

    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")

    if message.status in {"queued", "sending", "sent", "delivered"}:
        # Already approved/processed; return current message (idempotency!)
        return message
    if message.status != "draft":
        raise HTTPException(status_code=409, detail="Only pending drafts can be approved.")

    account = get_scoped_account(db, conversation=message.conversation, require_enabled=True)
    if account is None or message.conversation.is_blocked:
        raise HTTPException(status_code=409, detail="The bound SMS line cannot send this draft.")

    # Mark message as queued for outbound send
    message.direction = "outbound"
    message.status = "queued"

    # Create the SmsOutboundJob record transactionally
    existing_job = db.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == message.id).first()
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

    # Ingest learning event for unchanged draft approval
    now = datetime.now(timezone.utc)
    db.add(
        LearningEvent(
            tenant_id=tenant.id,
            provider_id=message.provider_id,
            conversation_id=str(message.conversation_id),
            message_id=str(message.id),
            event_type="approved_draft",
            source="production_messages",
            original_ai_content=scrub_pii(message.body) if message.body else None,
            human_content=scrub_pii(message.body) if message.body else None,
            status="pending",
            confidence_score=0.2,
            created_at=now,
        )
    )

    # Log approval event
    record_event(
        db,
        conversation_id=message.conversation_id,
        event_type="draft_approved",
        actor_id=admin_user.id,
        metadata={"message_id": message.id},
    )
    db.commit()
    db.refresh(message)

    return message


@router.post("/messages/{message_id}/discard", response_model=SmsMessageResponse)
async def discard_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    message = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.id == message_id,
            SmsMessage.tenant_id == tenant.id,
            SmsConversation.tenant_id == tenant.id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            SmsMessage.sms_account_id == SmsConversation.sms_account_id,
        )
        .first()
    )

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


# --- Quick Tools Endpoints ---


@router.get("/quick-tools", response_model=List[SmsQuickToolItem])
async def get_quick_tools(
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return 5 saved macro buttons for the tenant/user, defaulting to sensible defaults if none saved."""
    tools = (
        db.query(SmsQuickTool)
        .filter(
            SmsQuickTool.tenant_id == tenant.id,
            (SmsQuickTool.user_id == admin_user.id) | (SmsQuickTool.user_id.is_(None)),
        )
        .all()
    )

    # User-specific tools take precedence over tenant-wide tools
    slot_map: dict[int, SmsQuickTool] = {}
    for tool in tools:
        if tool.slot_index not in slot_map or tool.user_id == admin_user.id:
            slot_map[tool.slot_index] = tool

    results: list[SmsQuickToolItem] = []
    for slot_idx in range(5):
        if slot_idx in slot_map:
            t = slot_map[slot_idx]
            results.append(
                SmsQuickToolItem(
                    id=t.id,
                    tenant_id=t.tenant_id,
                    user_id=t.user_id,
                    slot_index=t.slot_index,
                    label=t.label,
                    content=t.content,
                    updated_at=t.updated_at,
                )
            )
        else:
            default_item = DEFAULT_QUICK_TOOLS[slot_idx]
            results.append(
                SmsQuickToolItem(
                    id=None,
                    tenant_id=tenant.id,
                    user_id=admin_user.id,
                    slot_index=slot_idx,
                    label=default_item["label"],
                    content=default_item["content"],
                    updated_at=datetime.now(timezone.utc),
                )
            )

    return results


@router.post("/quick-tools", response_model=SmsQuickToolItem)
async def save_quick_tool(
    payload: SmsQuickToolCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Save or update one of the 5 macro button slots (0-4)."""
    tool = (
        db.query(SmsQuickTool)
        .filter(
            SmsQuickTool.tenant_id == tenant.id,
            SmsQuickTool.slot_index == payload.slot_index,
            SmsQuickTool.user_id == admin_user.id,
        )
        .first()
    )

    now = datetime.now(timezone.utc)
    if tool:
        tool.label = payload.label.strip()[:8]
        tool.content = payload.content.strip()
        tool.user_id = admin_user.id
        tool.updated_at = now
    else:
        tool = SmsQuickTool(
            tenant_id=tenant.id,
            user_id=admin_user.id,
            slot_index=payload.slot_index,
            label=payload.label.strip()[:8],
            content=payload.content.strip(),
            updated_at=now,
        )
        db.add(tool)

    db.commit()
    db.refresh(tool)
    return tool


# --- Simulator Endpoint ---


@router.post("/simulate-inbound")
async def simulate_inbound(
    payload: SmsSimulateInboundRequest,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Simulate an incoming SMS message and optionally execute dialogue turn."""
    account_query = db.query(SmsAccount).filter(
        SmsAccount.tenant_id == tenant.id, SmsAccount.is_enabled == True
    )
    if payload.account_id is not None:
        account = account_query.filter(SmsAccount.id == payload.account_id).first()
    else:
        account = account_query.first()

    if not account:
        raise HTTPException(
            status_code=400,
            detail="No enabled SMS account available for simulation.",
        )

    sender = payload.sender.strip()
    message_text = payload.message.strip()
    if not sender or not message_text:
        raise HTTPException(
            status_code=422, detail="Both sender and message are required."
        )

    # Find or create conversation
    conv = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.sms_account_id == account.id,
            SmsConversation.customer_address == sender,
        )
        .first()
    )

    if not conv:
        matching_client = (
            db.query(Client)
            .filter(Client.tenant_id == tenant.id, Client.phone == sender)
            .first()
        )
        conv = SmsConversation(
            tenant_id=tenant.id,
            provider_id=account.provider_id,
            sms_account_id=account.id,
            customer_address=sender,
            client_id=matching_client.id if matching_client else None,
            state="auto-reply",
            unread_count=0,
            is_pinned=False,
            is_blocked=False,
            ai_enabled=True,
        )
        db.add(conv)
        db.flush()

    now = datetime.now(timezone.utc)
    turn_ref = f"sim_{int(now.timestamp())}"

    inbound_msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body=message_text,
        normalized_body=message_text.lower(),
        direction="inbound",
        author_type="customer",
        status="received",
        provider_message_id=f"sim-prov-{int(now.timestamp())}",
        customer_turn_ref=turn_ref,
        occurred_at=now,
        received_at=now,
    )
    db.add(inbound_msg)
    conv.unread_count += 1
    conv.last_activity_at = now
    db.commit()
    db.refresh(inbound_msg)
    db.refresh(conv)

    turn_result = None
    reply_text = None

    if payload.execute_dialogue_turn and conv.ai_enabled and not conv.is_blocked:
        try:
            from ...engine.dialogue_graph import process_dialogue_turn
            from ...engine.state import AgentState, DialogueTurn
            from langchain_core.messages import HumanMessage
            from ...db.async_session import AsyncSessionLocal

            client_name = conv.client.name if conv.client else None
            initial_state: AgentState = {
                "messages": [HumanMessage(content=message_text)],
                "tenant_id": tenant.id,
                "provider_id": conv.provider_id,
                "customer_name": client_name,
                "conversation_id": conv.id,
                "dialogue_turn": DialogueTurn(),
                "should_escalate": False,
            }
            async with AsyncSessionLocal() as async_db:
                turn_result = await process_dialogue_turn(initial_state, async_db)

            if isinstance(turn_result, dict):
                reply_text = turn_result.get("reply_text")
            else:
                reply_text = getattr(turn_result, "reply_text", None)

            if reply_text:
                status_val = (
                    "queued" if account.ai_mode == "autopilot" else "draft"
                )
                enqueue_outbound_message_transactional(
                    db=db,
                    account=account,
                    conversation=conv,
                    body=reply_text,
                    author_type="ai",
                    status=status_val,
                    parent_message_id=inbound_msg.id,
                    customer_turn_ref=turn_ref,
                )
                db.commit()
        except Exception as e:
            logger.warning(
                "LangGraph simulation turn execution failed (%s); running local rules fallback",
                e,
            )
            try:
                from ...services.sms.ai_orchestrator import run_local_rules_engine

                reply_text = run_local_rules_engine(db, account, conv, message_text)
                if reply_text:
                    status_val = (
                        "queued" if account.ai_mode == "autopilot" else "draft"
                    )
                    enqueue_outbound_message_transactional(
                        db=db,
                        account=account,
                        conversation=conv,
                        body=reply_text,
                        author_type="ai",
                        status=status_val,
                        parent_message_id=inbound_msg.id,
                        customer_turn_ref=turn_ref,
                    )
                    db.commit()
            except Exception as ex:
                logger.warning(
                    "Local rules fallback also encountered an error: %s", ex
                )

    return {
        "status": "success",
        "conversation_id": conv.id,
        "message_id": inbound_msg.id,
        "turn_ref": turn_ref,
        "executed_turn": payload.execute_dialogue_turn,
        "dialogue_reply": (
            turn_result.get("reply_text")
            if isinstance(turn_result, dict)
            else reply_text
        )
        if (turn_result or reply_text)
        else None,
    }


@router.post("/seed-scenarios", response_model=SmsSeedScenariosResponse)
async def seed_test_scenarios(
    payload: Optional[SmsSeedScenariosRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Batch preload 16 structured test scenarios across numbered clients (Client 1..5)
    covering Booking, Pricing, Arrival with chime, Reschedule, Cancellation, Ambiguous, etc.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Scenario seeding is disabled on the production operations API; use the isolated SMS simulator.",
    )

    from datetime import timedelta
    from ...models.sms_arrival import SmsArrivalSession
    from ...models.booking import Booking
    from ...models.service import Service
    from ...models.provider import Provider
    from ...models.location import Location
    from ...services.outbox_service import create_outbox_event
    from ...core.state_machine import BookingStatus

    try:
        from scripts.seed_clean_numbered_data import ensure_database_schema
        ensure_database_schema(db)
    except Exception as e:
        logger.debug("ensure_database_schema note: %s", e)

    clear_existing = payload.clear_existing if payload else False
    account_id = payload.account_id if payload else None

    # 1. Resolve SMS account(s)
    acc_query = db.query(SmsAccount).filter(SmsAccount.tenant_id == tenant.id, SmsAccount.is_enabled == True)
    if account_id:
        primary_account = acc_query.filter(SmsAccount.id == account_id).first()
    else:
        primary_account = acc_query.first()

    if not primary_account:
        prov = db.query(Provider).filter(Provider.tenant_id == tenant.id).first()
        if not prov:
            prov = Provider(tenant_id=tenant.id, name="Provider 1 - Dr. Sarah Bennett", phone="0400000001", active=True)
            db.add(prov)
            db.commit()
            db.refresh(prov)
        primary_account = SmsAccount(
            tenant_id=tenant.id,
            provider_id=prov.id,
            transport_type="simulator",
            display_name="Provider 1 Line",
            sender_address="0400000001",
            is_enabled=True,
            ai_enabled=True,
            ai_mode="draft",
            autoresponder_enabled=True
        )
        db.add(primary_account)
        db.commit()
        db.refresh(primary_account)

    # 2. Ensure Clients 1..5 exist
    client_specs = [
        {"name": "Client 1 - Alice Walker", "phone": "0411000001", "email": "client1@example.com"},
        {"name": "Client 2 - Bob Taylor", "phone": "0411000002", "email": "client2@example.com"},
        {"name": "Client 3 - Charlie Evans", "phone": "0411000003", "email": "client3@example.com"},
        {"name": "Client 4 - Diana Prince", "phone": "0411000004", "email": "client4@example.com"},
        {"name": "Client 5 - Evan Wright", "phone": "0411000005", "email": "client5@example.com"},
    ]
    clients_map = {}
    for spec in client_specs:
        cl = db.query(Client).filter(Client.tenant_id == tenant.id, Client.phone == spec["phone"]).first()
        if not cl:
            cl = Client(
                tenant_id=tenant.id,
                name=spec["name"],
                phone=spec["phone"],
                email=spec["email"],
                active=True
            )
            db.add(cl)
            db.commit()
            db.refresh(cl)
        clients_map[spec["phone"]] = cl

    # 3. Clear existing test conversations if requested
    client_phones = list(clients_map.keys())
    if clear_existing:
        existing_convs = db.query(SmsConversation).filter(
            SmsConversation.tenant_id == tenant.id,
            SmsConversation.customer_address.in_(client_phones)
        ).all()
        conv_ids = [c.id for c in existing_convs]
        if conv_ids:
            db.query(SmsArrivalSession).filter(SmsArrivalSession.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
            db.query(SmsMessage).filter(SmsMessage.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
            db.query(SmsConversation).filter(SmsConversation.id.in_(conv_ids)).delete(synchronize_session=False)
            db.commit()

    # 4. Define structured test scenarios
    now = datetime.now(timezone.utc)
    scenarios = [
        # Client 1
        {
            "client_phone": "0411000001",
            "category": "booking",
            "inbound": "Hi Provider 1, I'd like to book Service 1 - Standard Consultation 60m with Dr. Sarah Bennett for tomorrow at 10:00 AM please.",
            "reply": "Hello Alice! Dr. Sarah Bennett has an opening for Service 1 tomorrow at 10:00 AM. I have reserved this slot for you. Shall I confirm your booking?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 35,
        },
        {
            "client_phone": "0411000001",
            "category": "addons",
            "inbound": "Could I also add Add-on 1 - Extended Care (15m) to my consultation session?",
            "reply": "Certainly Alice! We've noted your request for Add-on 1 (15m extra). Your total session duration will be 75 minutes.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 20,
        },
        {
            "client_phone": "0411000001",
            "category": "arrival",
            "inbound": "I'm here! Just arrived at Location 1 - Main Center for my 10 AM consultation.",
            "reply": "Welcome Alice! We've notified Dr. Sarah Bennett that you are in the waiting area. Please take a seat, she will be right with you.",
            "reply_status": "sent",
            "is_arrival": True,
            "minutes_ago": 5,
        },
        # Client 2
        {
            "client_phone": "0411000002",
            "category": "pricing",
            "inbound": "Hello, what is the price difference between Service 2 - Express Follow-up 30m and Service 3 - Premium Assessment 90m?",
            "reply": "Hi Bob! Service 2 (Express Follow-up, 30m) is $65.00, while Service 3 (Premium Assessment, 90m) is $195.00 and includes comprehensive health diagnostics. Would you like to book one of these?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 50,
        },
        {
            "client_phone": "0411000002",
            "category": "booking",
            "inbound": "Do you have any available slots this Thursday afternoon between 2:00 PM and 4:00 PM?",
            "reply": "Hi Bob, yes! We have an opening with Provider 1 at 2:30 PM this Thursday. Would you like me to book that for you?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 30,
        },
        {
            "client_phone": "0411000002",
            "category": "reschedule",
            "inbound": "Can I reschedule my appointment on Friday to next Tuesday morning at 10:30 AM instead?",
            "reply": "Hi Bob, no problem at all. We have next Tuesday at 10:30 AM open with Dr. Sarah Bennett. I have prepared your rescheduled slot.",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 12,
        },
        # Client 3
        {
            "client_phone": "0411000003",
            "category": "cancellation",
            "inbound": "Please cancel my booking for tomorrow at 2:00 PM, something unexpected came up.",
            "reply": "Hi Charlie, we have received your cancellation request for tomorrow at 2:00 PM. No cancellation fee applies under our 24h policy. Would you like to rebook for later this week?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 45,
        },
        {
            "client_phone": "0411000003",
            "category": "arrival",
            "inbound": "I'm here in the parking lot at Location 1 - Main Center, walking into reception now.",
            "reply": "Hi Charlie! Reception has been notified of your arrival. Please check in at Suite 100.",
            "reply_status": "sent",
            "is_arrival": True,
            "minutes_ago": 8,
        },
        {
            "client_phone": "0411000003",
            "category": "products",
            "inbound": "Do you have Product 1 - Essential Kit and Product 2 - Recovery Balm available for purchase after my session?",
            "reply": "Yes Charlie! Both Product 1 ($45) and Product 2 ($28) are in stock at reception. We can add them to your account invoice.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 3,
        },
        # Client 4
        {
            "client_phone": "0411000004",
            "category": "ambiguous",
            "inbound": "Hi there! I have lower back tension and fatigue. Should I book Service 1 - Standard Consultation or Service 4 - Holistic Wellness 45m?",
            "reply": "Hi Diana! For muscular tension and fatigue, Service 4 - Holistic Wellness 45m with Marcus Vance is ideal. If you require a clinical diagnostic assessment, Service 1 with Dr. Bennett is recommended. Would you prefer holistic care or medical consultation?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 55,
        },
        {
            "client_phone": "0411000004",
            "category": "special_request",
            "inbound": "Can I request a ground floor room and wheelchair accessibility for Location 1?",
            "reply": "Hi Diana, absolutely. Location 1 - Main Center is fully wheelchair accessible with elevator access and dedicated accessible parking right outside.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 28,
        },
        {
            "client_phone": "0411000004",
            "category": "after_hours",
            "inbound": "Are you open on Sundays or do you take evening appointments after 6:00 PM?",
            "reply": "Hi Diana! Our standard hours are Monday to Friday 9:00 AM to 5:00 PM. We also offer Saturday morning sessions from 9:00 AM to 1:00 PM. We are closed Sundays.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 15,
        },
        # Client 5
        {
            "client_phone": "0411000005",
            "category": "location",
            "inbound": "Where is Location 1 - Main Center located and is customer parking free?",
            "reply": "Hi Evan! We are at 100 Main Street, Suite 100. Dedicated customer parking bays are located at the rear of the building and are completely free for clients during appointments.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 60,
        },
        {
            "client_phone": "0411000005",
            "category": "urgent_booking",
            "inbound": "I need urgent Service 5 - Rapid Triage 15m today if there is any cancellation!",
            "reply": "Hi Evan! We had a cancellation for Service 5 at 3:45 PM today with Marcus Vance. Would you like me to reserve this emergency triage slot for you right now?",
            "reply_status": "draft",
            "is_arrival": False,
            "minutes_ago": 25,
        },
        {
            "client_phone": "0411000005",
            "category": "arrival",
            "inbound": "I'm here in the main lobby for my 3:45 PM appointment.",
            "reply": "Thanks Evan, Marcus Vance has been notified. He will greet you in Suite 100 momentarily.",
            "reply_status": "sent",
            "is_arrival": True,
            "minutes_ago": 2,
        },
        {
            "client_phone": "0411000005",
            "category": "feedback",
            "inbound": "Thank you for seeing me so quickly today, the triage advice helped tremendously!",
            "reply": "You are very welcome Evan! Take care, and feel free to message us if you need any follow-up care.",
            "reply_status": "sent",
            "is_arrival": False,
            "minutes_ago": 1,
        },
    ]

    conv_map = {}
    created_drafts_count = 0
    created_arrivals_count = 0

    for sc in scenarios:
        phone = sc["client_phone"]
        cl = clients_map[phone]

        if phone not in conv_map:
            conv = db.query(SmsConversation).filter(
                SmsConversation.tenant_id == tenant.id,
                SmsConversation.sms_account_id == primary_account.id,
                SmsConversation.customer_address == phone
            ).first()
            if not conv:
                conv = SmsConversation(
                    tenant_id=tenant.id,
                    provider_id=primary_account.provider_id,
                    sms_account_id=primary_account.id,
                    customer_address=phone,
                    client_id=cl.id,
                    state="auto-reply",
                    unread_count=0,
                    is_pinned=False,
                    is_blocked=False,
                    ai_enabled=True,
                    last_activity_at=now
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)
            conv_map[phone] = conv
        else:
            conv = conv_map[phone]

        msg_time = now - timedelta(minutes=sc["minutes_ago"])
        turn_ref = f"seed_{int(msg_time.timestamp())}_{sc['category']}"

        # Inbound message
        inbound_msg = SmsMessage(
            tenant_id=tenant.id,
            provider_id=conv.provider_id,
            sms_account_id=primary_account.id,
            conversation_id=conv.id,
            body=sc["inbound"],
            normalized_body=sc["inbound"].lower(),
            direction="inbound",
            author_type="customer",
            status="received",
            provider_message_id=f"seed-in-{int(msg_time.timestamp())}",
            customer_turn_ref=turn_ref,
            occurred_at=msg_time,
            received_at=msg_time,
        )
        db.add(inbound_msg)
        conv.unread_count += 1
        conv.last_activity_at = msg_time
        db.flush()

        # Outbound reply (draft or sent)
        reply_status = sc["reply_status"]
        if reply_status == "draft":
            created_drafts_count += 1

        reply_time = msg_time + timedelta(seconds=15)
        outbound_msg = SmsMessage(
            tenant_id=tenant.id,
            provider_id=conv.provider_id,
            sms_account_id=primary_account.id,
            conversation_id=conv.id,
            body=sc["reply"],
            normalized_body=sc["reply"].lower(),
            direction="outbound" if reply_status == "sent" else "draft",
            author_type="staff" if reply_status == "sent" else "ai",
            status=reply_status,
            provider_message_id=f"seed-out-{int(reply_time.timestamp())}" if reply_status == "sent" else None,
            parent_message_id=inbound_msg.id,
            customer_turn_ref=turn_ref,
            occurred_at=reply_time,
            received_at=reply_time,
        )
        db.add(outbound_msg)
        db.flush()

        # Handle Arrival scenarios
        if sc.get("is_arrival"):
            created_arrivals_count += 1
            booking = db.query(Booking).filter(
                Booking.tenant_id == tenant.id,
                Booking.client_id == cl.id,
                Booking.status == BookingStatus.CONFIRMED
            ).order_by(Booking.start_time.desc()).first()

            if not booking:
                srv = db.query(Service).filter(Service.tenant_id == tenant.id).first()
                loc = db.query(Location).filter(Location.tenant_id == tenant.id).first()
                start_t = now + timedelta(hours=created_arrivals_count, minutes=sc["minutes_ago"])
                booking = Booking(
                    tenant_id=tenant.id,
                    client_id=cl.id,
                    provider_id=conv.provider_id,
                    service_id=srv.id if srv else 1,
                    location_id=loc.id if loc else 1,
                    start_time=start_t,
                    end_time=start_t + timedelta(minutes=60),
                    status=BookingStatus.CONFIRMED,
                    notes=f"Auto-generated for arrival test ({sc['category']})"
                )
                db.add(booking)
                db.flush()

            existing_arr = db.query(SmsArrivalSession).filter(
                SmsArrivalSession.booking_id == booking.id
            ).first()

            if existing_arr:
                existing_arr.conversation_id = conv.id
                existing_arr.arrived_at = msg_time
                existing_arr.acknowledged_at = None
            else:
                new_arr = SmsArrivalSession(
                    booking_id=booking.id,
                    conversation_id=conv.id,
                    token=f"arr-tok-{booking.id}-{int(msg_time.timestamp())}",
                    arrived_at=msg_time,
                    acknowledged_at=None,
                    created_at=msg_time - timedelta(minutes=30)
                )
                db.add(new_arr)

            arr_event = SmsConversationEvent(
                conversation_id=conv.id,
                type="customer_arrived",
                meta={"booking_id": booking.id, "source": "seed_scenarios"}
            )
            db.add(arr_event)

            try:
                create_outbox_event(
                    db,
                    "arrival.alert",
                    {
                        "booking_id": booking.id,
                        "conversation_id": conv.id,
                        "arrived_at": msg_time.isoformat(),
                        "client_name": cl.name,
                    },
                    tenant_id=tenant.id
                )
            except Exception as e:
                logger.warning(f"Could not create arrival alert outbox event: {e}")

    db.commit()

    return SmsSeedScenariosResponse(
        success=True,
        scenarios_count=len(scenarios),
        conversations_count=len(conv_map),
        arrivals_count=created_arrivals_count,
        drafts_count=created_drafts_count,
        message=f"Successfully preloaded {len(scenarios)} test scenarios across {len(conv_map)} numbered clients with {created_arrivals_count} active lobby arrivals and {created_drafts_count} drafts for triage."
    )


@router.get("/learning-events", response_model=List[LearningEventRead])
async def list_learning_events(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    conversation_id: Optional[str] = None,
    provider_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve learning events scoped to the authenticated tenant."""
    query = db.query(LearningEvent).filter(LearningEvent.tenant_id == tenant.id)
    if source:
        query = query.filter(LearningEvent.source == source)
    if event_type:
        query = query.filter(LearningEvent.event_type == event_type)
    if status:
        query = query.filter(LearningEvent.status == status)
    if conversation_id:
        query = query.filter(LearningEvent.conversation_id == conversation_id)
    if provider_id is not None:
        query = query.filter(LearningEvent.provider_id == provider_id)
    return query.order_by(LearningEvent.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/learning-events/summary", response_model=LearningEventSummary)
async def get_learning_events_summary(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve aggregate summary counts for learning events for the tenant."""
    events = db.query(LearningEvent).filter(LearningEvent.tenant_id == tenant.id).all()
    by_source: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    pending = 0
    processed = 0
    ignored = 0
    for ev in events:
        by_source[ev.source] = by_source.get(ev.source, 0) + 1
        by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
        if ev.status == "pending":
            pending += 1
        elif ev.status == "processed":
            processed += 1
        elif ev.status == "ignored":
            ignored += 1
    return LearningEventSummary(
        total_count=len(events),
        pending_count=pending,
        processed_count=processed,
        ignored_count=ignored,
        by_source=by_source,
        by_type=by_type,
    )


# --- Conversation-Specific Endpoints ---


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


@router.post("/{conversation_id}/notes", status_code=status.HTTP_201_CREATED)
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


@router.post("/{conversation_id}/corrections", status_code=status.HTTP_201_CREATED)
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
    now = datetime.now(timezone.utc)
    reason_str = payload.reason.strip()
    corrected_wording = payload.corrected_wording.strip() if payload.corrected_wording else None
    human_content = corrected_wording or reason_str

    # Find prior customer inbound message for learning context
    prior_customer_msg_obj = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "inbound",
            SmsMessage.occurred_at <= message.occurred_at,
        )
        .order_by(SmsMessage.occurred_at.desc())
        .first()
    )
    prior_customer_msg = prior_customer_msg_obj.body if prior_customer_msg_obj else None

    # Ingest KnowledgeProposal so live corrections are fed to the curator queue
    proposal_fingerprint = hashlib.sha256(
        f"production_correction:{tenant.id}:{conversation.id}:{message.id}:{now.isoformat()}".encode("utf-8")
    ).hexdigest()
    scrubbed_query = scrub_pii(prior_customer_msg) if prior_customer_msg else None
    scrubbed_response = scrub_pii(human_content) if human_content else None
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=conversation.provider_id,
        proposal_type="conflict",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="production_correction",
        user_query=scrubbed_query,
        proposed_response=scrubbed_response,
        fingerprint=proposal_fingerprint,
        reason_code=f"production_correction: {reason_str}"[:64],
        confidence_score=1.0,
        contains_dynamic_fact=payload.contains_dynamic_facts,
        requires_review=True,
        evidence_count=1,
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)

    # Ingest unified LearningEvent
    learning_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=conversation.provider_id,
        conversation_id=str(conversation.id),
        message_id=str(message.id),
        event_type="flagged_response",
        source="production_messages",
        customer_message=scrubbed_query,
        original_ai_content=scrub_pii(message.body) if message.body else None,
        human_content=scrubbed_response,
        metadata_payload={
            "reason": reason_str,
            "contains_dynamic_facts": payload.contains_dynamic_facts,
        },
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db.add(learning_event)

    record_event(
        db,
        conversation_id=conversation.id,
        event_type="ai_correction_recorded",
        actor_id=admin_user.id,
        metadata={
            "message_id": message.id,
            "reason": reason_str,
            "corrected_wording": corrected_wording,
            "contains_dynamic_facts": payload.contains_dynamic_facts,
        },
    )
    db.commit()
    return {
        "status": "recorded",
        "knowledge_changed": False,
        "proposal_id": proposal.id,
        "learning_event_id": learning_event.id,
    }


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
    payload: SmsConversationActionRequest = SmsConversationActionRequest(),
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
    payload: SmsConversationActionRequest = SmsConversationActionRequest(),
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


@router.post(
    "/{conversation_id}/answer-info-request",
    status_code=status.HTTP_200_OK,
)
async def answer_info_request(
    conversation_id: DatabaseId,
    payload: SmsAnswerInfoRequest,
    auto_curate: bool = Query(False),
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Staff answer to an info request: safely queue as a pending KnowledgeProposal.

    Live knowledge (CuratedMemory / SmsKnowledgeEntry) is NEVER modified directly,
    ensuring governed curator review before facts enter agent ground truth.
    """
    conv = get_scoped_conversation(
        db, tenant_id=tenant.id, conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    question = (payload.question or "").strip()
    answer = (payload.answer or payload.reply or payload.knowledge or "").strip()
    if not question and not answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either question or answer must be provided.",
        )

    now = datetime.now(timezone.utc)
    fingerprint = hashlib.sha256(
        f"{tenant.id}:{conversation_id}:{question}:{answer}:{now.isoformat()}".encode("utf-8")
    ).hexdigest()

    scrubbed_question = scrub_pii(question) if question else None
    scrubbed_answer = scrub_pii(answer) if answer else None
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        proposal_type="gap",
        status="pending",
        category=payload.category or "faq",
        knowledge_kind="durable_fact",
        authority="conversation_candidate",
        user_query=scrubbed_question,
        proposed_response=scrubbed_answer,
        fingerprint=fingerprint,
        reason_code="staff_info_request_answer",
        confidence_score=1.0,
        contains_dynamic_fact=False,
        requires_review=True,
        evidence_count=1,
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)
    db.flush()

    learning_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        conversation_id=str(conv.id),
        event_type="knowledge_answer",
        source="production_messages",
        customer_message=scrubbed_question,
        human_content=scrubbed_answer,
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db.add(learning_event)
    db.flush()

    curator_decision = None
    should_auto_curate = auto_curate or getattr(payload, "auto_curate", False)
    if should_auto_curate:
        from app.services.knowledge.curator import unified_curator
        curator_decision = unified_curator.process_learning_event(db, learning_event)

    record_event(
        db,
        conversation_id=conv.id,
        event_type="info_request_proposal_created",
        actor_id=admin_user.id,
        metadata={
            "proposal_id": proposal.id,
            "proposal_type": proposal.proposal_type,
            "category": proposal.category,
        },
    )
    db.commit()
    db.refresh(proposal)

    return {
        "status": "success",
        "proposal_id": proposal.id,
        "proposal_type": proposal.proposal_type,
        "learning_event_id": learning_event.id,
        "curated_memory_id": curator_decision.memory_id if curator_decision else None,
        "detail": "Knowledge answered and curated into memory." if curator_decision else "Knowledge proposal created and queued for curator review.",
    }


@router.get("/knowledge/proposals", response_model=List[dict])
async def list_conversation_knowledge_proposals(
    status: Optional[str] = "pending",
    proposal_type: Optional[str] = None,
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from .sms_settings import list_knowledge_proposals
    return await list_knowledge_proposals(
        status=status,
        proposal_type=proposal_type,
        provider_id=provider_id,
        tenant=tenant,
        _admin=_admin,
        db=db,
    )


@router.post("/knowledge/proposals/{proposal_id}/resolve")
async def resolve_conversation_knowledge_proposal(
    proposal_id: DatabaseId,
    payload: dict,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from .sms_settings import resolve_knowledge_proposal, SmsProposalResolveRequest
    req = SmsProposalResolveRequest(**payload)
    return await resolve_knowledge_proposal(
        proposal_id=proposal_id,
        payload=req,
        tenant=tenant,
        admin_user=admin_user,
        db=db,
    )


@router.get("/{conversation_id}/messages", response_model=List[SmsMessageResponse])
async def list_conversation_messages(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Verify conversation belongs to tenant
    conv = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.id == conversation_id,
            SmsConversation.tenant_id == tenant.id,
        )
        .first()
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


@router.post("/{conversation_id}/messages", response_model=SmsMessageResponse)
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
    if conv.is_blocked:
        raise HTTPException(status_code=409, detail="Unblock this contact before sending.")
    if not payload.client_request_id:
        raise HTTPException(status_code=422, detail="client_request_id is required.")

    existing = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.conversation_id == conv.id,
            SmsMessage.sms_account_id == conv.sms_account_id,
            SmsMessage.client_request_id == payload.client_request_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    account = get_scoped_account(db, conversation=conv, require_enabled=True)
    if not account or not account.is_enabled:
        raise HTTPException(
            status_code=400, detail="SMS account is disabled or missing."
        )

    # 1. Enqueue message
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
    if msg.status == "failed":
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="The message was blocked by the outbound safety policy.",
        )

    # 2. Cancel pending AI jobs (since staff took action, current turn is resolved)
    db.query(SmsAiJob).filter(
        SmsAiJob.conversation_id == conv.id, SmsAiJob.status == "PENDING"
    ).update({"status": "CANCELLED"})

    # 3. Log event
    record_event(
        db,
        conversation_id=conv.id,
        event_type="staff_replied",
        actor_id=admin_user.id,
        metadata={"message_id": msg.id},
    )

    # 4. Takeover automatically if not already
    if conv.state != "taken-over":
        transition_conversation(
            db,
            conversation=conv,
            action="takeover",
            actor_id=admin_user.id,
            reason=None,
        )
    else:
        conv.ai_enabled = False

    db.commit()
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

    transition_conversation(
        db,
        conversation=conv,
        action="takeover",
        actor_id=admin_user.id,
        reason=None,
    )
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
