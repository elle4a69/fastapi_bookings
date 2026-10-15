"""Platform Owner Support Ticket Review Queue and Codex Launch Bridge.

Provides global administrative endpoints for platform owners to triage, review,
reply to, and launch isolated Codex investigations for tenant support tickets.
Protected strictly via `require_platform_owner`.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

# Ensure Codex Control Centre backend is importable
CODEX_DIR = Path(__file__).resolve().parents[3] / "codex-control-centre"
if str(CODEX_DIR) not in sys.path:
    sys.path.insert(0, str(CODEX_DIR))

import importlib

codex_database = importlib.import_module("backend.database")
codex_models = importlib.import_module("backend.models.codex")
codex_threads_router = importlib.import_module("backend.routers.threads")
codex_turns_router = importlib.import_module("backend.routers.turns")

CodexSessionLocal = codex_database.SessionLocal
CodexProject = codex_models.Project
CodexThread = codex_models.Thread
CodexTurn = codex_models.Turn
ThreadCreate = codex_threads_router.ThreadCreate
create_thread = codex_threads_router.create_thread
TurnStart = codex_turns_router.TurnStart
start_turn = codex_turns_router.start_turn

from ...db.database import get_db
from ...models.support_ticket import SupportTicket, SupportTicketAuditEvent, SupportTicketMessage
from ...models.user import User
from ...services.curation.pii_scrubber import scrub_pii
from ..deps import require_platform_owner

logger = logging.getLogger(__name__)

VALID_STATUSES = {
    "received",
    "under_review",
    "queued_for_codex",
    "in_progress",
    "waiting_on_tenant",
    "resolved",
    "closed",
}

VALID_PRIORITIES = {"low", "normal", "high", "critical"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _calculate_latest_activity(ticket: SupportTicket) -> datetime:
    timestamps = [ticket.updated_at or ticket.created_at]
    if ticket.messages:
        timestamps.extend(m.created_at for m in ticket.messages if m.created_at)
    if ticket.audit_events:
        timestamps.extend(a.created_at for a in ticket.audit_events if a.created_at)
    return max(timestamps)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class SupportTicketMessageAdminResponse(BaseModel):
    """Full message representation including internal notes."""

    id: str
    ticket_id: str
    sender_user_id: Optional[int] = None
    sender_type: str
    visibility: str
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketAuditEventAdminResponse(BaseModel):
    """Full audit log event for support ticket lifecycle tracking."""

    id: str
    ticket_id: str
    actor_user_id: Optional[int] = None
    action: str
    event_data: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketListItemAdminResponse(BaseModel):
    """Summary item for administrative queue listing across all tenants."""

    id: str
    tenant_id: int
    created_by_user_id: int
    title: str
    description: str
    category: str
    status: str
    tenant_status: str
    triage_priority: str
    error_context: Optional[dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    codex_thread_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    message_count: int = 0
    latest_activity_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketDetailAdminResponse(BaseModel):
    """Full ticket detail view including all threaded messages and audit log."""

    id: str
    tenant_id: int
    created_by_user_id: int
    title: str
    description: str
    category: str
    status: str
    tenant_status: str
    triage_priority: str
    error_context: Optional[dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    codex_thread_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    message_count: int = 0
    latest_activity_at: datetime
    messages: list[SupportTicketMessageAdminResponse] = []
    audit_events: list[SupportTicketAuditEventAdminResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SupportTicketStatusUpdate(BaseModel):
    """Payload to update ticket status or triage priority."""

    status: Optional[str] = None
    triage_priority: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{v}'. Allowed statuses: {sorted(VALID_STATUSES)}")
            return normalized
        return v

    @field_validator("triage_priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in VALID_PRIORITIES:
                raise ValueError(f"Invalid triage_priority '{v}'. Allowed: {sorted(VALID_PRIORITIES)}")
            return normalized
        return v


class SupportTicketNoteCreate(BaseModel):
    """Payload to post an internal note or reply."""

    body: Optional[str] = None
    message: Optional[str] = None

    @model_validator(mode="after")
    def validate_content(self) -> "SupportTicketNoteCreate":
        text = (self.body or self.message or "").strip()
        if not text:
            raise ValueError("Message body cannot be empty.")
        self.body = scrub_pii(text)
        return self


class LaunchCodexRequest(BaseModel):
    """Payload to launch a Codex investigation."""

    project_id: Optional[str] = None


class LaunchCodexResponse(BaseModel):
    """Response returned upon launching Codex turn."""

    ticket_id: str
    codex_thread_id: str
    turn_id: int


# ---------------------------------------------------------------------------
# Router Definition
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/admin/support-tickets",
    tags=["Admin Support Tickets"],
    dependencies=[Depends(require_platform_owner)],
)


@router.get("", response_model=list[SupportTicketListItemAdminResponse])
def list_support_tickets_admin(
    status: Optional[str] = Query(None, description="Filter by ticket status"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """List tickets across all tenants with metadata, message counts, and latest activity timestamp."""
    query = db.query(SupportTicket)

    if status:
        query = query.filter(SupportTicket.status == status.strip().lower())
    if tenant_id is not None:
        query = query.filter(SupportTicket.tenant_id == tenant_id)
    if category:
        query = query.filter(SupportTicket.category == category.strip().lower())

    tickets = query.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit).all()

    results: list[SupportTicketListItemAdminResponse] = []
    for t in tickets:
        msg_count = db.query(func.count(SupportTicketMessage.id)).filter(SupportTicketMessage.ticket_id == t.id).scalar() or 0
        latest_act = _calculate_latest_activity(t)
        item = SupportTicketListItemAdminResponse(
            id=t.id,
            tenant_id=t.tenant_id,
            created_by_user_id=t.created_by_user_id,
            title=t.title,
            description=t.description,
            category=t.category,
            status=t.status,
            tenant_status=t.tenant_status,
            triage_priority=t.triage_priority,
            error_context=t.error_context,
            idempotency_key=t.idempotency_key,
            codex_thread_id=t.codex_thread_id,
            created_at=t.created_at,
            updated_at=t.updated_at,
            resolved_at=t.resolved_at,
            message_count=msg_count,
            latest_activity_at=latest_act,
        )
        results.append(item)

    return results


@router.get("/{ticket_id}", response_model=SupportTicketDetailAdminResponse)
def get_support_ticket_admin(
    ticket_id: str,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Full detail view of the ticket, including ALL messages (tenant_visible & internal_only) and audit events."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    messages = (
        db.query(SupportTicketMessage)
        .filter(SupportTicketMessage.ticket_id == ticket.id)
        .order_by(SupportTicketMessage.created_at.asc())
        .all()
    )

    audit_events = (
        db.query(SupportTicketAuditEvent)
        .filter(SupportTicketAuditEvent.ticket_id == ticket.id)
        .order_by(SupportTicketAuditEvent.created_at.asc())
        .all()
    )

    latest_act = _calculate_latest_activity(ticket)

    return SupportTicketDetailAdminResponse(
        id=ticket.id,
        tenant_id=ticket.tenant_id,
        created_by_user_id=ticket.created_by_user_id,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        status=ticket.status,
        tenant_status=ticket.tenant_status,
        triage_priority=ticket.triage_priority,
        error_context=ticket.error_context,
        idempotency_key=ticket.idempotency_key,
        codex_thread_id=ticket.codex_thread_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        message_count=len(messages),
        latest_activity_at=latest_act,
        messages=[SupportTicketMessageAdminResponse.model_validate(m) for m in messages],
        audit_events=[SupportTicketAuditEventAdminResponse.model_validate(a) for a in audit_events],
    )


@router.patch("/{ticket_id}/status", response_model=SupportTicketDetailAdminResponse)
def update_support_ticket_status(
    ticket_id: str,
    payload: SupportTicketStatusUpdate,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Allows platform owner to change ticket status and/or triage priority, recording an audit event."""
    if payload.status is None and payload.triage_priority is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'status' or 'triage_priority' to update.",
        )

    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    old_status = ticket.status
    old_priority = ticket.triage_priority

    if payload.status is not None:
        ticket.status = payload.status
        if payload.status in {"resolved", "closed"}:
            if not ticket.resolved_at:
                ticket.resolved_at = _utc_now()
        else:
            ticket.resolved_at = None

    if payload.triage_priority is not None:
        ticket.triage_priority = payload.triage_priority

    ticket.updated_at = _utc_now()

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=platform_owner.id,
        action="status_changed",
        event_data={
            "old_status": old_status,
            "new_status": ticket.status,
            "old_priority": old_priority,
            "new_priority": ticket.triage_priority,
        },
    )
    db.add(audit_event)
    db.commit()
    db.refresh(ticket)

    return get_support_ticket_admin(ticket_id=ticket.id, platform_owner=platform_owner, db=db)


