"""Tenant- and user-scoped persistence operations for internal staff conversations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_

from sqlalchemy.orm import Session

from ...models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantMemory,
    BusinessAssistantMessage,
    BusinessAssistantOnboardingProgress,
    BusinessAssistantToolRun,
    SupportTicket,
    SupportTicketDeduplicationClaim,
    SupportTicketEvent,
)
from ...models.curated_memory import CuratedMemory, KnowledgeProposal


class BusinessAssistantRepository:
    """Repository that always requires authoritative tenant and user scope."""

    def __init__(self, db: Session, tenant_id: int, user_id: int) -> None:
        if tenant_id <= 0 or user_id <= 0:
            raise ValueError("A positive tenant and user identifier are required.")
        self._db = db
        self._tenant_id = tenant_id
        self._user_id = user_id

    def create_conversation(
        self,
        *,
        title: Optional[str] = None,
        request_key: Optional[str] = None,
        payload_hash: Optional[str] = None,
    ) -> BusinessAssistantConversation:
        """Create one scoped conversation, reusing an existing request-key result."""
        if request_key:
            existing = (
                self._db.query(BusinessAssistantConversation)
                .filter(
                    BusinessAssistantConversation.tenant_id == self._tenant_id,
                    BusinessAssistantConversation.user_id == self._user_id,
                    BusinessAssistantConversation.creation_request_key == request_key,
                )
                .first()
            )
            if existing:
                return existing

        conversation = BusinessAssistantConversation(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            title=title,
            creation_request_key=request_key,
            creation_payload_hash=payload_hash,
        )
        self._db.add(conversation)
        self._db.flush()
        return conversation

    def list_conversations(self) -> list[BusinessAssistantConversation]:
        """Return only conversations owned by the authoritative user in the tenant."""
        return (
            self._db.query(BusinessAssistantConversation)
            .filter(
                BusinessAssistantConversation.tenant_id == self._tenant_id,
                BusinessAssistantConversation.user_id == self._user_id,
            )
            .order_by(BusinessAssistantConversation.updated_at.desc(), BusinessAssistantConversation.id.desc())
            .all()
        )

    def get_conversation(self, conversation_id: int) -> Optional[BusinessAssistantConversation]:
        """Find a conversation only when it belongs to the current tenant and user."""
        return (
            self._db.query(BusinessAssistantConversation)
            .filter(
                BusinessAssistantConversation.id == conversation_id,
                BusinessAssistantConversation.tenant_id == self._tenant_id,
                BusinessAssistantConversation.user_id == self._user_id,
            )
            .first()
        )

    def get_conversation_by_creation_request_key(
        self,
        request_key: str,
    ) -> Optional[BusinessAssistantConversation]:
        """Find a conversation creation retry only in the authoritative scope."""
        return (
            self._db.query(BusinessAssistantConversation)
            .filter(
                BusinessAssistantConversation.tenant_id == self._tenant_id,
                BusinessAssistantConversation.user_id == self._user_id,
                BusinessAssistantConversation.creation_request_key == request_key,
            )
            .first()
        )

    def append_message(
        self,
        *,
        conversation: BusinessAssistantConversation,
        role: str,
        content: str,
        request_key: Optional[str] = None,
        request_payload_hash: Optional[str] = None,
        channel: str = "text",
        realtime_session_id: Optional[str] = None,
        realtime_item_id: Optional[str] = None,
        in_reply_to_message_id: Optional[int] = None,
        generation_status: Optional[str] = None,
        generation_started_at: Optional[datetime] = None,
    ) -> BusinessAssistantMessage:
        """Append a message only after proving the conversation belongs to this scope."""
        if conversation.tenant_id != self._tenant_id or conversation.user_id != self._user_id:
            raise ValueError("Conversation is outside the authenticated scope.")
        message = BusinessAssistantMessage(
            conversation_id=conversation.id,
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            role=role,
            content=content,
            request_key=request_key,
            request_payload_hash=request_payload_hash,
            channel=channel,
            realtime_session_id=realtime_session_id,
            realtime_item_id=realtime_item_id,
            in_reply_to_message_id=in_reply_to_message_id,
            generation_status=generation_status,
            generation_started_at=generation_started_at,
        )
        self._db.add(message)
        self._db.flush()
        return message

    def get_message_by_request_key(
        self,
        *,
        conversation_id: int,
        request_key: str,
    ) -> Optional[BusinessAssistantMessage]:
        """Find an idempotent user turn only within the authoritative scope."""
        return (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.conversation_id == conversation_id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
                BusinessAssistantMessage.user_id == self._user_id,
                BusinessAssistantMessage.request_key == request_key,
            )
            .first()
        )

    def get_message(self, message_id: int) -> Optional[BusinessAssistantMessage]:
        """Find a message only within the authoritative tenant and user scope."""
        return (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.id == message_id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
                BusinessAssistantMessage.user_id == self._user_id,
            )
            .first()
        )

    def get_reply_to_message(self, message_id: int) -> Optional[BusinessAssistantMessage]:
        """Return a generated reply only when it belongs to this tenant and user scope."""
        return (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.in_reply_to_message_id == message_id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
                BusinessAssistantMessage.user_id == self._user_id,
                BusinessAssistantMessage.role == "business_assistant",
            )
            .first()
        )

    def get_message_by_realtime_item(
        self,
        *,
        conversation_id: int,
        session_id: str,
        item_id: str,
    ) -> Optional[BusinessAssistantMessage]:
        """Find one voice transcript event inside the authorised conversation scope."""
        return (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.conversation_id == conversation_id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
                BusinessAssistantMessage.user_id == self._user_id,
                BusinessAssistantMessage.realtime_session_id == session_id,
                BusinessAssistantMessage.realtime_item_id == item_id,
            )
            .first()
        )

    def list_messages(
        self,
        *,
        conversation: BusinessAssistantConversation,
        limit: int,
    ) -> list[BusinessAssistantMessage]:
        """Return chronological history from an authorised conversation only."""
        if conversation.tenant_id != self._tenant_id or conversation.user_id != self._user_id:
            raise ValueError("Conversation is outside the authenticated scope.")
        newest_first = (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.conversation_id == conversation.id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
            )
            .order_by(BusinessAssistantMessage.created_at.desc(), BusinessAssistantMessage.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(newest_first))

    def claim_retryable_turn(self, message_id: int) -> bool:
        """Atomically claim a failed user turn before it can call the text provider again."""
        claimed = (
            self._db.query(BusinessAssistantMessage)
            .filter(
                BusinessAssistantMessage.id == message_id,
                BusinessAssistantMessage.tenant_id == self._tenant_id,
                BusinessAssistantMessage.user_id == self._user_id,
                BusinessAssistantMessage.role == "user",
                or_(
                    BusinessAssistantMessage.generation_status == "failed",
                    BusinessAssistantMessage.generation_status.is_(None),
                ),
            )
            .update(
                {
                    BusinessAssistantMessage.generation_status: "running",
                    BusinessAssistantMessage.generation_started_at: datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )
        if claimed:
            self._db.commit()
            return True
        self._db.rollback()
        return False

    def mark_turn_failed(self, message: BusinessAssistantMessage) -> None:
        """Persist an explicit retryable failure without storing provider error details."""
        if message.tenant_id != self._tenant_id or message.user_id != self._user_id:
            raise ValueError("Message is outside the authenticated scope.")
        message.generation_status = "failed"
        self._db.commit()
        self._db.refresh(message)

    def mark_turn_completed(self, message: BusinessAssistantMessage) -> None:
        """Record successful reply persistence after the reply has been appended."""
        if message.tenant_id != self._tenant_id or message.user_id != self._user_id:
            raise ValueError("Message is outside the authenticated scope.")
        message.generation_status = "completed"

    def record_tool_run(
        self,
        *,
        conversation: BusinessAssistantConversation,
        message: Optional[BusinessAssistantMessage] = None,
        tool_name: str,
        status: str,
        duration_ms: int,
    ) -> None:
        """Append structural tool telemetry without storing arguments or result content."""
        if conversation.tenant_id != self._tenant_id or (message and message.tenant_id != self._tenant_id):
            raise ValueError("Tool run is outside the authenticated scope.")
        self._db.add(
            BusinessAssistantToolRun(
                tenant_id=self._tenant_id,
                user_id=self._user_id,
                conversation_id=conversation.id,
                message_id=message.id if message else None,
                tool_name=tool_name[:96],
                status=status[:32],
                duration_ms=max(0, duration_ms),
                safe_metadata={},
            )
        )
        self._db.flush()

    def get_onboarding_progress(self) -> Optional[BusinessAssistantOnboardingProgress]:
        """Read personal onboarding progress only in the authoritative scope."""
        return (
            self._db.query(BusinessAssistantOnboardingProgress)
            .filter(
                BusinessAssistantOnboardingProgress.tenant_id == self._tenant_id,
                BusinessAssistantOnboardingProgress.user_id == self._user_id,
            )
            .first()
        )

    def get_or_create_onboarding_progress(self) -> BusinessAssistantOnboardingProgress:
        """Create an empty personal progress record only when one is absent."""
        progress = self.get_onboarding_progress()
        if progress:
            return progress
        progress = BusinessAssistantOnboardingProgress(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            completed_steps=[],
        )
        self._db.add(progress)
        self._db.flush()
        return progress

    def create_ticket(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        deduplication_key: str,
        request_key: Optional[str] = None,
        request_payload_hash: Optional[str] = None,
        conversation: Optional[BusinessAssistantConversation] = None,
    ) -> SupportTicket:
        """Create a no-dispatch ticket and its initial append-only lifecycle event."""
        if conversation and (
            conversation.tenant_id != self._tenant_id or conversation.user_id != self._user_id
        ):
            raise ValueError("Conversation is outside the authenticated scope.")
        ticket = SupportTicket(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            conversation_id=conversation.id if conversation else None,
            category=category,
            severity=severity,
            title=title,
            description=description,
            request_key=request_key,
            request_payload_hash=request_payload_hash,
            deduplication_key=deduplication_key,
        )
        self._db.add(ticket)
        self._db.flush()
        self._db.add(
            SupportTicketDeduplicationClaim(
                ticket_id=ticket.id,
                tenant_id=self._tenant_id,
                user_id=self._user_id,
                deduplication_key=deduplication_key,
            )
        )
        self._db.flush()
        self._db.add(
            SupportTicketEvent(
                ticket_id=ticket.id,
                tenant_id=self._tenant_id,
                actor_user_id=self._user_id,
                event_type="created",
                safe_metadata={"status": ticket.status},
            )
        )
        self._db.flush()
        return ticket

    def get_ticket(self, ticket_id: int) -> Optional[SupportTicket]:
        """Find one ticket only when it belongs to the authenticated user and tenant."""
        return (
            self._db.query(SupportTicket)
            .filter(
                SupportTicket.id == ticket_id,
                SupportTicket.tenant_id == self._tenant_id,
                SupportTicket.user_id == self._user_id,
            )
            .first()
        )

    def list_tickets(self, *, limit: int) -> list[SupportTicket]:
        """Return only ticket summaries visible to the authenticated ticket creator."""
        return (
            self._db.query(SupportTicket)
            .filter(
                SupportTicket.tenant_id == self._tenant_id,
                SupportTicket.user_id == self._user_id,
            )
            .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
            .limit(limit)
            .all()
        )

    def get_ticket_by_request_key(self, request_key: str) -> Optional[SupportTicket]:
        """Find a prior idempotent ticket creation in the current scope."""
        return (
            self._db.query(SupportTicket)
            .filter(
                SupportTicket.tenant_id == self._tenant_id,
                SupportTicket.user_id == self._user_id,
                SupportTicket.request_key == request_key,
            )
            .first()
        )

    def get_active_ticket_by_deduplication_key(self, deduplication_key: str) -> Optional[SupportTicket]:
        """Find an active duplicate without revealing tickets outside this user scope."""
        return (
            self._db.query(SupportTicket)
            .join(
                SupportTicketDeduplicationClaim,
                SupportTicketDeduplicationClaim.ticket_id == SupportTicket.id,
            )
            .filter(
                SupportTicket.tenant_id == self._tenant_id,
                SupportTicket.user_id == self._user_id,
                SupportTicketDeduplicationClaim.tenant_id == self._tenant_id,
                SupportTicketDeduplicationClaim.user_id == self._user_id,
                SupportTicketDeduplicationClaim.deduplication_key == deduplication_key,
            )
            .first()
        )

    def list_ticket_events(self, ticket_id: int) -> list[SupportTicketEvent]:
        """Read events only through the ticket's tenant and initiating-user boundary."""
        return (
            self._db.query(SupportTicketEvent)
            .join(SupportTicket, SupportTicketEvent.ticket_id == SupportTicket.id)
            .filter(
                SupportTicketEvent.ticket_id == ticket_id,
                SupportTicketEvent.tenant_id == self._tenant_id,
                SupportTicket.tenant_id == self._tenant_id,
                SupportTicket.user_id == self._user_id,
            )
            .order_by(SupportTicketEvent.created_at.asc(), SupportTicketEvent.id.asc())
            .all()
        )

    def create_memory_draft(
        self,
        *,
        memory_key: str,
        content: str,
        interpretation: Optional[str] = None,
        category: str = "policy",
        curator_item_id: Optional[int] = None,
        payload_hash: Optional[str] = None,
        provenance: Optional[dict] = None,
    ) -> BusinessAssistantMemory:
        """Create a new drafted business rule in authoritative tenant and user scope."""
        memory = BusinessAssistantMemory(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            memory_key=memory_key,
            content=content,
            interpretation=interpretation,
            category=category,
            version=1,
            payload_hash=payload_hash,
            curator_item_id=curator_item_id,
            status="draft",
            provenance=provenance or {"created_by_user_id": self._user_id, "source": "staff_draft"},
        )
        self._db.add(memory)
        self._db.flush()
        return memory

    def get_memory_by_key(self, memory_key: str) -> Optional[BusinessAssistantMemory]:
        """Retrieve a business rule by its memory_key within tenant and user scope."""
        return (
            self._db.query(BusinessAssistantMemory)
            .filter(
                BusinessAssistantMemory.tenant_id == self._tenant_id,
                BusinessAssistantMemory.user_id == self._user_id,
                BusinessAssistantMemory.memory_key == memory_key,
            )
            .first()
        )

    def get_memory_by_id(self, memory_id: int) -> Optional[BusinessAssistantMemory]:
        """Retrieve a business rule by its ID within tenant and user scope."""
        return (
            self._db.query(BusinessAssistantMemory)
            .filter(
                BusinessAssistantMemory.id == memory_id,
                BusinessAssistantMemory.tenant_id == self._tenant_id,
                BusinessAssistantMemory.user_id == self._user_id,
            )
            .first()
        )

    def list_memories(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessAssistantMemory]:
        """List business rules scoped to the current tenant and user."""
        query = self._db.query(BusinessAssistantMemory).filter(
            BusinessAssistantMemory.tenant_id == self._tenant_id,
            BusinessAssistantMemory.user_id == self._user_id,
        )
        if status:
            query = query.filter(BusinessAssistantMemory.status == status)
        return (
            query.order_by(
                BusinessAssistantMemory.updated_at.desc(),
                BusinessAssistantMemory.id.desc(),
            )
            .limit(limit)
            .all()
        )

    def update_memory_draft(
        self,
        *,
        memory: BusinessAssistantMemory,
        content: str,
        interpretation: Optional[str] = None,
        category: Optional[str] = None,
        curator_item_id: Optional[int] = None,
        payload_hash: Optional[str] = None,
        provenance_update: Optional[dict] = None,
    ) -> BusinessAssistantMemory:
        """Update an existing business rule draft, incrementing its version."""
        if memory.tenant_id != self._tenant_id or memory.user_id != self._user_id:
            raise ValueError("Memory record is outside the authenticated scope.")
        memory.content = content
        if interpretation is not None:
            memory.interpretation = interpretation
        if category is not None:
            memory.category = category
        if curator_item_id is not None:
            memory.curator_item_id = curator_item_id
        memory.version = (memory.version or 1) + 1
        memory.payload_hash = payload_hash
        memory.status = "draft"
        memory.updated_at = datetime.now(timezone.utc)
        current_prov = dict(memory.provenance or {})
        if provenance_update:
            current_prov.update(provenance_update)
        memory.provenance = current_prov
        self._db.flush()
        return memory

    def activate_memory(
        self,
        *,
        memory: BusinessAssistantMemory,
        actor_user_id: int,
        provenance_update: Optional[dict] = None,
    ) -> BusinessAssistantMemory:
        """Activate a business rule, recording actor and provenance."""
        if memory.tenant_id != self._tenant_id or memory.user_id != self._user_id:
            raise ValueError("Memory record is outside the authenticated scope.")
        now = datetime.now(timezone.utc)
        memory.status = "active"
        memory.activated_at = now
        memory.activated_by_user_id = actor_user_id
        memory.updated_at = now
        current_prov = dict(memory.provenance or {})
        current_prov["activated_at"] = now.isoformat()
        current_prov["activated_by_user_id"] = actor_user_id
        if provenance_update:
            current_prov.update(provenance_update)
        memory.provenance = current_prov
        self._db.flush()
        return memory

    def list_curator_proposals(
        self,
        *,
        status: str = "pending",
        limit: int = 50,
    ) -> list[KnowledgeProposal]:
        """List reviewable curator proposals strictly within tenant boundary."""
        query = self._db.query(KnowledgeProposal).filter(
            KnowledgeProposal.tenant_id == self._tenant_id,
        )
        if status != "all":
            query = query.filter(KnowledgeProposal.status == status)
        return (
            query.order_by(
                KnowledgeProposal.created_at.desc(),
                KnowledgeProposal.id.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_curator_proposal(self, proposal_id: int) -> Optional[KnowledgeProposal]:
        """Retrieve a curator proposal strictly within tenant boundary."""
        return (
            self._db.query(KnowledgeProposal)
            .filter(
                KnowledgeProposal.id == proposal_id,
                KnowledgeProposal.tenant_id == self._tenant_id,
            )
            .first()
        )

    def resolve_curator_proposal(
        self,
        *,
        proposal: KnowledgeProposal,
        actor_user_id: int,
        resolution_code: str = "resolved",
        status: str = "resolved",
    ) -> KnowledgeProposal:
        """Resolve a curator proposal recording reviewer and resolution code."""
        if proposal.tenant_id != self._tenant_id:
            raise ValueError("Curator proposal is outside the authenticated scope.")
        proposal.status = status
        proposal.resolution_code = resolution_code
        proposal.reviewed_by_user_id = actor_user_id
        proposal.reviewed_at = datetime.now(timezone.utc)
        self._db.flush()
        return proposal

    def sync_curated_memory(
        self,
        *,
        memory: BusinessAssistantMemory,
    ) -> CuratedMemory:
        """Sync an active business rule into CuratedMemory for system retrieval."""
        if memory.tenant_id != self._tenant_id:
            raise ValueError("Memory record is outside the authenticated scope.")
        source_ref = f"business_assistant_memory:{memory.id}"
        existing = (
            self._db.query(CuratedMemory)
            .filter(
                CuratedMemory.tenant_id == self._tenant_id,
                CuratedMemory.source_reference == source_ref,
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.category = memory.category
            existing.user_query = memory.memory_key
            existing.ideal_response = memory.content
            existing.content_hash = memory.payload_hash
            existing.status = "active"
            existing.verified_by_user_id = memory.activated_by_user_id
            existing.last_verified_at = now
            existing.updated_at = now
            self._db.flush()
            return existing

        curated = CuratedMemory(
            tenant_id=self._tenant_id,
            category=memory.category,
            user_query=memory.memory_key,
            ideal_response=memory.content,
            knowledge_kind="response_guidance" if "guidance" in memory.category.lower() else "durable_fact",
            authority="owner_verified",
            status="active",
            conflict_state="clear",
            content_hash=memory.payload_hash,
            source_reference=source_ref,
            verified_by_user_id=memory.activated_by_user_id,
            last_verified_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(curated)
        self._db.flush()
        return curated

