"""Tenant Support Ticket Intake API.

Provides tenant-scoped ticket intake, threaded conversations, error context
scrubbing, and platform owner administration.
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.user import User
from ...models.tenant import Tenant
from ...models.support_ticket import SupportTicket, SupportTicketMessage, SupportTicketAuditEvent
from ..deps import get_current_tenant_user, require_platform_owner
from ...services.curation.pii_scrubber import scrub_pii

# Tenant-facing friendly status representations
TENANT_STATUS_MAP: dict[str, str] = {
    "received": "Received",
    "under_review": "Under Review",
    "queued_for_codex": "Under Review",
    "in_progress": "Under Review",
    "waiting_on_tenant": "Needs Information",
    "resolved": "Resolved",
    "closed": "Resolved",
}


class ErrorContextSchema(BaseModel):
    """Allowlisted error context attached to a support ticket, PII scrubbed."""

    model_config = ConfigDict(extra="ignore")

    route: Optional[str] = None
    action_attempted: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    client_timestamp: Optional[str] = None

    @field_validator("route", "action_attempted", "error_code", "error_message", mode="before")
    @classmethod
    def scrub_text(cls, v: Any) -> Optional[str]:
        if v is not None and isinstance(v, str):
            return scrub_pii(v)
        return v


class SupportTicketCreate(BaseModel):
    """Request payload to create a new support ticket."""

    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1)
    category: str = Field(default="general", max_length=40)
    error_context: Optional[ErrorContextSchema] = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def scrub_content(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            return scrub_pii(v)
        return v


class SupportTicketMessageResponse(BaseModel):
    """Message turn visible in ticket discussion."""

    id: str
    sender_type: str
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketTenantResponse(BaseModel):
    """Tenant-safe view of a support ticket."""

    id: str
    title: str
    category: str
    tenant_status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    messages: Optional[list[SupportTicketMessageResponse]] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def resolve_tenant_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tenant_status" not in data and "status" in data:
                data["tenant_status"] = TENANT_STATUS_MAP.get(
                    data["status"], (data["status"] or "").replace("_", " ").title()
                )
            return data
        if hasattr(data, "status") and not hasattr(data, "tenant_status"):
            st = getattr(data, "status", "")
            setattr(data, "tenant_status", TENANT_STATUS_MAP.get(st, st.replace("_", " ").title()))
        return data


class SupportTicketReplyCreate(BaseModel):
    """Payload to reply to a support ticket."""

    body: Optional[str] = None
    message: Optional[str] = None

    @model_validator(mode="after")
    def validate_content(self) -> "SupportTicketReplyCreate":
        text = (self.body or self.message or "").strip()
        if not text:
            raise ValueError("Reply body cannot be empty.")
        self.body = scrub_pii(text)
        return self


router = APIRouter(prefix="/api/support/tickets", tags=["Support Tickets"])


@router.post("", response_model=SupportTicketTenantResponse, status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    payload: SupportTicketCreate,
    tenant_user: tuple[Tenant, User] = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """Create a new support ticket bound to the server-verified tenant and user."""
    tenant, current_user = tenant_user
    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None

    if idempotency_key:
        existing = (
            db.query(SupportTicket)
            .filter(
                SupportTicket.tenant_id == tenant.id,
                SupportTicket.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return SupportTicketTenantResponse.model_validate(existing)

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        status="received",
        triage_priority="normal",
        error_context=payload.error_context.model_dump(exclude_none=True) if payload.error_context else None,
        idempotency_key=idempotency_key,
    )
    db.add(ticket)
    db.flush()

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=current_user.id,
        action="created",
        event_data={
            "category": ticket.category,
            "status": ticket.status,
            "has_error_context": payload.error_context is not None,
        },
    )
    db.add(audit_event)
    db.commit()
    db.refresh(ticket)

    return SupportTicketTenantResponse.model_validate(ticket)


@router.get("", response_model=list[SupportTicketTenantResponse])
def list_support_tickets(
    tenant_user: tuple[Tenant, User] = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    """List tickets for the current tenant."""
    tenant, _ = tenant_user
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.tenant_id == tenant.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return [SupportTicketTenantResponse.model_validate(t) for t in tickets]


@router.get("/{ticket_id}", response_model=SupportTicketTenantResponse)
def get_support_ticket(
    ticket_id: str,
    tenant_user: tuple[Tenant, User] = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    """Retrieve ticket details with tenant-visible message history."""
    tenant, _ = tenant_user
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id, SupportTicket.tenant_id == tenant.id)
        .first()
    )
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    # Filter messages where visibility == "tenant_visible" (never exposing internal_only)
    messages = (
        db.query(SupportTicketMessage)
        .filter(
            SupportTicketMessage.ticket_id == ticket.id,
            SupportTicketMessage.visibility == "tenant_visible",
        )
        .order_by(SupportTicketMessage.created_at.asc())
        .all()
    )

    response_data = SupportTicketTenantResponse.model_validate(ticket)
    response_data.messages = [
        SupportTicketMessageResponse.model_validate(m) for m in messages
    ]
    return response_data


@router.post("/{ticket_id}/reply", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_support_ticket(
    ticket_id: str,
    payload: SupportTicketReplyCreate,
    tenant_user: tuple[Tenant, User] = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    """Post a tenant reply to an active support ticket."""
    tenant, current_user = tenant_user
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id, SupportTicket.tenant_id == tenant.id)
        .first()
    )
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )

    msg = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=current_user.id,
        sender_type="tenant_user",
        visibility="tenant_visible",
        body=payload.body,
    )
    db.add(msg)

    if ticket.status == "waiting_on_tenant":
        ticket.status = "under_review"

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=current_user.id,
        action="reply_added",
        event_data={"sender_type": "tenant_user", "message_id": msg.id},
    )
    db.add(audit_event)
    db.commit()
    db.refresh(msg)

    return SupportTicketMessageResponse.model_validate(msg)


@router.post("/{ticket_id}/internal-note", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def add_internal_note(
    ticket_id: str,
    payload: SupportTicketReplyCreate,
    platform_owner: User = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    """Platform owner internal-only note endpoint. Never exposed to tenant."""
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

    audit_event = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=platform_owner.id,
        action="internal_note_added",
        event_data={"message_id": msg.id},
    )
    db.add(audit_event)
    db.commit()
    db.refresh(msg)

    return SupportTicketMessageResponse.model_validate(msg)
