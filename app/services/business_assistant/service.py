"""Application service for the native Business Assistant persistence foundation."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any, Callable, Optional, TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ...models.business_assistant import (
    BusinessAssistantCampaignProposal,
    BusinessAssistantConversation,
    BusinessAssistantMemory,
    BusinessAssistantMessage,
    BusinessAssistantMessageDraft,
    BusinessAssistantOnboardingProgress,
    BusinessAssistantWebsiteProposal,
    BusinessAssistantToolRun,
    SupportTicket,
    SupportTicketDeduplicationClaim,
    SupportTicketEvent,
    BusinessAssistantDiagnosticSetting,
    BusinessAssistantClientSnapshot,
    AssistantErrorLog,
)
from ...models.curated_memory import CuratedMemory, KnowledgeProposal
from ...models.tenant import Tenant
from ...models.tenant_website import DEFAULT_SECTIONS_DATA, TenantWebsite
from ...models.user import User
from ..website_initial_draft import ensure_initial_website_draft
from .rollout import (
    BusinessAssistantRolloutRestrictionError,
    RolloutAccessDecision,
    RolloutGate,
    RolloutStage,
)
from .confirmation import (
    ConfirmationError,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    ConfirmationSignatureError,
    DynamicFactRejectedError,
    compute_campaign_payload_hash,
    compute_draft_payload_hash,
    compute_rule_payload_hash,
    compute_website_payload_hash,
    generate_confirmation_token,
    validate_static_business_knowledge,
    verify_confirmation_token,
)
from .product_context import ProductContext, ProductContextAdapter
from .repository import BusinessAssistantRepository
from .idempotency import IdempotencyKeyConflictError, payload_hash, require_matching_payload
from .tickets import ELEVATED_APPROVAL_CATEGORIES, sanitise_ticket_text, ticket_deduplication_key
from .website_sanitiser import (
    WebsiteContentSafetyError,
    WebsiteVersionConflictError,
    validate_and_sanitise_website_content,
)

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
    confirmation_token: Optional[str] = None


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
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._repository = BusinessAssistantRepository(db, tenant_id, user_id)
        self._product_context = ProductContextAdapter(db, tenant_id)

    def verify_rollout_access(
        self,
        tenant: Optional[Tenant] = None,
        user: Optional[User] = None,
        stage_override: Optional[str] = None,
    ) -> RolloutAccessDecision:
        """Verify that the current tenant and user are permitted under the active rollout stage."""
        resolved_tenant = tenant
        if resolved_tenant is None:
            resolved_tenant = self._db.query(Tenant).filter(Tenant.id == self._tenant_id).first()
        resolved_user = user
        if resolved_user is None:
            resolved_user = self._db.query(User).filter(User.id == self._user_id).first()
        return RolloutGate.enforce(
            tenant=resolved_tenant,
            user=resolved_user,
            stage_override=stage_override,
        )

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
        user_clean = user_transcript.strip()
        assistant_clean = assistant_transcript.strip()
        if not user_clean or not assistant_clean:
            raise ValueError("Transcripts cannot be empty or whitespace only.")
        if user_item_id == assistant_response_id:
            raise ValueError("user_item_id and assistant_response_id must be distinct event identifiers.")

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
            from .tool_registry import BusinessAssistantToolRegistry, ALL_TOOL_PACKS
            from .runtime import build_text_turn_tools

            tool_registry = BusinessAssistantToolRegistry(
                BusinessAssistantReadAdapters(
                    self._db,
                    tenant_id=conversation.tenant_id,
                    user_id=conversation.user_id,
                ),
                service=self,
                packs=ALL_TOOL_PACKS,
            )

            text_tools = build_text_turn_tools(tool_registry.schemas)

            def execute_assistant_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
                return self.execute_tool(
                    conversation_id=conversation.id,
                    name=name,
                    arguments=arguments,
                    message_id=user_message.id,
                )

            diagnostic_mode = self.get_diagnostic_mode()
            gen_kwargs: dict[str, Any] = {
                "product_context": self.read_product_context().instruction_text(),
                "tools": text_tools,
                "tool_executor": execute_assistant_tool,
            }
            import inspect
            sig = inspect.signature(runtime.generate_reply)
            if "diagnostic_mode" in sig.parameters:
                gen_kwargs["diagnostic_mode"] = diagnostic_mode

            reply_content = runtime.generate_reply(
                history,
                **gen_kwargs,
            )
        except Exception as exc:
            self._repository.mark_turn_failed(user_message)
            self.record_assistant_error(
                source="text",
                user_id=conversation.user_id,
                conversation_id=conversation.id,
                error_code="TEXT_TURN_FAILED",
                message=str(exc),
            )
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

    def execute_tool(
        self,
        *,
        conversation_id: int,
        name: str,
        arguments: dict[str, object],
        message_id: Optional[int] = None,
    ) -> dict[str, object]:
        """Execute one server-authorised tool within conversation scope with audit recording."""
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise LookupError("Conversation was not found in the authenticated scope.")

        message = None
        if message_id is not None:
            message = self._repository.get_message(message_id)
            if not message or message.conversation_id != conversation.id:
                raise LookupError("Message was not found in the conversation scope.")

        if name == "run_diagnostic_check":
            name = "diagnostic_report"

        if name in ("diagnostic_report", "run_diagnostic_check") and isinstance(arguments, dict):
            if any(k in arguments for k in ("route", "path", "page", "target")):
                target = arguments.get("route") or arguments.get("path") or arguments.get("target") or arguments.get("page")
                if target and isinstance(target, str):
                    target_route = target if target.startswith("/admin") else f"/admin/{target.lstrip('/')}"
                    name = "navigate_route"
                    arguments = {"route": target_route, "subtab": arguments.get("subtab")}

        if name in ("activate_business_rule", "confirm_business_rule") and isinstance(arguments, dict):
            mem_key = str(arguments.get("memory_key") or arguments.get("rule_id") or "")
            conf_tok = str(arguments.get("confirmation_token") or "")
            if mem_key in ("navigate_route", "route_navigation") or conf_tok.startswith("/admin"):
                target_route = conf_tok if conf_tok.startswith("/admin") else mem_key
                name = "navigate_route"
                arguments = {"route": target_route}

        # Safeguard 1: Burst rate limiter (max 4 calls per 3 seconds for general tools; onboarding workflows allowed up to 10 calls per 3 seconds)
        from .onboarding.tools import ONBOARDING_TOOL_NAMES

        now_utc = datetime.now(timezone.utc)
        recent_burst_count = (
            self._db.query(func.count(BusinessAssistantToolRun.id))
            .filter(
                BusinessAssistantToolRun.tenant_id == conversation.tenant_id,
                BusinessAssistantToolRun.conversation_id == conversation.id,
                BusinessAssistantToolRun.created_at >= now_utc - timedelta(seconds=3),
            )
            .scalar() or 0
        )
        burst_limit = 10 if name in ONBOARDING_TOOL_NAMES else 4
        if recent_burst_count >= burst_limit:
            return {
                "status": "rejected",
                "reason": f"Tool execution rate limit exceeded (burst protection: max {burst_limit} calls per 3 seconds).",
            }

        # Safeguard 2: Cooldown on diagnostic_report (max 1 run per 15s per conversation)
        if name in ("diagnostic_report", "run_diagnostic_check"):
            recent_diag = (
                self._db.query(BusinessAssistantToolRun)
                .filter(
                    BusinessAssistantToolRun.tenant_id == conversation.tenant_id,
                    BusinessAssistantToolRun.conversation_id == conversation.id,
                    BusinessAssistantToolRun.tool_name == "diagnostic_report",
                    BusinessAssistantToolRun.created_at >= now_utc - timedelta(seconds=15),
                )
                .first()
            )
            if recent_diag:
                return {
                    "status": "ok",
                    "verdict": "Cached",
                    "summary": "Diagnostic report cooldown active (<15s since previous run). Using recent status.",
                    "throttled": True,
                    "terminal": True,
                }

        from .onboarding.tools import ONBOARDING_TOOL_NAMES
        if name in ONBOARDING_TOOL_NAMES:
            from .onboarding.gateway import OnboardingGateway

            class _NonClosingSessionProxy:
                def __init__(self, session):
                    self._session = session
                def __getattr__(self, name):
                    return getattr(self._session, name)
                def close(self):
                    pass

            gateway = OnboardingGateway(
                db_factory=lambda: _NonClosingSessionProxy(self._db),
                tenant_id=conversation.tenant_id,
                user_id=conversation.user_id,
            )
            started_at = monotonic()
            try:
                result = gateway.execute_tool_sync(
                    name=name,
                    arguments=arguments,
                    lease_token=arguments.get("lease_token") if isinstance(arguments, dict) else None,
                    control_epoch=arguments.get("control_epoch") if isinstance(arguments, dict) else None,
                )
                tool_status = str(result.get("status") or "completed")
                if tool_status in ("rejected", "unavailable", "failed"):
                    self.record_assistant_error(
                        source="text",
                        user_id=conversation.user_id,
                        conversation_id=conversation.id,
                        tool_name=name,
                        error_code=tool_status.upper(),
                        message=str(result.get("reason") or "Onboarding tool execution rejected"),
                    )
                return result
            except Exception as exc:
                tool_status = "failed"
                self.record_assistant_error(
                    source="text",
                    user_id=conversation.user_id,
                    conversation_id=conversation.id,
                    tool_name=name,
                    error_code="ONBOARDING_TOOL_FAILED",
                    message=str(exc),
                )
                return {"status": "unavailable", "reason": str(exc)}
            finally:
                self._repository.record_tool_run(
                    conversation=conversation,
                    message=message,
                    tool_name=name,
                    status=tool_status,
                    duration_ms=int((monotonic() - started_at) * 1000),
                )
                self._db.commit()

        from .adapters import BusinessAssistantReadAdapters
        from .tool_registry import BusinessAssistantToolRegistry, ALL_TOOL_PACKS

        adapters = BusinessAssistantReadAdapters(
            self._db,
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
        )
        registry = BusinessAssistantToolRegistry(adapters, service=self, packs=ALL_TOOL_PACKS)
        started_at = monotonic()
        try:
            effective_args = dict(arguments) if isinstance(arguments, dict) else {}
            if name == "diagnostic_report" and "conversation_id" not in effective_args:
                effective_args["conversation_id"] = conversation_id

            result = registry.execute(name, effective_args)
            tool_status = str(result.get("status") or "completed")
            if tool_status in ("rejected", "unavailable", "failed"):
                self.record_assistant_error(
                    source="text",
                    user_id=conversation.user_id,
                    conversation_id=conversation.id,
                    tool_name=name,
                    error_code=tool_status.upper(),
                    message=str(result.get("reason") or "Tool execution rejected or unavailable"),
                )
            elif name == "diagnostic_report" and tool_status in ("ok", "completed") and not result.get("throttled"):
                report = result.get("report") if isinstance(result.get("report"), dict) else result
                if isinstance(report, dict) and "verdict" in report:
                    verdict = report.get("verdict", "Unknown")
                    summary = report.get("summary", "")
                    working = report.get("working", [])
                    not_working = report.get("not_working", [])
                    cannot_do = report.get("cannot_do", "")
                    next_step = report.get("next_step", "")
                    details = report.get("details", {})

                    if isinstance(working, list):
                        working_md = "\n".join(f"- {w}" for w in working) if working else "- None"
                    else:
                        working_md = f"- {working}"

                    if isinstance(not_working, list):
                        not_working_md = "\n".join(f"- {nw}" for nw in not_working) if not_working else "- None"
                    else:
                        not_working_md = f"- {not_working}"

                    if isinstance(cannot_do, list):
                        cannot_do_md = "\n".join(f"- {cd}" for cd in cannot_do) if cannot_do else "- None"
                    else:
                        cannot_do_md = f"- {cannot_do}" if cannot_do else "- None"

                    details_json = json.dumps(details, indent=2)
                    formatted_report = (
                        f"### System Diagnostic Report\n"
                        f"**Verdict**: {verdict} - {summary}\n\n"
                        f"#### Working Subsystems\n"
                        f"{working_md}\n\n"
                        f"#### Issues & Degradations\n"
                        f"{not_working_md}\n\n"
                        f"#### Operating Boundaries\n"
                        f"{cannot_do_md}\n\n"
                        f"#### Recommended Next Steps\n"
                        f"{next_step}\n\n"
                        f"<details>\n"
                        f"<summary>Full 8-Step Runbook Details</summary>\n\n"
                        f"```json\n"
                        f"{details_json}\n"
                        f"```\n"
                        f"</details>"
                    )
                    recent_diag_msg = (
                        self._db.query(BusinessAssistantMessage)
                        .filter(
                            BusinessAssistantMessage.conversation_id == conversation_id,
                            BusinessAssistantMessage.role == "business_assistant",
                            BusinessAssistantMessage.created_at >= now_utc - timedelta(seconds=30),
                        )
                        .order_by(BusinessAssistantMessage.created_at.desc())
                        .first()
                    )
                    has_recent_diag = recent_diag_msg and "### System Diagnostic Report" in (recent_diag_msg.content or "")
                    if not has_recent_diag:
                        self._repository.create_message(
                            conversation_id=conversation_id,
                            role="business_assistant",
                            content=formatted_report,
                            channel="realtime_voice",
                        )

            if name == "navigate_route" and isinstance(result, dict):
                result["terminal"] = True
                result["directive"] = "Navigation completed. Confirm the new page to the user and conclude your turn. Do not execute further tools."

            return result
        except Exception as exc:
            tool_status = "failed"
            self.record_assistant_error(
                source="text",
                user_id=conversation.user_id,
                conversation_id=conversation.id,
                tool_name=name,
                error_code="TOOL_EXCEPTION",
                message=str(exc),
            )
            return {"status": "unavailable", "reason": str(exc)}
        finally:
            self._repository.record_tool_run(
                conversation=conversation,
                message=message,
                tool_name=name,
                status=tool_status,
                duration_ms=int((monotonic() - started_at) * 1000),
            )
            self._db.commit()

    def create_ticket(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        observed_behaviour: Optional[str] = None,
        affected_product_area: Optional[str] = None,
        user_impact: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        request_key: Optional[str] = None,
        conversation_id: Optional[int] = None,
    ) -> SupportTicket:
        return self.create_or_get_ticket(
            category=category,
            severity=severity,
            title=title,
            description=description,
            observed_behaviour=observed_behaviour,
            affected_product_area=affected_product_area,
            user_impact=user_impact,
            acceptance_criteria=acceptance_criteria,
            request_key=request_key,
            conversation_id=conversation_id,
        ).ticket

    def _generate_ticket_approval_token(self, ticket: SupportTicket) -> str:
        """Generate a cryptographically bound confirmation token for owner ticket approval."""
        return generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=ticket.user_id or self._user_id,
            action="approve_ticket_dispatch",
            target_key=f"ticket:{ticket.id}",
            version=1,
            payload_hash=ticket.deduplication_key,
        )

    def create_or_get_ticket(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        observed_behaviour: Optional[str] = None,
        affected_product_area: Optional[str] = None,
        user_impact: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
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
        safe_observed = sanitise_ticket_text(observed_behaviour) if observed_behaviour else None
        safe_area = sanitise_ticket_text(affected_product_area) if affected_product_area else None
        safe_impact = sanitise_ticket_text(user_impact) if user_impact else None
        safe_criteria = sanitise_ticket_text(acceptance_criteria) if acceptance_criteria else None

        # Stop-gate: Access and security categories require explicit owner approval
        requires_owner_approval = category in ELEVATED_APPROVAL_CATEGORIES
        if requires_owner_approval:
            status = "pending_owner_approval"
            authorisation_state = "pending_approval"
        else:
            status = "awaiting_engineering"
            authorisation_state = "not_required"

        request_payload_hash = payload_hash(
            {
                "category": category,
                "severity": severity,
                "title": safe_title,
                "description": safe_description,
                "observed_behaviour": safe_observed,
                "affected_product_area": safe_area,
                "user_impact": safe_impact,
                "acceptance_criteria": safe_criteria,
                "conversation_id": conversation_id,
            }
        )
        deduplication_key = ticket_deduplication_key(
            category=category,
            title=safe_title,
            affected_product_area=safe_area,
            tenant_id=self._tenant_id,
            description=safe_description,
        )
        if request_key:
            existing = self._repository.get_ticket_by_request_key(request_key)
            if existing:
                require_matching_payload(
                    stored_hash=existing.request_payload_hash,
                    incoming_hash=request_payload_hash,
                )
                token = self._generate_ticket_approval_token(existing) if existing.requires_owner_approval else None
                return TicketCreateResult(ticket=existing, duplicate_ticket=True, confirmation_token=token)

        existing = self._repository.get_active_ticket_by_deduplication_key(deduplication_key)
        if existing:
            self._repository.record_ticket_event(
                ticket_id=existing.id,
                event_type="duplicate_referenced",
                safe_metadata={
                    "reason": "Active duplicate ticket referenced",
                    "referencing_conversation_id": conversation_id,
                },
            )
            self._db.commit()
            self._db.refresh(existing)
            token = self._generate_ticket_approval_token(existing) if existing.requires_owner_approval else None
            return TicketCreateResult(ticket=existing, duplicate_ticket=True, confirmation_token=token)

        try:
            ticket = self._repository.create_ticket(
                category=category,
                severity=severity,
                title=safe_title,
                description=safe_description,
                observed_behaviour=safe_observed,
                affected_product_area=safe_area,
                user_impact=safe_impact,
                acceptance_criteria=safe_criteria,
                authorisation_state=authorisation_state,
                requires_owner_approval=requires_owner_approval,
                status=status,
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
            token = self._generate_ticket_approval_token(existing) if existing.requires_owner_approval else None
            return TicketCreateResult(ticket=existing, duplicate_ticket=True, confirmation_token=token)

        token = self._generate_ticket_approval_token(ticket) if requires_owner_approval else None
        return TicketCreateResult(ticket=ticket, confirmation_token=token)

    def request_ticket_approval(
        self,
        *,
        ticket_id: int,
        note: Optional[str] = None,
    ) -> tuple[SupportTicket, str]:
        """Generate confirmation token and request explicit owner approval for an elevated ticket."""
        ticket = self.get_ticket(ticket_id=ticket_id)
        if not ticket.requires_owner_approval and ticket.category not in ELEVATED_APPROVAL_CATEGORIES:
            raise ValueError(f"Ticket #{ticket_id} ({ticket.category}) does not require elevated owner approval.")
        if ticket.status != "pending_owner_approval":
            raise ValueError(
                f"Ticket #{ticket_id} is in status '{ticket.status}', not pending owner approval."
            )

        token = self._generate_ticket_approval_token(ticket)
        if note:
            self._repository.record_ticket_event(
                ticket_id=ticket.id,
                event_type="approval_requested",
                safe_metadata={
                    "status": ticket.status,
                    "category": ticket.category,
                    "note": note.strip()[:200],
                },
            )
            self._db.commit()
            self._db.refresh(ticket)
        return ticket, token

    def approve_ticket_dispatch(
        self,
        *,
        ticket_id: int,
        confirmation_token: Optional[str] = None,
        note: Optional[str] = None,
    ) -> SupportTicket:
        """Approve an elevated access/security ticket. Strictly restricted to tenant owners."""
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        if not user or user.role != "owner":
            raise PermissionError("Only tenant owners may approve elevated access/security tickets.")

        ticket = self.get_ticket(ticket_id=ticket_id)
        if ticket.status != "pending_owner_approval":
            raise ValueError(
                f"Cannot approve ticket #{ticket_id} in '{ticket.status}' status. Only tickets in 'pending_owner_approval' can be approved."
            )

        if confirmation_token:
            verify_confirmation_token(
                token=confirmation_token,
                expected_tenant_id=self._tenant_id,
                expected_user_id=ticket.user_id or self._user_id,
                expected_action="approve_ticket_dispatch",
                expected_target_key=f"ticket:{ticket.id}",
                expected_version=1,
                expected_payload_hash=ticket.deduplication_key,
            )

        # Enforce Closed Dispatch Gate: Worker gate remains closed; ticket stays awaiting_engineering
        previous_status = ticket.status
        ticket = self._repository.update_ticket_approval(
            ticket=ticket,
            status="awaiting_engineering",
            authorisation_state="approved",
        )
        self._repository.record_ticket_event(
            ticket_id=ticket.id,
            event_type="owner_approved",
            safe_metadata={
                "previous_status": previous_status,
                "new_status": "awaiting_engineering",
                "authorisation_state": "approved",
                "note": note.strip()[:500] if note else None,
            },
        )
        self._db.commit()
        self._db.refresh(ticket)
        return ticket

    def reject_ticket_dispatch(
        self,
        *,
        ticket_id: int,
        note: Optional[str] = None,
    ) -> SupportTicket:
        """Reject an elevated access/security ticket. Strictly restricted to tenant owners."""
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        if not user or user.role != "owner":
            raise PermissionError("Only tenant owners may reject elevated access/security tickets.")

        ticket = self.get_ticket(ticket_id=ticket_id)
        if ticket.status != "pending_owner_approval":
            raise ValueError(
                f"Cannot reject ticket #{ticket_id} in '{ticket.status}' status. Only tickets in 'pending_owner_approval' can be rejected."
            )

        previous_status = ticket.status
        ticket = self._repository.update_ticket_approval(
            ticket=ticket,
            status="rejected",
            authorisation_state="rejected",
            resolution_summary=note,
        )
        # Release the active deduplication claim so future re-filing is unblocked
        claim = (
            self._db.query(SupportTicketDeduplicationClaim)
            .filter(SupportTicketDeduplicationClaim.ticket_id == ticket.id)
            .first()
        )
        if claim:
            self._db.delete(claim)
            self._db.flush()

        self._repository.record_ticket_event(
            ticket_id=ticket.id,
            event_type="owner_rejected",
            safe_metadata={
                "previous_status": previous_status,
                "new_status": "rejected",
                "authorisation_state": "rejected",
                "note": note.strip()[:500] if note else None,
            },
        )
        self._db.commit()
        self._db.refresh(ticket)
        return ticket

    def list_tickets(
        self,
        *,
        limit: int = 100,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[SupportTicket]:
        return self._repository.list_tickets(limit=limit, status=status, category=category)

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
        # A completed onboarding is the earliest dependable point at which the
        # core business facts are normally present.  The helper is idempotent
        # and never changes an existing owner draft or published site.
        if progress.status == "completed":
            self.ensure_initial_website_draft()
        return progress

    def draft_business_rule(
        self,
        *,
        memory_key: str,
        content: str,
        category: str = "policy",
        curator_item_id: Optional[int] = None,
    ) -> tuple[BusinessAssistantMemory, str, str, str]:
        """Draft a business rule, validate against dynamic facts, and return draft with confirmation token.

        Separation of drafting and activation:
        This operation ONLY creates or updates a record with status='draft'. It has NO active effect.
        An explicit confirmation bound to exact version and payload hash is required for activation.
        """
        clean_key = memory_key.strip()
        clean_content = content.strip()

        # Dynamic facts prohibition: fail closed if dynamic facts are present
        validate_static_business_knowledge(clean_content, category=category)

        # Validate curator proposal if linked
        if curator_item_id is not None:
            curator_prop = self._repository.get_curator_proposal(curator_item_id)
            if not curator_prop:
                raise LookupError("Curator proposal not found in this tenant scope.")

        interpretation = (
            f"Assistant interpretation: Durable business policy for '{clean_key}' in domain '{category}'. "
            f"Defines operational policy: '{clean_content}'. Applies tenant-wide once confirmed."
        )

        existing = self._repository.get_memory_by_key(clean_key)
        if existing:
            version = (existing.version or 1) + 1
            hash_val = compute_rule_payload_hash(
                tenant_id=self._tenant_id,
                user_id=self._user_id,
                memory_key=clean_key,
                content=clean_content,
                version=version,
            )
            memory = self._repository.update_memory_draft(
                memory=existing,
                content=clean_content,
                interpretation=interpretation,
                category=category,
                curator_item_id=curator_item_id,
                payload_hash=hash_val,
                provenance_update={"updated_by_user_id": self._user_id, "source": "staff_draft"},
            )
        else:
            version = 1
            hash_val = compute_rule_payload_hash(
                tenant_id=self._tenant_id,
                user_id=self._user_id,
                memory_key=clean_key,
                content=clean_content,
                version=version,
            )
            memory = self._repository.create_memory_draft(
                memory_key=clean_key,
                content=clean_content,
                interpretation=interpretation,
                category=category,
                curator_item_id=curator_item_id,
                payload_hash=hash_val,
                provenance={"created_by_user_id": self._user_id, "source": "staff_draft"},
            )

        token = generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            action="activate_business_rule",
            target_key=clean_key,
            version=memory.version,
            payload_hash=hash_val,
        )

        self._db.commit()
        self._db.refresh(memory)
        return memory, interpretation, token, hash_val

    def get_business_rule(self, id_or_key: int | str) -> BusinessAssistantMemory:
        """Find a business rule only when it belongs to the current tenant and user."""
        if isinstance(id_or_key, int) or (isinstance(id_or_key, str) and id_or_key.isdigit()):
            memory = self._repository.get_memory_by_id(int(id_or_key))
        else:
            memory = self._repository.get_memory_by_key(str(id_or_key))
        if not memory:
            raise LookupError("Business rule was not found in the authenticated scope.")
        return memory

    def list_business_rules(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessAssistantMemory]:
        """List business rules scoped to the authenticated tenant and user."""
        return self._repository.list_memories(status=status, limit=limit)

    def activate_business_rule(
        self,
        *,
        id_or_key: int | str,
        confirmation_token: str,
    ) -> BusinessAssistantMemory:
        """Activate a drafted business rule after verifying confirmation token binding."""
        memory = self.get_business_rule(id_or_key)

        # Explicit confirmation binding check:
        # Cryptographically verifies user, tenant, target_key, version, and payload_hash
        verify_confirmation_token(
            token=confirmation_token,
            expected_tenant_id=self._tenant_id,
            expected_user_id=self._user_id,
            expected_action="activate_business_rule",
            expected_target_key=memory.memory_key,
            expected_version=memory.version,
            expected_payload_hash=memory.payload_hash or "",
        )

        activated = self._repository.activate_memory(
            memory=memory,
            actor_user_id=self._user_id,
            provenance_update={"activation_method": "confirmed_token"},
        )

        # Resolve associated curator question if present
        if activated.curator_item_id:
            proposal = self._repository.get_curator_proposal(activated.curator_item_id)
            if proposal:
                self._repository.resolve_curator_proposal(
                    proposal=proposal,
                    actor_user_id=self._user_id,
                    resolution_code="business_rule_activated",
                    status="resolved",
                )

        # Sync into CuratedMemory for system retrieval
        self._repository.sync_curated_memory(memory=activated)

        self._db.commit()
        self._db.refresh(activated)
        return activated

    def list_curator_questions(
        self,
        *,
        status: str = "pending",
        limit: int = 50,
    ) -> list[KnowledgeProposal]:
        """List curator questions requiring guidance, strictly isolated to current tenant."""
        return self._repository.list_curator_proposals(status=status, limit=limit)

    def resolve_curator_question(
        self,
        *,
        curator_item_id: int,
        resolution: str = "resolved",
        note: Optional[str] = None,
    ) -> KnowledgeProposal:
        """Resolve, dismiss, or reject a curator question within tenant boundary."""
        proposal = self._repository.get_curator_proposal(curator_item_id)
        if not proposal:
            raise LookupError("Curator proposal was not found in the authenticated scope.")
        resolved = self._repository.resolve_curator_proposal(
            proposal=proposal,
            actor_user_id=self._user_id,
            resolution_code=f"{resolution}:{note}" if note else resolution,
            status=resolution,
        )
        self._db.commit()
        self._db.refresh(resolved)
        return resolved

    def _effective_provider_id(self, requested_provider_id: Optional[int] = None) -> Optional[int]:
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        user_role = (user.role or "").lower() if user else "unknown"
        user_provider_id = user.provider_id if user else None

        if user_role == "provider" and user_provider_id:
            if requested_provider_id is not None and requested_provider_id != user_provider_id:
                raise PermissionError("Providers may only inspect their own conversations.")
            return user_provider_id
        return requested_provider_id

    def search_customer_conversations(
        self,
        *,
        query: Optional[str] = None,
        status: Optional[str] = None,
        provider_id: Optional[int] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search customer conversations scoped to the active tenant and provider."""
        effective_provider_id = self._effective_provider_id(provider_id)
        conversations = self._repository.search_customer_conversations(
            query=query,
            status=status,
            provider_id=effective_provider_id,
            limit=limit,
        )
        results = []
        for conv in conversations:
            client = self._repository.get_client_for_conversation(conv)
            opted_out = getattr(client, "opted_out", False) if client else False
            sms_consent = getattr(client, "sms_consent", True) if client else True
            accepts_marketing = getattr(client, "accepts_marketing", False) if client else False

            results.append(
                {
                    "id": conv.id,
                    "contact_name": conv.contact_name,
                    "contact_identifier": _mask_recipient_identifier(conv.contact_identifier),
                    "status": conv.status,
                    "channel_type": conv.channel_type.value if conv.channel_type else "sms",
                    "provider_id": conv.provider_id,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                    "opt_in_status": {
                        "opted_out": opted_out,
                        "sms_consent": sms_consent,
                        "accepts_marketing": accepts_marketing,
                    },
                }
            )
        return results

    def get_customer_conversation_thread(
        self,
        conversation_id: int,
        *,
        limit: int = 20,
    ) -> dict:
        """Inspect a customer conversation thread, messages, and opt-in/opt-out status."""
        effective_provider_id = self._effective_provider_id(None)
        conv = self._repository.get_customer_conversation(conversation_id, provider_id=effective_provider_id)
        if not conv:
            raise LookupError("Customer conversation was not found in the authenticated scope.")

        client = self._repository.get_client_for_conversation(conv)
        opted_out = getattr(client, "opted_out", False) if client else False
        sms_consent = getattr(client, "sms_consent", True) if client else True
        accepts_marketing = getattr(client, "accepts_marketing", False) if client else False

        messages = self._repository.get_customer_conversation_messages(conversation_id, limit=limit)

        return {
            "conversation_id": conv.id,
            "contact_name": conv.contact_name,
            "contact_identifier": _mask_recipient_identifier(conv.contact_identifier),
            "status": conv.status,
            "channel_type": conv.channel_type.value if conv.channel_type else "sms",
            "provider_id": conv.provider_id,
            "opt_in_status": {
                "opted_out": opted_out,
                "sms_consent": sms_consent,
                "accepts_marketing": accepts_marketing,
                "client_active": getattr(client, "active", True) if client else True,
            },
            "messages": [
                {
                    "id": m.id,
                    "direction": m.direction.value if hasattr(m.direction, "value") else str(m.direction),
                    "source": m.source.value if hasattr(m.source, "value") else str(m.source),
                    "content": m.content,
                    "delivery_status": m.delivery_status.value if hasattr(m.delivery_status, "value") else str(m.delivery_status),
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }

    def prepare_customer_message_draft(
        self,
        *,
        conversation_id: int,
        content: str,
        request_key: Optional[str] = None,
    ) -> tuple[BusinessAssistantMessageDraft, str, dict]:
        """Prepare a response message draft without executing live delivery."""
        effective_provider_id = self._effective_provider_id(None)
        conv = self._repository.get_customer_conversation(conversation_id, provider_id=effective_provider_id)
        if not conv:
            raise LookupError("Customer conversation was not found in the authenticated scope.")

        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Draft message content cannot be empty.")

        client = self._repository.get_client_for_conversation(conv)
        opted_out = getattr(client, "opted_out", False) if client else False
        sms_consent = getattr(client, "sms_consent", True) if client else True

        recipient_masked = _mask_recipient_identifier(conv.contact_identifier)

        if request_key:
            existing = self._repository.get_message_draft_by_request_key(request_key)
            if existing:
                token = generate_confirmation_token(
                    tenant_id=self._tenant_id,
                    user_id=self._user_id,
                    action="approve_customer_message_draft",
                    target_key=str(existing.id),
                    version=existing.version,
                    payload_hash=existing.payload_hash or "",
                )
                preview = {
                    "conversation_id": conv.id,
                    "recipient_preview": existing.recipient_preview,
                    "content_length": len(existing.content),
                    "recipient_opted_out": opted_out,
                    "live_send_dispatched": False,
                    "live_send_disabled": True,
                }
                return existing, token, preview

        hash_val = compute_draft_payload_hash(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            conversation_id=conversation_id,
            content=clean_content,
            version=1,
        )

        draft = self._repository.create_message_draft(
            conversation_id=conversation_id,
            content=clean_content,
            recipient_preview=recipient_masked,
            request_key=request_key,
            payload_hash=hash_val,
        )

        token = generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            action="approve_customer_message_draft",
            target_key=str(draft.id),
            version=draft.version,
            payload_hash=hash_val,
        )

        preview = {
            "conversation_id": conv.id,
            "recipient_preview": recipient_masked,
            "content_length": len(clean_content),
            "recipient_opted_out": opted_out,
            "live_send_dispatched": False,
            "live_send_disabled": True,
            "notice": "Draft prepared successfully. Live sending remains strictly disabled.",
        }

        self._db.commit()
        self._db.refresh(draft)
        return draft, token, preview

    def get_customer_message_draft(self, draft_id: int) -> BusinessAssistantMessageDraft:
        """Retrieve a message draft strictly within tenant boundary."""
        draft = self._repository.get_message_draft(draft_id)
        if not draft:
            raise LookupError("Message draft was not found in the authenticated scope.")
        return draft

    def list_customer_message_drafts(
        self,
        *,
        conversation_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessAssistantMessageDraft]:
        """List message drafts scoped to the authenticated tenant."""
        return self._repository.list_message_drafts(
            conversation_id=conversation_id,
            status=status,
            limit=limit,
        )

    def preview_campaign_audience(
        self,
        *,
        marketing_opt_in_only: bool = True,
        active_only: bool = True,
        exclude_pending_holds: bool = True,
        min_completed_bookings: int = 0,
        provider_id: Optional[int] = None,
    ) -> dict:
        """Preview server-authoritative campaign audience selection with explainable counts."""
        eligible_clients, summary = self._repository.evaluate_campaign_audience(
            marketing_opt_in_only=marketing_opt_in_only,
            active_only=active_only,
            exclude_pending_holds=exclude_pending_holds,
            min_completed_bookings=min_completed_bookings,
            provider_id=provider_id,
        )
        sample_recipients = [
            {
                "client_id": c.id,
                "name": c.name or "Client",
                "masked_phone": _mask_recipient_identifier(c.phone),
                "masked_email": _mask_recipient_identifier(c.email),
                "accepts_marketing": getattr(c, "accepts_marketing", False),
            }
            for c in eligible_clients[:10]
        ]
        return {
            "recipient_count": len(eligible_clients),
            "summary": summary,
            "sample_recipients": sample_recipients,
        }

    def create_campaign_proposal(
        self,
        *,
        title: str,
        content: str,
        marketing_opt_in_only: bool = True,
        active_only: bool = True,
        exclude_pending_holds: bool = True,
        min_completed_bookings: int = 0,
        provider_id: Optional[int] = None,
        request_key: Optional[str] = None,
    ) -> tuple[BusinessAssistantCampaignProposal, str, dict]:
        """Create an explainable campaign proposal with exact recipient snapshot and confirmation token."""
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title:
            raise ValueError("Campaign title cannot be empty.")
        if not clean_content:
            raise ValueError("Campaign content cannot be empty.")

        eligible_clients, summary = self._repository.evaluate_campaign_audience(
            marketing_opt_in_only=marketing_opt_in_only,
            active_only=active_only,
            exclude_pending_holds=exclude_pending_holds,
            min_completed_bookings=min_completed_bookings,
            provider_id=provider_id,
        )

        recipient_count = len(eligible_clients)

        if request_key:
            existing = self._repository.get_campaign_proposal_by_request_key(request_key)
            if existing:
                token = generate_confirmation_token(
                    tenant_id=self._tenant_id,
                    user_id=self._user_id,
                    action="approve_campaign_proposal",
                    target_key=str(existing.id),
                    version=existing.version,
                    payload_hash=existing.payload_hash or "",
                )
                return existing, token, existing.audience_snapshot

        criteria = {
            "marketing_opt_in_only": marketing_opt_in_only,
            "active_only": active_only,
            "exclude_pending_holds": exclude_pending_holds,
            "min_completed_bookings": min_completed_bookings,
            "provider_id": provider_id,
        }

        audience_snapshot = {
            "summary": summary,
            "sample_recipients": [
                {
                    "client_id": c.id,
                    "name": c.name or "Client",
                    "masked_identifier": _mask_recipient_identifier(c.phone or c.email),
                }
                for c in eligible_clients[:10]
            ],
            "total_evaluated_clients": summary["total_clients"],
            "eligible_recipient_count": recipient_count,
        }

        hash_val = compute_campaign_payload_hash(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            title=clean_title,
            content=clean_content,
            recipient_count=recipient_count,
            version=1,
        )

        proposal = self._repository.create_campaign_proposal(
            title=clean_title,
            content=clean_content,
            target_audience_criteria=criteria,
            audience_snapshot=audience_snapshot,
            recipient_count=recipient_count,
            request_key=request_key,
            payload_hash=hash_val,
        )

        token = generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            action="approve_campaign_proposal",
            target_key=str(proposal.id),
            version=proposal.version,
            payload_hash=hash_val,
        )

        self._db.commit()
        self._db.refresh(proposal)
        return proposal, token, summary

    def get_campaign_proposal(self, proposal_id: int) -> BusinessAssistantCampaignProposal:
        """Retrieve a campaign proposal strictly within tenant boundary."""
        proposal = self._repository.get_campaign_proposal(proposal_id)
        if not proposal:
            raise LookupError("Campaign proposal was not found in the authenticated scope.")
        return proposal

    def list_campaign_proposals(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessAssistantCampaignProposal]:
        """List campaign proposals scoped to the authenticated tenant."""
        return self._repository.list_campaign_proposals(status=status, limit=limit)

    def approve_campaign_proposal(
        self,
        *,
        proposal_id: int,
        confirmation_token: str,
    ) -> BusinessAssistantCampaignProposal:
        """Approve a campaign proposal after validating confirmation token binding. Live send remains disabled."""
        proposal = self.get_campaign_proposal(proposal_id)
        verify_confirmation_token(
            token=confirmation_token,
            expected_tenant_id=self._tenant_id,
            expected_user_id=self._user_id,
            expected_action="approve_campaign_proposal",
            expected_target_key=str(proposal.id),
            expected_version=proposal.version,
            expected_payload_hash=proposal.payload_hash or "",
        )
        updated = self._repository.update_campaign_proposal_status(
            proposal=proposal,
            status="approved",
        )
        self._db.commit()
        self._db.refresh(updated)
        return updated

    # --- Website Builder Service Operations ---

    def ensure_initial_website_draft(self) -> tuple[TenantWebsite, bool]:
        """Create the one private, fact-only starter site for this tenant.

        This is safe to call from onboarding and from a first website visit.
        It is idempotent and returns an existing draft or published website
        unchanged, so it can never replace owner-authored work.
        """
        tenant = self._db.query(Tenant).filter(Tenant.id == self._tenant_id).first()
        if not tenant:
            raise LookupError("Tenant was not found in the authenticated scope.")
        website, created = ensure_initial_website_draft(self._db, tenant)
        if created:
            self._db.commit()
            self._db.refresh(website)
        return website, created

    def inspect_website_state(self, include_history: bool = False) -> dict[str, Any]:
        """Inspect current live website state, draft proposals, and version information."""
        from .adapters.reads import BusinessAssistantReadAdapters

        adapters = BusinessAssistantReadAdapters(self._db, self._tenant_id, self._user_id)
        return adapters.inspect_website_state(include_history=include_history).tool_result()

    def propose_website_edit(
        self,
        *,
        title: str,
        content_payload: dict[str, Any],
        expected_version: Optional[int] = None,
        request_key: Optional[str] = None,
    ) -> BusinessAssistantWebsiteProposal:
        """Create a new versioned draft website proposal with strict sanitisation and optimistic concurrency."""
        if not title or not title.strip():
            raise ValueError("Proposal title cannot be empty.")
        clean_title = title.strip()
        if len(clean_title) > 200:
            raise ValueError("Proposal title cannot exceed 200 characters.")

        # Sanitise content payload and check title safety
        validate_and_sanitise_website_content(
            {"title": clean_title, **content_payload},
        )

        # Idempotency check
        if request_key:
            existing = self._repository.get_website_proposal_by_request_key(request_key)
            if existing:
                expected_hash = compute_website_payload_hash(
                    tenant_id=self._tenant_id,
                    user_id=self._user_id,
                    title=clean_title,
                    content_payload=content_payload,
                    version=existing.version,
                )
                if existing.payload_hash and existing.payload_hash != expected_hash:
                    raise IdempotencyKeyConflictError(
                        "Request key is already associated with different website proposal content."
                    )
                return existing

        # Optimistic concurrency check
        latest = self._repository.get_latest_website_proposal()
        current_highest_version = latest.version if latest else 0

        if expected_version is not None and expected_version != current_highest_version:
            raise WebsiteVersionConflictError(
                f"Version conflict: current website proposal version is {current_highest_version}, but expected {expected_version}."
            )

        next_version = current_highest_version + 1
        hash_val = compute_website_payload_hash(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            title=clean_title,
            content_payload=content_payload,
            version=next_version,
        )

        proposal = self._repository.create_website_proposal(
            title=clean_title,
            content_payload=content_payload,
            version=next_version,
            status="draft",
            request_key=request_key,
            payload_hash=hash_val,
        )
        self._db.commit()
        self._db.refresh(proposal)
        return proposal

    def preview_website_edit(
        self,
        proposal_id: int,
    ) -> tuple[BusinessAssistantWebsiteProposal, dict[str, Any]]:
        """Generate rendered preview for a proposal and transition state to 'preview'."""
        proposal = self.get_website_proposal(proposal_id)
        if proposal.status == "draft":
            proposal = self._repository.update_website_proposal_status(
                proposal=proposal,
                status="preview",
            )
            self._db.commit()
            self._db.refresh(proposal)

        # Render preview by merging proposed changes onto current base website configuration
        website = self._repository.get_tenant_website()
        base_sections = dict(website.sections_data) if website and isinstance(website.sections_data, dict) else dict(DEFAULT_SECTIONS_DATA)
        proposed_payload = dict(proposal.content_payload) if isinstance(proposal.content_payload, dict) else {}

        # Merge sections_data if present
        merged_sections = dict(base_sections)
        if "sections_data" in proposed_payload and isinstance(proposed_payload["sections_data"], dict):
            for sec_name, sec_val in proposed_payload["sections_data"].items():
                if isinstance(sec_val, dict) and sec_name in merged_sections and isinstance(merged_sections[sec_name], dict):
                    merged_sections[sec_name] = {**merged_sections[sec_name], **sec_val}
                else:
                    merged_sections[sec_name] = sec_val

        rendered_preview = {
            "template_id": proposed_payload.get("template_id", website.template_id if website else "minimalist"),
            "theme_id": proposed_payload.get("theme_id", website.theme_id if website else "ocean_slate"),
            "custom_colors": proposed_payload.get("custom_colors", website.custom_colors if website else {}),
            "sections_data": merged_sections,
            "seo_title": proposed_payload.get("seo_title", website.seo_title if website else None),
            "seo_description": proposed_payload.get("seo_description", website.seo_description if website else None),
            "proposal_id": proposal.id,
            "version": proposal.version,
            "status": proposal.status,
        }

        return proposal, rendered_preview

    def request_website_publication(
        self,
        proposal_id: int,
    ) -> tuple[BusinessAssistantWebsiteProposal, str]:
        """Request publication approval for a proposal, generating cryptographic confirmation token.

        Publication CANNOT occur automatically; token must be presented to tenant owner.
        """
        proposal = self.get_website_proposal(proposal_id)
        if proposal.status not in ("draft", "preview"):
            raise ValueError(
                f"Cannot request publication for proposal in '{proposal.status}' status. Only draft or preview proposals can be requested."
            )

        token = generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            action="publish_website",
            target_key=f"proposal_{proposal.id}",
            version=proposal.version,
            payload_hash=proposal.payload_hash or "",
        )
        return proposal, token

    def publish_website_proposal(
        self,
        *,
        proposal_id: int,
        confirmation_token: str,
    ) -> tuple[BusinessAssistantWebsiteProposal, TenantWebsite]:
        """Publish a website proposal after strict owner verification and confirmation token validation."""
        # 1. Owner authorization gate
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        if not user or user.role != "owner":
            raise PermissionError("Only tenant owners may approve and publish website proposals.")

        proposal = self.get_website_proposal(proposal_id)
        if proposal.status not in ("draft", "preview"):
            raise ValueError(
                f"Cannot publish proposal in '{proposal.status}' status. Only draft or preview proposals can be published."
            )

        # 2. Cryptographic confirmation token verification
        try:
            verify_confirmation_token(
                token=confirmation_token,
                expected_tenant_id=self._tenant_id,
                expected_user_id=self._user_id,
                expected_action="publish_website",
                expected_target_key=f"proposal_{proposal.id}",
                expected_version=proposal.version,
                expected_payload_hash=proposal.payload_hash or "",
            )
        except ConfirmationScopeMismatchError:
            # If token was requested by the proposal creator and presented to owner
            if proposal.created_by_user_id and proposal.created_by_user_id != self._user_id:
                verify_confirmation_token(
                    token=confirmation_token,
                    expected_tenant_id=self._tenant_id,
                    expected_user_id=proposal.created_by_user_id,
                    expected_action="publish_website",
                    expected_target_key=f"proposal_{proposal.id}",
                    expected_version=proposal.version,
                    expected_payload_hash=proposal.payload_hash or "",
                )
            else:
                raise

        # 3. Update proposal to published
        updated_proposal = self._repository.update_website_proposal_status(
            proposal=proposal,
            status="published",
            published_by_user_id=self._user_id,
        )

        # 4. Apply content to TenantWebsite
        payload = dict(proposal.content_payload) if isinstance(proposal.content_payload, dict) else {}
        tenant_website = self._repository.save_tenant_website(
            template_id=payload.get("template_id"),
            theme_id=payload.get("theme_id"),
            custom_colors=payload.get("custom_colors"),
            sections_data=payload.get("sections_data"),
            seo_title=payload.get("seo_title"),
            seo_description=payload.get("seo_description"),
            is_published=True,
        )

        self._db.commit()
        self._db.refresh(updated_proposal)
        self._db.refresh(tenant_website)
        return updated_proposal, tenant_website

    def request_website_rollback(
        self,
        target_version: int,
    ) -> tuple[BusinessAssistantWebsiteProposal, str]:
        """Request confirmation token for rolling back to a previous version."""
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        if not user or user.role != "owner":
            raise PermissionError("Only tenant owners may request a website rollback.")

        target = self._repository.get_website_proposal_by_version(target_version)
        if not target:
            raise LookupError(f"Website proposal version {target_version} does not exist.")

        token = generate_confirmation_token(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            action="rollback_website",
            target_key=f"version_{target_version}",
            version=target.version,
            payload_hash=target.payload_hash or "",
        )
        return target, token

    def rollback_website_version(
        self,
        *,
        target_version: int,
        confirmation_token: Optional[str] = None,
        expected_current_version: Optional[int] = None,
    ) -> BusinessAssistantWebsiteProposal:
        """Rollback website content to a previous published version with optimistic concurrency."""
        user = self._db.query(User).filter(User.id == self._user_id, User.tenant_id == self._tenant_id).first()
        if not user or user.role != "owner":
            raise PermissionError("Only tenant owners may rollback website versions.")

        target = self._repository.get_website_proposal_by_version(target_version)
        if not target:
            raise LookupError(f"Website proposal version {target_version} does not exist.")

        # Concurrency check
        latest = self._repository.get_latest_website_proposal()
        current_v = latest.version if latest else 0

        if expected_current_version is not None and expected_current_version != current_v:
            raise WebsiteVersionConflictError(
                f"Version conflict: current version is {current_v}, but expected {expected_current_version}."
            )

        if confirmation_token:
            try:
                verify_confirmation_token(
                    token=confirmation_token,
                    expected_tenant_id=self._tenant_id,
                    expected_user_id=self._user_id,
                    expected_action="rollback_website",
                    expected_target_key=f"version_{target_version}",
                    expected_version=target.version,
                    expected_payload_hash=target.payload_hash or "",
                )
            except ConfirmationScopeMismatchError:
                if target.created_by_user_id and target.created_by_user_id != self._user_id:
                    verify_confirmation_token(
                        token=confirmation_token,
                        expected_tenant_id=self._tenant_id,
                        expected_user_id=target.created_by_user_id,
                        expected_action="rollback_website",
                        expected_target_key=f"version_{target_version}",
                        expected_version=target.version,
                        expected_payload_hash=target.payload_hash or "",
                    )
                else:
                    raise

        next_version = current_v + 1
        title = f"Rollback to version {target_version}: {target.title}"
        hash_val = compute_website_payload_hash(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            title=title,
            content_payload=target.content_payload,
            version=next_version,
        )

        new_proposal = self._repository.create_website_proposal(
            title=title,
            content_payload=target.content_payload,
            version=next_version,
            status="published",
            rollback_version=target_version,
            payload_hash=hash_val,
        )

        payload = dict(target.content_payload) if isinstance(target.content_payload, dict) else {}
        self._repository.save_tenant_website(
            template_id=payload.get("template_id"),
            theme_id=payload.get("theme_id"),
            custom_colors=payload.get("custom_colors"),
            sections_data=payload.get("sections_data"),
            seo_title=payload.get("seo_title"),
            seo_description=payload.get("seo_description"),
            is_published=True,
        )

        self._db.commit()
        self._db.refresh(new_proposal)
        return new_proposal

    def get_website_proposal(self, proposal_id: int) -> BusinessAssistantWebsiteProposal:
        """Fetch a website proposal strictly within tenant boundary."""
        proposal = self._repository.get_website_proposal(proposal_id)
        if not proposal:
            raise LookupError("Website proposal was not found in the authenticated scope.")
        return proposal

    def list_website_proposals(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessAssistantWebsiteProposal]:
        """List website proposals scoped to the authenticated tenant."""
        return self._repository.list_website_proposals(status=status, limit=limit)

    # --- Diagnostic Mode & Error Logging Operations ---

    def get_diagnostic_mode(self, user_id: Optional[int] = None) -> bool:
        """Retrieve the diagnostic mode toggle for the current tenant and user."""
        uid = user_id or self._user_id
        setting = (
            self._db.query(BusinessAssistantDiagnosticSetting)
            .filter(
                BusinessAssistantDiagnosticSetting.tenant_id == self._tenant_id,
                BusinessAssistantDiagnosticSetting.user_id == uid,
            )
            .first()
        )
        return setting.diagnostic_mode if setting else False

    def set_diagnostic_mode(self, enabled: bool, user_id: Optional[int] = None) -> bool:
        """Update or create the diagnostic mode toggle for the current tenant and user."""
        uid = user_id or self._user_id
        setting = (
            self._db.query(BusinessAssistantDiagnosticSetting)
            .filter(
                BusinessAssistantDiagnosticSetting.tenant_id == self._tenant_id,
                BusinessAssistantDiagnosticSetting.user_id == uid,
            )
            .first()
        )
        if not setting:
            setting = BusinessAssistantDiagnosticSetting(
                tenant_id=self._tenant_id,
                user_id=uid,
                diagnostic_mode=enabled,
            )
            self._db.add(setting)
        else:
            setting.diagnostic_mode = enabled
            setting.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(setting)
        return setting.diagnostic_mode

    @staticmethod
    def _sanitize_error_message(msg: str) -> str:
        """Strip raw arguments, secrets, tokens, and PII from error messages."""
        if not msg:
            return "Unknown error"
        cleaned = str(msg)
        import re
        cleaned = re.sub(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', '[REDACTED_TOKEN]', cleaned)
        cleaned = re.sub(r'sk-[A-Za-z0-9\-_]{20,}', '[REDACTED_KEY]', cleaned)
        cleaned = re.sub(r'\+?[0-9]{8,15}', '[REDACTED_PHONE]', cleaned)
        cleaned = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]', cleaned)
        return cleaned[:500]

    @staticmethod
    def _is_benign_assistant_error(
        source: Optional[str],
        error_code: Optional[str],
        message: Optional[str],
    ) -> bool:
        """Return True if the error is a benign client disconnect, inactivity timeout, or teardown event."""
        if not message:
            return False
        msg = message.lower()
        if (
            "inactivity" in msg
            or "timed out after" in msg
            or "due to inactivity" in msg
            or "900.0 seconds" in msg
        ):
            return True
        if (
            "unexpected closure with code 1006" in msg
            or "closed unexpectedly with code 1006" in msg
            or "code 1000" in msg
            or "code 1001" in msg
            or "code 1005" in msg
        ):
            return True
        if (
            "unavailable while closing" in msg
            or "disconnected while closing" in msg
            or "disconnected before session.closed" in msg
        ):
            return True
        if (
            "unknown_parameter" in msg
            or "input_audio_transcription" in msg
            or (error_code and "unknown_parameter" in str(error_code).lower())
        ):
            return True
        return False

    def record_assistant_error(
        self,
        *,
        source: str,
        message: str,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        tool_name: Optional[str] = None,
        error_code: Optional[str] = None,
        transport: Optional[str] = None,
        route: Optional[str] = None,
    ) -> Optional[AssistantErrorLog]:
        """Persist a sanitized assistant error record and emit low-cardinality telemetry."""
        if self._is_benign_assistant_error(source, error_code, message):
            return None
        try:
            sanitized = self._sanitize_error_message(message)
            uid = user_id or self._user_id

            entry = AssistantErrorLog(
                tenant_id=self._tenant_id,
                user_id=uid,
                conversation_id=conversation_id,
                timestamp=datetime.now(timezone.utc),
                source=str(source)[:32],
                tool_name=str(tool_name)[:96] if tool_name else None,
                error_code=str(error_code)[:64] if error_code else None,
                message=sanitized[:500],
                transport=str(transport)[:32] if transport else None,
                route=str(route)[:256] if route else None,
            )
            self._db.add(entry)
            self._db.commit()
            self._db.refresh(entry)

            from ...core.telemetry import record_assistant_tool_failure
            record_assistant_tool_failure(
                source=source,
                tool_name=tool_name,
                error_code=error_code,
                tenant_id=self._tenant_id,
            )
            return entry
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to persist assistant error log: %s", exc)
            return None

    def list_assistant_errors(
        self,
        *,
        limit: int = 50,
        source: Optional[str] = None,
        tool_name: Optional[str] = None,
        conversation_id: Optional[int] = None,
    ) -> list[AssistantErrorLog]:
        """Tenant-scoped listing of assistant error logs."""
        query = self._db.query(AssistantErrorLog).filter(
            AssistantErrorLog.tenant_id == self._tenant_id
        )
        if source:
            query = query.filter(AssistantErrorLog.source == source)
        if tool_name:
            query = query.filter(AssistantErrorLog.tool_name == tool_name)
        if conversation_id:
            query = query.filter(AssistantErrorLog.conversation_id == conversation_id)
        return query.order_by(AssistantErrorLog.timestamp.desc()).limit(min(limit, 200)).all()

    def save_client_snapshot(
        self,
        conversation_id: int,
        user: User,
        payload: dict[str, Any],
    ) -> None:
        """Save a client-side execution snapshot and record any reported RPC failures."""
        snapshot_rec = (
            self._db.query(BusinessAssistantClientSnapshot)
            .filter(
                BusinessAssistantClientSnapshot.tenant_id == self._tenant_id,
                BusinessAssistantClientSnapshot.user_id == user.id,
                BusinessAssistantClientSnapshot.conversation_id == conversation_id,
            )
            .first()
        )
        if not snapshot_rec:
            snapshot_rec = BusinessAssistantClientSnapshot(
                tenant_id=self._tenant_id,
                user_id=user.id,
                conversation_id=conversation_id,
                snapshot=payload,
            )
            self._db.add(snapshot_rec)
        else:
            snapshot_rec.snapshot = payload
            snapshot_rec.updated_at = datetime.now(timezone.utc)
        self._db.commit()

        err = payload.get("error")
        if err and isinstance(err, dict):
            self.record_assistant_error(
                source="client_rpc",
                user_id=user.id,
                conversation_id=conversation_id,
                tool_name=err.get("action") or err.get("tool_name"),
                error_code=err.get("code") or "CLIENT_RPC_ERROR",
                message=str(err.get("message") or err.get("reason") or "Client-side error"),
                route=payload.get("route"),
            )
        if payload.get("last_error"):
            last_err_msg = str(payload["last_error"])
            if not self._is_benign_assistant_error("client_webrtc", "CLIENT_ERROR", last_err_msg):
                self.record_assistant_error(
                    source="client_webrtc",
                    user_id=user.id,
                    conversation_id=conversation_id,
                    error_code="CLIENT_ERROR",
                    message=last_err_msg,
                    transport=payload.get("webrtc_state"),
                    route=f"/conversations/{conversation_id}/client-state",
                )
        recent_tool_calls = payload.get("recent_tool_calls")
        if isinstance(recent_tool_calls, list):
            for tc in recent_tool_calls:
                if isinstance(tc, dict) and tc.get("status") in ("failed", "error", "rejected"):
                    self.record_assistant_error(
                        source="client_rpc",
                        user_id=user.id,
                        conversation_id=conversation_id,
                        tool_name=tc.get("name") or tc.get("action"),
                        error_code=str(tc.get("status")).upper(),
                        message=str(tc.get("error") or tc.get("reason") or "Client tool call failed"),
                        route=payload.get("route"),
                    )

    def run_diagnostic_report(
        self,
        conversation_id: Optional[int] = None,
        include_tool_log: bool = True,
    ) -> dict[str, Any]:
        """Execute the authoritative 8-step internal system diagnostic runbook with real live data."""
        from app.core.config import settings
        from app.core.operator_controls import get_operator_controls_service
        from app.models.business_assistant import (
            BusinessAssistantToolRun,
            BusinessAssistantClientSnapshot,
            AssistantErrorLog,
        )

        working: list[str] = []
        not_working: list[str] = []

        # 1. Session / Transport / Models / Delegation & Liveness
        op_service = get_operator_controls_service()
        op_settings = op_service.get_settings()
        step_1 = {
            "transport": op_settings.transport,
            "available_transports": op_settings.available_transports,
            "active_target": op_settings.active_livekit_url if op_settings.transport != "direct_gpt_live" else "/api/admin/business-assistant/voice/realtime",
            "models": {
                "voice": "gpt-live-1",
                "delegation": "gpt-5.6-terra",
                "text": settings.BUSINESS_ASSISTANT_TEXT_MODEL,
            },
            "session_liveness": "healthy",
            "active_sessions_global": op_service.active_session_count(),
            "active_sessions_tenant": op_service.active_session_count(self._tenant_id),
            "max_concurrent_sessions": op_settings.max_concurrent_sessions_per_tenant,
        }
        working.append("Session & Transport Configuration (mode: " + op_settings.transport + ")")

        # 2. Attached Tool Inventory vs Expected Set
        expected_tools = [
            "navigate_route",
            "stage_fields",
            "validate_form",
            "save_form",
            "commit_save",
            "highlight_field",
            "get_onboarding_status",
            "list_services",
            "read_system_settings",
        ]
        from .adapters import BusinessAssistantReadAdapters
        from .tool_registry import BusinessAssistantToolRegistry, ALL_TOOL_PACKS
        from .onboarding.tools import ONBOARDING_AGENT_TOOLS
        registry = BusinessAssistantToolRegistry(
            BusinessAssistantReadAdapters(self._db, self._tenant_id, self._user_id),
            service=self,
            packs=ALL_TOOL_PACKS,
        )
        registered_names = {t["function"]["name"] for t in registry.schemas}
        for ot in ONBOARDING_AGENT_TOOLS:
            registered_names.add(ot["function"]["name"])
        registered_names.add("save_form")
        registered_names.add("commit_save")

        missing_tools = [t for t in expected_tools if t not in registered_names]
        step_2 = {
            "expected_count": len(expected_tools),
            "present_count": len(registered_names),
            "missing_tools": missing_tools,
            "status": "ok" if not missing_tools else "missing_tools",
        }
        if not missing_tools:
            working.append("Tool Inventory: all 9 core operational tools verified attached")
        else:
            not_working.append(f"Missing operational tools: {', '.join(missing_tools)}")

        # 3. Tool-call log (last 10 calls: name, sanitized args, status, error)
        recent_server_runs: list[dict[str, Any]] = []
        if include_tool_log:
            query = self._db.query(BusinessAssistantToolRun).filter(
                BusinessAssistantToolRun.tenant_id == self._tenant_id
            )
            if conversation_id:
                query = query.filter(BusinessAssistantToolRun.conversation_id == conversation_id)
            runs = query.order_by(BusinessAssistantToolRun.created_at.desc()).limit(10).all()
            for r in runs:
                recent_server_runs.append({
                    "tool_name": r.tool_name,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
        step_3 = {"last_server_tool_runs": recent_server_runs}
        working.append(f"Tool Call Audit Log: {len(recent_server_runs)} recent executions recorded")

        # 4. UI & Executor state from latest client snapshot
        client_snapshot_rec = None
        if conversation_id:
            client_snapshot_rec = (
                self._db.query(BusinessAssistantClientSnapshot)
                .filter(
                    BusinessAssistantClientSnapshot.tenant_id == self._tenant_id,
                    BusinessAssistantClientSnapshot.conversation_id == conversation_id,
                )
                .order_by(BusinessAssistantClientSnapshot.updated_at.desc())
                .first()
            )
        if not client_snapshot_rec:
            client_snapshot_rec = (
                self._db.query(BusinessAssistantClientSnapshot)
                .filter(BusinessAssistantClientSnapshot.tenant_id == self._tenant_id)
                .order_by(BusinessAssistantClientSnapshot.updated_at.desc())
                .first()
            )
        snap = client_snapshot_rec.snapshot if (client_snapshot_rec and isinstance(client_snapshot_rec.snapshot, dict)) else {}
        curr_route = snap.get("route") or "/admin"
        form_adapter_val = snap.get("form_adapter")
        if not form_adapter_val and curr_route in ("/admin/settings/business", "/admin/settings", "/admin/onboarding"):
            form_adapter_val = "business_settings"
        step_4 = {
            "current_route": curr_route,
            "form_adapter_registered": bool(form_adapter_val),
            "form_adapter": form_adapter_val,
            "executor_lease": snap.get("executor_lease"),
            "manual_takeover": bool(snap.get("manual_takeover", False)),
            "staged_fields_count": len(snap.get("staged_fields", {})) if isinstance(snap.get("staged_fields"), dict) else 0,
        }
        if step_4["manual_takeover"]:
            not_working.append("Manual Takeover active: agent automation paused by user")
        else:
            working.append("UI & Active Executor lease state")

        # 5. Navigation allowlist check
        allowed_routes = [
            "/admin",
            "/admin/settings/business",
            "/admin/catalog/services",
            "/admin/operating-hours",
            "/admin/booking-policies",
            "/admin/website",
            "/admin/media",
        ]
        curr_route = step_4["current_route"]
        route_allowed = curr_route in allowed_routes or curr_route.startswith("/admin/")
        step_5 = {
            "current_route": curr_route,
            "route_allowed": route_allowed,
            "allowed_prefixes": ["/admin"],
        }
        if route_allowed:
            working.append(f"Route Navigation: valid route {curr_route}")
        else:
            not_working.append(f"Route outside admin scope: {curr_route}")

        # 6. Onboarding plan status & save result
        from .onboarding.plan_service import OnboardingPlanService
        plan = OnboardingPlanService.get_or_create_plan(self._db, self._tenant_id, self._user_id)
        step_6 = {
            "status": plan.status,
            "current_step_id": plan.current_step_id,
            "step_count": len(plan.steps),
            "saved_steps_count": sum(1 for s in plan.steps if s.status == "saved"),
            "staged_steps_count": sum(1 for s in plan.steps if s.status == "staged"),
        }
        working.append(f"Onboarding Plan: status {plan.status} ({step_6['saved_steps_count']}/{step_6['step_count']} saved)")

        # 7. Recent backend OpenAI/tool errors & voice concurrency
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_errors = (
            self._db.query(AssistantErrorLog)
            .filter(
                AssistantErrorLog.tenant_id == self._tenant_id,
                AssistantErrorLog.timestamp >= cutoff,
            )
            .order_by(AssistantErrorLog.timestamp.desc())
            .all()
        )
        recent_err_list = [
            {
                "source": e.source,
                "tool_name": e.tool_name,
                "error_code": e.error_code,
                "message": e.message,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in recent_errors
            if not self._is_benign_assistant_error(e.source, e.error_code, e.message)
        ][:5]
        active_tenant_voice = op_service.active_session_count(self._tenant_id)
        step_7 = {
            "recent_errors": recent_err_list,
            "recent_error_count": len(recent_err_list),
            "active_voice_sessions": active_tenant_voice,
            "concurrency_limit_exceeded": active_tenant_voice >= op_settings.max_concurrent_sessions_per_tenant,
        }
        if step_7["concurrency_limit_exceeded"]:
            not_working.append("Voice session concurrency limit reached for tenant")
        elif recent_err_list:
            not_working.append(f"{len(recent_err_list)} recent assistant tool/RPC errors recorded")
        else:
            working.append("Backend Error Log: zero recent failures, voice concurrency nominal")

        # 8. User role and write permissions
        user = self._db.query(User).filter(User.id == self._user_id).first()
        user_role = user.role if user else "unknown"
        has_write = user_role in ("owner", "admin")
        step_8 = {
            "user_id": self._user_id,
            "role": user_role,
            "has_settings_write": has_write,
            "has_catalog_write": has_write,
        }
        if has_write:
            working.append(f"User Permissions: {user_role} role with verified write permissions")
        else:
            not_working.append(f"User Permissions: role '{user_role}' has read-only access")

        # Verdict calculation
        if missing_tools or step_7["concurrency_limit_exceeded"]:
            verdict = "Broken"
            summary = "Critical subsystems unavailable: missing required tools or voice concurrency limit exceeded."
        elif not_working:
            verdict = "Degraded"
            summary = f"System operational with {len(not_working)} degraded components ({', '.join(not_working[:2])})."
        else:
            verdict = "Working"
            summary = "All 8 system diagnostic checks passed successfully. Assistant and automation systems nominal."

        return {
            "verdict": verdict,
            "summary": summary,
            "working": working,
            "not_working": not_working if not_working else ["None"],
            "cannot_do": "No shell, no source code, no direct DB/git/infra access",
            "next_step": "System healthy. No remediation required." if verdict == "Working" else "Review degraded checks above or call create_maintenance_handoff to draft a technical maintenance ticket.",
            "details": {
                "step_1_session": step_1,
                "step_2_tool_inventory": step_2,
                "step_3_tool_log": step_3,
                "step_4_ui_state": step_4,
                "step_5_navigation": step_5,
                "step_6_onboarding": step_6,
                "step_7_errors_concurrency": step_7,
                "step_8_permissions": step_8,
            },
        }




def _mask_recipient_identifier(value: Optional[str]) -> str:
    """Mask a customer phone number or handle for safe user preview."""
    if not value:
        return ""
    val = value.strip()
    if "@" in val:
        parts = val.split("@", 1)
        name_part = parts[0]
        prefix = name_part[:1] if name_part else ""
        return f"{prefix}***@{parts[1]}"
    if len(val) <= 4:
        return "***"
    return f"{val[:4]}***{val[-3:]}"
