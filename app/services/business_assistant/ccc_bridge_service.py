"""Codex Control Centre (CCC) Autonomous Agent Bridge Service.

Bridges authenticated Staff SupportTicket lifecycles with local Codex Control Centre
agents for automated code remediation, milestone tracking, real-time steering, and
UI verification receipts.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from ...core.config import settings
from ...db.database import SessionLocal
from ...models.business_assistant import (
    BusinessAssistantMessage,
    SupportTicket,
    SupportTicketEvent,
)

logger = logging.getLogger(__name__)


class CCCBridgeService:
    """Autonomous bridge between SupportTicket persistence and Codex Control Centre."""

    def __init__(
        self,
        ccc_url: Optional[str] = None,
        ccc_token: Optional[str] = None,
    ) -> None:
        self.ccc_url = (ccc_url or settings.CODEX_CONTROL_CENTRE_URL).rstrip("/")
        self.ccc_token = ccc_token or settings.CODEX_CONTROL_CENTRE_TOKEN
        self._active_listeners: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.ccc_token:
            headers["Authorization"] = f"Bearer {self.ccc_token}"
        return headers

    async def dispatch_ticket(self, ticket_id: int, db: Session) -> Dict[str, Any]:
        """Dispatch a ticket in awaiting_engineering to CCC in an isolated worktree."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            raise LookupError(f"Ticket #{ticket_id} not found")

        # If already dispatched and active, return current dispatch state
        if ticket.coding_task_id and ticket.status == "in_progress":
            self.ensure_sse_listener(
                thread_id=ticket.coding_task_id,
                ticket_id=ticket.id,
                tenant_id=ticket.tenant_id,
                conversation_id=ticket.conversation_id,
            )
            return {
                "status": "in_progress",
                "ticket_id": ticket.id,
                "thread_id": ticket.coding_task_id,
                "already_dispatched": True,
            }

        thread_id = str(ticket.id)
        # 1. Create thread in CCC
        create_thread_url = f"{self.ccc_url}/codex/threads"
        thread_payload = {
            "project_id": "fastapi-bookings",
            "title": f"Remediate Ticket #{ticket.id}: {ticket.title}",
            "id": thread_id,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.post(
                    create_thread_url,
                    json=thread_payload,
                    headers=self._headers(),
                )
                if res.status_code < 400:
                    data = res.json()
                    thread_id = str(data.get("id") or thread_id)
                else:
                    logger.warning(
                        "CCC thread creation returned %s: %s; falling back to thread_id %s",
                        res.status_code,
                        res.text,
                        thread_id,
                    )
            except Exception as exc:
                logger.error("Failed to connect to CCC /codex/threads: %s", exc)
                # Keep thread_id as fallback

        # 2. Build detailed remediation prompt
        prompt_lines = [
            f"# Autonomous Remediation Task: Support Ticket #{ticket.id}",
            f"**Title**: {ticket.title}",
            f"**Category**: {ticket.category} | **Severity**: {ticket.severity}",
            f"**Target Sandbox**: worktrees/wt-{ticket.id}",
            "",
            "## Description & Observed Behaviour",
            ticket.description,
        ]
        if ticket.observed_behaviour:
            prompt_lines.extend(["", "### Observed Behaviour", ticket.observed_behaviour])
        if ticket.affected_product_area:
            prompt_lines.extend(["", "### Affected Area", ticket.affected_product_area])
        if ticket.user_impact:
            prompt_lines.extend(["", "### User Impact", ticket.user_impact])
        if ticket.acceptance_criteria:
            prompt_lines.extend(["", "### Acceptance Criteria", ticket.acceptance_criteria])

        prompt_lines.extend([
            "",
            "## Instructions for Codex Engineer",
            "1. Inspect the codebase strictly in your isolated worktree.",
            "2. Write tests replicating the defect and implement the minimal fix.",
            "3. Run automated tests and report changes once verified.",
        ])
        prompt = "\n".join(prompt_lines)

        # 3. Start remediation turn in CCC
        start_turn_url = f"{self.ccc_url}/codex/turns/start"
        turn_payload = {
            "thread_id": thread_id,
            "prompt": prompt,
        }
        turn_id = None

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                res = await client.post(
                    start_turn_url,
                    json=turn_payload,
                    headers=self._headers(),
                )
                if res.status_code < 400:
                    turn_data = res.json()
                    turn_id = turn_data.get("turn_id")
                else:
                    logger.warning(
                        "CCC /codex/turns/start returned %s: %s",
                        res.status_code,
                        res.text,
                    )
            except Exception as exc:
                logger.error("Failed to start turn in CCC: %s", exc)

        # 4. Update ticket and persist milestone event
        ticket.status = "in_progress"
        ticket.coding_task_id = thread_id
        ticket.updated_at = datetime.now(timezone.utc)

        event = SupportTicketEvent(
            ticket_id=ticket.id,
            tenant_id=ticket.tenant_id,
            actor_user_id=ticket.user_id,
            event_type="dispatched_to_ccc",
            safe_metadata={
                "thread_id": thread_id,
                "turn_id": turn_id,
                "workspace": f"worktrees/wt-{ticket.id}",
                "status": "in_progress",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(event)
        db.commit()
        db.refresh(ticket)

        # 5. Spin up background SSE listener for milestones & clarification dispatch
        self.ensure_sse_listener(
            thread_id=thread_id,
            ticket_id=ticket.id,
            tenant_id=ticket.tenant_id,
            conversation_id=ticket.conversation_id,
        )

        return {
            "status": "in_progress",
            "ticket_id": ticket.id,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "workspace": f"worktrees/wt-{ticket.id}",
        }

    async def steer_ticket(self, ticket_id: int, instruction: str, db: Session) -> Dict[str, Any]:
        """Forward steering guidance or clarification reply from staff/Grok to CCC."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            raise LookupError(f"Ticket #{ticket_id} not found")
        if not ticket.coding_task_id:
            raise ValueError(f"Ticket #{ticket_id} has not been dispatched to Codex Control Centre yet.")

        steer_url = f"{self.ccc_url}/codex/turns/steer"
        payload = {
            "thread_id": ticket.coding_task_id,
            "instruction": instruction,
            "turn_id": 0,
        }

        ccc_res_data: Dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.post(steer_url, json=payload, headers=self._headers())
                if res.status_code >= 400:
                    logger.warning("CCC steer endpoint returned %s: %s", res.status_code, res.text)
                else:
                    ccc_res_data = res.json()
            except Exception as exc:
                logger.error("Failed to connect to CCC /codex/turns/steer: %s", exc)

        # Record steering milestone
        event = SupportTicketEvent(
            ticket_id=ticket.id,
            tenant_id=ticket.tenant_id,
            actor_user_id=ticket.user_id,
            event_type="engineering_steer_sent",
            safe_metadata={
                "instruction": instruction,
                "thread_id": ticket.coding_task_id,
                "ccc_response": ccc_res_data,
                "steered_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(event)
        ticket.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(ticket)

        return {
            "status": "steered",
            "ticket_id": ticket.id,
            "thread_id": ticket.coding_task_id,
            "instruction": instruction,
        }

    def record_ui_verify_receipt(
        self,
        ticket_id: int,
        receipt_data: Dict[str, Any],
        db: Session,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a UI verification receipt and optionally resolve ticket."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            raise LookupError(f"Ticket #{ticket_id} not found")

        event = SupportTicketEvent(
            ticket_id=ticket.id,
            tenant_id=ticket.tenant_id,
            actor_user_id=actor_user_id or ticket.user_id,
            event_type="ui_verification_receipt",
            safe_metadata={
                **receipt_data,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(event)

        # Update resolution state if verified
        is_verified = (
            receipt_data.get("verified") is True
            or receipt_data.get("receipt_state") in ("saved", "verified", "approved")
            or receipt_data.get("status") in ("success", "approved", "verified")
        )
        if is_verified:
            ticket.status = "resolved"
            summary = (
                receipt_data.get("resolution_summary")
                or receipt_data.get("notes")
                or receipt_data.get("summary")
                or "UI state verified and approved by staff."
            )
            ticket.resolution_summary = str(summary)
            ticket.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ticket)

        return {
            "status": ticket.status,
            "ticket": ticket,
            "event": event,
        }

    def ensure_sse_listener(
        self,
        thread_id: str,
        ticket_id: int,
        tenant_id: int,
        conversation_id: Optional[int],
    ) -> None:
        """Start background SSE listener task for thread milestones if not already running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if thread_id in self._active_listeners:
            task = self._active_listeners[thread_id]
            if not task.done():
                return

        task = loop.create_task(
            self._sse_stream_listener(thread_id, ticket_id, tenant_id, conversation_id)
        )
        self._active_listeners[thread_id] = task

    async def _sse_stream_listener(
        self,
        thread_id: str,
        ticket_id: int,
        tenant_id: int,
        conversation_id: Optional[int],
    ) -> None:
        """Connects to CCC SSE stream and records milestones and clarifications in DB."""
        sse_url = f"{self.ccc_url}/codex/events/fastapi-bookings/{thread_id}?token={self.ccc_token}"
        headers = {"Accept": "text/event-stream"}
        if self.ccc_token:
            headers["Authorization"] = f"Bearer {self.ccc_token}"

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", sse_url, headers=headers) as response:
                    if response.status_code >= 400:
                        logger.warning("SSE connection to %s failed with %s", sse_url, response.status_code)
                        return

                    current_event_type = "message"
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("event:"):
                            current_event_type = line[6:].strip()
                            continue

                        if line.startswith("data:"):
                            raw_data = line[5:].strip()
                            try:
                                payload = json.loads(raw_data)
                            except Exception:
                                payload = {"raw": raw_data}

                            self._process_sse_milestone(
                                current_event_type=current_event_type,
                                payload=payload,
                                ticket_id=ticket_id,
                                tenant_id=tenant_id,
                                conversation_id=conversation_id,
                                thread_id=thread_id,
                            )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("SSE stream for thread %s disconnected: %s", thread_id, exc)

    def _process_sse_milestone(
        self,
        current_event_type: str,
        payload: Dict[str, Any],
        ticket_id: int,
        tenant_id: int,
        conversation_id: Optional[int],
        thread_id: str,
        db: Optional[Session] = None,
    ) -> None:
        """Helper to record milestone events and dispatch clarification to active staff session."""
        if db is not None:
            self._handle_milestone_db(
                db=db,
                current_event_type=current_event_type,
                payload=payload,
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                thread_id=thread_id,
            )
            return

        try:
            with SessionLocal() as session:
                self._handle_milestone_db(
                    db=session,
                    current_event_type=current_event_type,
                    payload=payload,
                    ticket_id=ticket_id,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    thread_id=thread_id,
                )
        except Exception as exc:
            logger.error("Error processing SSE milestone for ticket %s: %s", ticket_id, exc)

    def _handle_milestone_db(
        self,
        db: Session,
        current_event_type: str,
        payload: Dict[str, Any],
        ticket_id: int,
        tenant_id: int,
        conversation_id: Optional[int],
        thread_id: str,
    ) -> None:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return

        event_type = current_event_type
        if current_event_type == "turn_started":
            event_type = "engineering_turn_started"
        elif current_event_type in ("command", "command_execution"):
            event_type = "command_executed"
        elif current_event_type in ("file_change", "file_modified", "fileModified"):
            event_type = "file_modified"
        elif current_event_type in ("approval_requested", "approval.requested"):
            event_type = "clarification_requested"
        elif current_event_type == "turn_completed":
            event_type = "engineering_turn_completed"
            status = str(payload.get("status") or "").lower()
            if status in ("completed", "success"):
                ticket.status = "awaiting_verification"
                ticket.updated_at = datetime.now(timezone.utc)
        elif current_event_type == "error":
            event_type = "engineering_error"

        ev = SupportTicketEvent(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            actor_user_id=ticket.user_id,
            event_type=event_type,
            safe_metadata=payload,
        )
        db.add(ev)

        # Dispatch clarification / steer request to Business Assistant session
        if event_type == "clarification_requested" and conversation_id:
            prompt_text = (
                payload.get("consequence")
                or payload.get("command")
                or payload.get("message")
                or "Clarification requested by autonomous coding worker."
            )
            assistant_msg = BusinessAssistantMessage(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=ticket.user_id,
                role="business_assistant",
                content=f"[Codex Autonomous Engineer Clarification on Ticket #{ticket_id}]: {prompt_text}",
                channel="text",
            )
            db.add(assistant_msg)

        db.commit()

    async def listen_and_dispatch_awaiting_tickets(self, db: Session) -> List[Dict[str, Any]]:
        """Scans for tickets in awaiting_engineering without active dispatch and launches them."""
        awaiting = (
            db.query(SupportTicket)
            .filter(
                SupportTicket.status == "awaiting_engineering",
                SupportTicket.coding_task_id.is_(None),
            )
            .all()
        )
        results = []
        for t in awaiting:
            try:
                res = await self.dispatch_ticket(t.id, db)
                results.append(res)
            except Exception as exc:
                logger.error("Auto-dispatch failed for ticket %s: %s", t.id, exc)
        return results


ccc_bridge_service = CCCBridgeService()