@router.post("/{ticket_id}/internal-note", response_model=SupportTicketMessageAdminResponse, status_code=status.HTTP_201_CREATED)
def add_internal_note_admin(
    ticket_id: str,
    payload: SupportTicketNoteCreate,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Allows platform owner to post an internal note visible only to administrators."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    msg = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=platform_owner.id,
        sender_type="platform_owner",
        visibility="internal_only",
        body=payload.body,
    )
    db.add(msg)
    ticket.updated_at = _utc_now()
    db.flush()

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=platform_owner.id,
        action="internal_note_added",
        event_data={"message_id": msg.id},
    )
    db.add(audit_event)
    db.commit()
    db.refresh(msg)

    return SupportTicketMessageAdminResponse.model_validate(msg)


@router.post("/{ticket_id}/tenant-reply", response_model=SupportTicketMessageAdminResponse, status_code=status.HTTP_201_CREATED)
def add_tenant_reply_admin(
    ticket_id: str,
    payload: SupportTicketNoteCreate,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Allows platform owner to send a message visible to the tenant."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    msg = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=platform_owner.id,
        sender_type="platform_owner",
        visibility="tenant_visible",
        body=payload.body,
    )
    db.add(msg)
    ticket.updated_at = _utc_now()
    db.flush()

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=platform_owner.id,
        action="tenant_reply_added",
        event_data={"message_id": msg.id, "sender_type": "platform_owner"},
    )
    db.add(audit_event)
    db.commit()
    db.refresh(msg)

    return SupportTicketMessageAdminResponse.model_validate(msg)


