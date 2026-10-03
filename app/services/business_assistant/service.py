"""Application service for the native Business Assistant persistence foundation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Optional, TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ...models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantMessage,
    SupportTicket,
    SupportTicketEvent,
    BusinessAssistantOnboardingProgress,
)
from .product_context import ProductContext, ProductContextAdapter
from .repository import BusinessAssistantRepository
from .idempotency import IdempotencyKeyConflictError, payload_hash, require_matching_payload
from .tickets import sanitise_ticket_text, ticket_deduplication_key

if TYPE_CHECKING:
    from .runtime import BusinessAssistantTextRuntime


@dataclass(frozen=True)
class TextTurnResult:
    """Persisted output from one completed text conversation turn."""

    user_message: BusinessAssistantMessage
    assistant_message: BusinessAssistantMessage
    duplicate_request: bool = False


class TextTurnInProgressError(RuntimeError):
    """Raised when another request already owns the provider call for a turn."""


class BusinessAssistantStorageUnavailableError(RuntimeError):
    """Raised when required native persistence has not been migrated or is unavailable."""


@dataclass(frozen=True)
class TicketCreateResult:
    """The persisted ticket and whether an existing active ticket was reused."""

    ticket: SupportTicket
    duplicate_ticket: bool = False


@dataclass(frozen=True)
class RealtimeTurnResult:
    """Ordered realtime transcript messages persisted in one transaction."""

    user_message: BusinessAssistantMessage
    assistant_message: BusinessAssistantMessage
    duplicate_turn: bool = False


ONBOARDING_STEPS = (
    "review_product_context",
    "review_catalog_readiness",
    "prepare_product_question",
)


class BusinessAssistantService:
    """Coordinates scoped persistence without model calls, tools, or external effects."""

    def __init__(self, db: Session, tenant_id: int, user_id: int) -> None:
        self._db = db
        self._repository = BusinessAssistantRepository(db, tenant_id, user_id)
        self._product_context = ProductContextAdapter(db, tenant_id)

    def create_conversation(
        self,
        *,
        title: Optional[str] = None,
        request_key: Optional[str] = None,
    ) -> BusinessAssistantConversation:
        return self.create_or_get_conversation(title=title, request_key=request_key)

    def create_or_get_conversation(
        self,
        *,
        title: Optional[str] = None,
        request_key: Optional[str] = None,
    ) -> BusinessAssistantConversation:
        """Persist an idempotent conversation and recover safely from a key race."""
        request_payload_hash = payload_hash({"title": title})
        try:
            if request_key:
                existing = self._repository.get_conversation_by_creation_request_key(request_key)
                if existing:
                    require_matching_payload(
                        stored_hash=existing.creation_payload_hash,
                        incoming_hash=request_payload_hash,
                    )
                    return existing
            conversation = self._repository.create_conversation(
                title=title,
                request_key=request_key,
                payload_hash=request_payload_hash if request_key else None,
            )
            self._db.commit()
            self._db.refresh(conversation)
            return conversation
        except IntegrityError:
            self._db.rollback()
            if not request_key:
                raise
            existing = self._repository.get_conversation_by_creation_request_key(request_key)
            if not existing:
                raise
            require_matching_payload(
                stored_hash=existing.creation_payload_hash,
                incoming_hash=request_payload_hash,
            )
            return existing
        except SQLAlchemyError as exc:
            self._db.rollback()
            raise BusinessAssistantStorageUnavailableError(
                "Business Assistant storage is unavailable. Apply the current database migration before retrying."
            ) from exc

    def list_conversations(self) -> list[BusinessAssistantConversation]:
        return self._repository.list_conversations()

    def get_conversation(self, *, conversation_id: int) -> BusinessAssistantConversation:
        """Return one conversation only in the current authenticated scope."""
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")
        return conversation

    def append_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
        request_key: Optional[str] = None,
        in_reply_to_message_id: Optional[int] = None,
    ) -> BusinessAssistantMessage:
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")
        return self._repository.append_message(
            conversation=conversation,
            role=role,
            content=content,
            request_key=request_key,
            in_reply_to_message_id=in_reply_to_message_id,
        )

    def list_messages(self, *, conversation_id: int, limit: int) -> list[BusinessAssistantMessage]:
        """Read only the caller-owned message history in chronological order."""
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")
        return self._repository.list_messages(conversation=conversation, limit=limit)

    def persist_realtime_turn(
        self,
        *,
        conversation_id: int,
        session_id: str,
        user_item_id: str,
        assistant_response_id: str,
        user_transcript: str,
        assistant_transcript: str,
    ) -> RealtimeTurnResult:
        """Persist one completed voice pair without granting any voice-only tools."""
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")
        existing_user = self._repository.get_message_by_realtime_item(
            conversation_id=conversation_id,
            session_id=session_id,
            item_id=user_item_id,
        )
        existing_assistant = self._repository.get_message_by_realtime_item(
            conversation_id=conversation_id,
            session_id=session_id,
            item_id=assistant_response_id,
        )
        if existing_user or existing_assistant:
            if existing_user and existing_assistant and existing_assistant.in_reply_to_message_id == existing_user.id:
                return RealtimeTurnResult(
                    user_message=existing_user,
                    assistant_message=existing_assistant,
                    duplicate_turn=True,
                )
            raise TextTurnInProgressError("A voice transcript with this event identifier is already being persisted.")
        try:
            user_message = self._repository.append_message(
                conversation=conversation,
                role="user",
                content=user_transcript,
                channel="realtime_voice",
                realtime_session_id=session_id,
                realtime_item_id=user_item_id,
            )
            assistant_message = self._repository.append_message(
                conversation=conversation,
                role="business_assistant",
                content=assistant_transcript,
                in_reply_to_message_id=user_message.id,
                channel="realtime_voice",
                realtime_session_id=session_id,
                realtime_item_id=assistant_response_id,
            )
            self._db.commit()
            self._db.refresh(user_message)
            self._db.refresh(assistant_message)
        except IntegrityError:
            self._db.rollback()
            existing_user = self._repository.get_message_by_realtime_item(
                conversation_id=conversation_id,
                session_id=session_id,
                item_id=user_item_id,
            )
            existing_assistant = self._repository.get_message_by_realtime_item(
                conversation_id=conversation_id,
                session_id=session_id,
                item_id=assistant_response_id,
            )
            if not existing_user or not existing_assistant or existing_assistant.in_reply_to_message_id != existing_user.id:
                raise TextTurnInProgressError("A voice transcript with this event identifier is already being persisted.")
            return RealtimeTurnResult(
                user_message=existing_user,
                assistant_message=existing_assistant,
                duplicate_turn=True,
            )
        return RealtimeTurnResult(user_message=user_message, assistant_message=assistant_message)

    def submit_text_turn(
        self,
        *,
        conversation_id: int,
        content: str,
        request_key: str,
        runtime_factory: Callable[[], "BusinessAssistantTextRuntime"],
    ) -> TextTurnResult:
        """Persist a user turn before bounded generation, preserving it on failure."""
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")

        request_payload_hash = payload_hash({"content": content})
        user_message = self._repository.get_message_by_request_key(
            conversation_id=conversation_id,
            request_key=request_key,
        )
        if user_message:
            require_matching_payload(
                stored_hash=user_message.request_payload_hash,
                incoming_hash=request_payload_hash,
            )
            reply = self._repository.get_reply_to_message(user_message.id)
            if reply:
                return TextTurnResult(
                    user_message=user_message,
                    assistant_message=reply,
                    duplicate_request=True,
                )
            if not self._repository.claim_retryable_turn(user_message.id):
                raise TextTurnInProgressError("A response for this message is already being generated.")
        else:
            try:
                user_message = self._repository.append_message(
                    conversation=conversation,
                    role="user",
                    content=content,
                    request_key=request_key,
                    request_payload_hash=request_payload_hash,
                    generation_status="running",
                    generation_started_at=datetime.now(timezone.utc),
                )
                self._db.commit()
                self._db.refresh(user_message)
            except IntegrityError:
                self._db.rollback()
                user_message = self._repository.get_message_by_request_key(
                    conversation_id=conversation_id,
                    request_key=request_key,
                )
                if not user_message:
                    raise
                require_matching_payload(
                    stored_hash=user_message.request_payload_hash,
                    incoming_hash=request_payload_hash,
                )
                reply = self._repository.get_reply_to_message(user_message.id)
                if reply:
                    return TextTurnResult(
                        user_message=user_message,
                        assistant_message=reply,
                        duplicate_request=True,
                    )
                raise TextTurnInProgressError("A response for this message is already being generated.")

        try:
            runtime = runtime_factory()
            history = self._repository.list_messages(
                conversation=conversation,
                limit=runtime.max_history_messages,
            )
            from .adapters import BusinessAssistantReadAdapters
            from .tool_registry import ProductHelpToolRegistry

            tool_registry = ProductHelpToolRegistry(
                BusinessAssistantReadAdapters(
                    self._db,
                    tenant_id=conversation.tenant_id,
                    user_id=conversation.user_id,
                )
            )

            def execute_product_help_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
                started_at = monotonic()
                try:
                    result = tool_registry.execute(name, arguments)
                    tool_status = str(result.get("status") or "completed")
                    return result
                except Exception:
                    tool_status = "failed"
                    return {"status": "unavailable", "reason": "That product-help read is currently unavailable."}
                finally:
                    self._repository.record_tool_run(
                        conversation=conversation,
                        message=user_message,
                        tool_name=name,
                        status=tool_status,
                        duration_ms=int((monotonic() - started_at) * 1000),
                    )

            reply_content = runtime.generate_reply(
                history,
                product_context=self.read_product_context().instruction_text(),
                tools=tool_registry.schemas,
                tool_executor=execute_product_help_tool,
            )
        except Exception:
            self._repository.mark_turn_failed(user_message)
            raise
        assistant_message = self._repository.append_message(
            conversation=conversation,
            role="business_assistant",
            content=reply_content,
            in_reply_to_message_id=user_message.id,
        )
        self._repository.mark_turn_completed(user_message)
        self._db.commit()
        self._db.refresh(assistant_message)
        return TextTurnResult(user_message=user_message, assistant_message=assistant_message)

    def create_ticket(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        request_key: Optional[str] = None,
        conversation_id: Optional[int] = None,
    ) -> SupportTicket:
        return self.create_or_get_ticket(
            category=category,
            severity=severity,
            title=title,
            description=description,
            request_key=request_key,
            conversation_id=conversation_id,
        ).ticket

    def create_or_get_ticket(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        request_key: Optional[str] = None,
        conversation_id: Optional[int] = None,
    ) -> TicketCreateResult:
        """Create a sanitised ticket or return a scoped idempotent active duplicate."""
        conversation = None
        if conversation_id is not None:
            conversation = self._repository.get_conversation(conversation_id)
            if not conversation:
                raise LookupError("Conversation was not found in the authenticated scope.")

        safe_title = sanitise_ticket_text(title)
        safe_description = sanitise_ticket_text(description)
        request_payload_hash = payload_hash(
            {
                "category": category,
                "severity": severity,
                "title": safe_title,
                "description": safe_description,
                "conversation_id": conversation_id,
            }
        )
        deduplication_key = ticket_deduplication_key(
            category=category,
            title=safe_title,
            description=safe_description,
        )
        if request_key:
            existing = self._repository.get_ticket_by_request_key(request_key)
            if existing:
                require_matching_payload(
                    stored_hash=existing.request_payload_hash,
                    incoming_hash=request_payload_hash,
                )
                return TicketCreateResult(ticket=existing, duplicate_ticket=True)
        existing = self._repository.get_active_ticket_by_deduplication_key(deduplication_key)
        if existing:
            return TicketCreateResult(ticket=existing, duplicate_ticket=True)

        try:
            ticket = self._repository.create_ticket(
                category=category,
                severity=severity,
                title=safe_title,
                description=safe_description,
                deduplication_key=deduplication_key,
                request_key=request_key,
                request_payload_hash=request_payload_hash if request_key else None,
                conversation=conversation,
            )
            self._db.commit()
            self._db.refresh(ticket)
        except IntegrityError:
            self._db.rollback()
            existing = (
                self._repository.get_ticket_by_request_key(request_key)
                if request_key
                else self._repository.get_active_ticket_by_deduplication_key(deduplication_key)
            )
            if not existing:
                existing = self._repository.get_active_ticket_by_deduplication_key(deduplication_key)
            if not existing:
                raise
            require_matching_payload(
                stored_hash=existing.request_payload_hash if request_key else request_payload_hash,
                incoming_hash=request_payload_hash,
            )
            return TicketCreateResult(ticket=existing, duplicate_ticket=True)
        return TicketCreateResult(ticket=ticket)

    def list_tickets(self, *, limit: int) -> list[SupportTicket]:
        return self._repository.list_tickets(limit=limit)

    def get_ticket(self, *, ticket_id: int) -> SupportTicket:
        ticket = self._repository.get_ticket(ticket_id)
        if not ticket:
            raise LookupError("Ticket was not found in the authenticated scope.")
        return ticket

    def list_ticket_events(self, *, ticket_id: int) -> list[SupportTicketEvent]:
        self.get_ticket(ticket_id=ticket_id)
        return self._repository.list_ticket_events(ticket_id)

    def read_product_context(self) -> ProductContext:
        """Return the current, strictly allowlisted native setup snapshot."""
        return self._product_context.read()

    def get_onboarding_progress(self) -> Optional[BusinessAssistantOnboardingProgress]:
        """Read personal onboarding state without creating or changing any record."""
        return self._repository.get_onboarding_progress()

    def complete_onboarding_step(self, *, step: str) -> BusinessAssistantOnboardingProgress:
        """Persist one fixed personal milestone without changing tenant configuration."""
        if step not in ONBOARDING_STEPS:
            raise ValueError("The onboarding step is not recognised.")
        progress = self._repository.get_or_create_onboarding_progress()
        completed = set(progress.completed_steps or [])
        completed.add(step)
        progress.completed_steps = [candidate for candidate in ONBOARDING_STEPS if candidate in completed]
        progress.status = "completed" if len(progress.completed_steps) == len(ONBOARDING_STEPS) else "in_progress"
        self._db.commit()
        self._db.refresh(progress)
        return progress