@router.post("/{ticket_id}/launch-codex", response_model=LaunchCodexResponse)
async def launch_codex_investigation(
    ticket_id: str,
    payload: LaunchCodexRequest = LaunchCodexRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Platform Owner Review Gate: launches an isolated Codex investigation from an approved ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    clean_title = scrub_pii(ticket.title)
    thread_title = f"Investigation: {clean_title}"

    with CodexSessionLocal() as codex_db:
        # Determine target project
        target_project_id = payload.project_id
        if not target_project_id:
            existing_proj = codex_db.query(CodexProject).first()
            target_project_id = existing_proj.id if existing_proj else "default"

        thread_req = ThreadCreate(
            project_id=target_project_id,
            title=thread_title,
        )
        new_thread = create_thread(thread_req, db=codex_db)
        codex_thread_id = new_thread.id

        # Format sanitized investigation prompt
        prompt_lines = [
            f"Investigation Task: {clean_title}",
            f"Category: {ticket.category}",
            f"Triage Priority: {ticket.triage_priority}",
            f"Description:\n{scrub_pii(ticket.description)}",
        ]
        if ticket.error_context:
            prompt_lines.append(f"Error Context:\n{json.dumps(ticket.error_context, default=str, indent=2)}")
        investigation_prompt = "\n\n".join(prompt_lines)

        turn_req = TurnStart(thread_id=codex_thread_id, prompt=investigation_prompt)
        turn_id = None
        try:
            turn_res = await start_turn(turn_req, background_tasks, db=codex_db)
            if isinstance(turn_res, dict) and "turn_id" in turn_res:
                turn_id = turn_res["turn_id"]
        except Exception as exc:
            logger.warning("Codex turn dispatch encountered exception, checking DB turn: %s", exc)
            last_turn = (
                codex_db.query(CodexTurn)
                .filter(CodexTurn.thread_id == codex_thread_id)
                .order_by(CodexTurn.id.desc())
                .first()
            )
            if last_turn:
                turn_id = last_turn.id
            else:
                fallback_turn = CodexTurn(
                    thread_id=codex_thread_id,
                    turn_number=1,
                    status="active",
                    prompt=investigation_prompt,
                )
                codex_db.add(fallback_turn)
                codex_db.commit()
                codex_db.refresh(fallback_turn)
                turn_id = fallback_turn.id

    # Update ticket in app database
    ticket.codex_thread_id = codex_thread_id
    ticket.status = "queued_for_codex"
    ticket.updated_at = _utc_now()

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=platform_owner.id,
        action="launched_codex",
        event_data={"codex_thread_id": codex_thread_id, "turn_id": turn_id},
    )
    db.add(audit_event)
    db.commit()
    db.refresh(ticket)

    return LaunchCodexResponse(
        ticket_id=ticket.id,
        codex_thread_id=codex_thread_id,
        turn_id=turn_id or 1,
    )
