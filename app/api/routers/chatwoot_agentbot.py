"""Chatwoot AgentBot webhook router.

Receives AgentBot events from Chatwoot, validates payload integrity,
and determines whether the incoming interaction requires automated AI agent
execution or immediate human agent handoff. Also provides conversation
completion hooks and background task dispatch for memory curation (Mem0 pattern).
"""

import logging
import re
import secrets
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.async_session import async_session_scope, get_async_db
from ...engine.dialogue_graph import process_dialogue_turn
from ...engine.state import AgentState, CustomerLocation, DialogueTurn
from ...models.sms_chatwoot import SmsChatwootBinding
from ...services.curation.memory_curator import CuratorDecision, curate_conversation
from ...services.messaging.chatwoot_handoff import handoff_to_human, send_bot_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chatwoot", tags=["chatwoot-agentbot"])


class ChatwootConversation(BaseModel):
    """Chatwoot conversation summary inside AgentBot event."""

    id: int = Field(..., description="Chatwoot conversation ID")
    inbox_id: Optional[int] = Field(None, description="Chatwoot inbox ID")
    status: Optional[str] = Field(None, description="Current conversation status")

    model_config = ConfigDict(extra="allow")


class ChatwootAccount(BaseModel):
    """Chatwoot account summary inside AgentBot event."""

    id: int = Field(..., description="Chatwoot account ID")
    name: Optional[str] = Field(None, description="Account name")

    model_config = ConfigDict(extra="allow")


class ChatwootSender(BaseModel):
    """Chatwoot sender entity (contact or agent user)."""

    id: Optional[int] = Field(None, description="Sender ID")
    name: Optional[str] = Field(None, description="Sender name")
    email: Optional[str] = Field(None, description="Sender email")
    type: Optional[str] = Field(
        None, description="Sender type: 'contact' (customer) or 'user' (agent)"
    )

    model_config = ConfigDict(extra="allow")


class ChatwootAgentBotPayload(BaseModel):
    """Payload schema for Chatwoot AgentBot webhook events."""

    event: str = Field(..., description="Event type, e.g. message_created")
    id: Optional[int] = Field(None, description="Message ID")
    content: Optional[str] = Field(None, description="Message text content")
    message_type: Optional[str] = Field(
        None, description="Type: 'incoming' from customer, 'outgoing' from staff/bot"
    )
    conversation: ChatwootConversation = Field(..., description="Associated conversation")
    account: ChatwootAccount = Field(..., description="Associated account")
    sender: Optional[ChatwootSender] = Field(None, description="Sender details")
    transcript: Optional[list[dict[str, Any]]] = Field(
        None, description="Optional conversation transcript for resolved events"
    )

    model_config = ConfigDict(extra="allow")


class ConversationCompletionHookPayload(BaseModel):
    """Payload for manual or automated post-conversation curation completion hook."""

    tenant_id: int = Field(..., description="Tenant ID owning the conversation")
    transcript: list[dict[str, Any]] = Field(
        ..., description="Full list of message dicts forming the dialogue transcript"
    )
    provider_id: Optional[int] = Field(
        None, description="Optional provider association"
    )

    model_config = ConfigDict(extra="allow")


# Regex patterns indicating explicit customer request for human assistance
HUMAN_HANDOFF_PATTERNS = [
    r"\bhuman\b",
    r"\bagent\b",
    r"\brepresentative\b",
    r"\boperator\b",
    r"\breal person\b",
    r"\bspeak to (someone|a person|a human|an agent)\b",
    r"\btalk to (someone|a person|a human|an agent)\b",
    r"\bcustomer (service|support)\b",
    r"\blive (agent|support|person)\b",
    r"\bsupervisor\b",
    r"\bescalate\b",
]

_HUMAN_HANDOFF_RE = re.compile("|".join(HUMAN_HANDOFF_PATTERNS), re.IGNORECASE)


def requires_human_handoff(content: Optional[str]) -> bool:
    """Analyze text content to determine if the user requested a human agent.

    Args:
        content: Raw message text from client.

    Returns:
        True if text matches human handoff triggers, False otherwise.
    """
    if not content:
        return False
    return bool(_HUMAN_HANDOFF_RE.search(content.strip()))


async def curate_conversation_background(
    tenant_id: int,
    transcript: list[dict[str, Any]],
    provider_id: Optional[int] = None,
) -> list[CuratorDecision]:
    """Execute background memory curation for a completed conversation."""
    try:
        async with async_session_scope() as session:
            decisions = await curate_conversation(
                tenant_id=tenant_id,
                transcript=transcript,
                db=session,
                provider_id=provider_id,
            )
            logger.info(
                "Background memory curation completed for tenant_id=%s: %d decisions",
                tenant_id,
                len(decisions),
            )
            return decisions
    except Exception as exc:
        logger.error(
            "Background memory curation failed for tenant_id=%s: %s",
            tenant_id,
            exc,
            exc_info=True,
        )
        return []


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def chatwoot_agentbot_webhook(
    payload: ChatwootAgentBotPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    token: Optional[str] = Query(None),
    x_chatwoot_token: Optional[str] = Header(None, alias="X-Chatwoot-Token"),
    x_chatwoot_base_url: Optional[str] = Header(None, alias="X-Chatwoot-Base-Url"),
    x_chatwoot_api_token: Optional[str] = Header(None, alias="X-Chatwoot-Api-Token"),
) -> dict[str, Any]:
    """Handle incoming Chatwoot AgentBot webhook events.

    Validates payload, enforces security secret verification if configured,
    analyzes message content to direct flow between automated agent
    execution and human escalation, and triggers background memory curation
    when conversations resolve.
    """
    # 1. Secret verification if configured
    configured_secret = getattr(settings, "CHATWOOT_WEBHOOK_SECRET", "")
    if configured_secret:
        provided_token = token or x_chatwoot_token
        if not provided_token or not secrets.compare_digest(provided_token, configured_secret):
            logger.warning("Rejecting Chatwoot AgentBot webhook: invalid authentication token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing webhook token",
            )

    # 2. Support conversation resolution background curation trigger
    if payload.event in ("conversation_resolved", "conversation_status_changed"):
        if payload.conversation.status == "resolved" and payload.transcript:
            logger.info(
                "Enqueuing memory curation for resolved conversation=%s account=%s",
                payload.conversation.id,
                payload.account.id,
            )
            background_tasks.add_task(
                curate_conversation_background,
                tenant_id=payload.account.id,
                transcript=payload.transcript,
            )
            return {
                "status": "handled",
                "action": "conversation_curation_enqueued",
                "conversation_id": payload.conversation.id,
                "account_id": payload.account.id,
            }

    # Filter event type and message origin
    if payload.event != "message_created":
        logger.info("Ignoring non-message_created event: %s", payload.event)
        return {
            "status": "ignored",
            "reason": f"unhandled_event_{payload.event}",
        }

    # Only process incoming messages from customers
    if payload.message_type != "incoming":
        logger.info("Ignoring non-incoming message_type: %s", payload.message_type)
        return {
            "status": "ignored",
            "reason": "non_incoming_message",
        }

    if payload.sender and payload.sender.type in ("user", "agent_bot", "bot"):
        logger.info(
            "Ignoring message sent by staff/bot sender id=%s, type=%s",
            payload.sender.id,
            payload.sender.type,
        )
        reason = "staff_message" if payload.sender.type == "user" else "bot_message"
        return {
            "status": "ignored",
            "reason": reason,
        }

    conversation_id = payload.conversation.id
    account_id = payload.account.id
    content = payload.content or ""

    # Determine Chatwoot endpoint and credentials
    base_url = x_chatwoot_base_url or getattr(settings, "CHATWOOT_BASE_URL", "https://app.chatwoot.com")
    api_token = x_chatwoot_api_token or getattr(settings, "CHATWOOT_API_ACCESS_TOKEN", "")

    # 3. Detect intent: Human agent handoff vs AI agent execution
    if requires_human_handoff(content):
        logger.info(
            "Human handoff requested for conversation=%s (content: '%s')",
            conversation_id,
            content,
        )

        # Execute human handoff if token is available
        handoff_details: Optional[dict[str, Any]] = None
        if api_token:
            try:
                handoff_details = await handoff_to_human(
                    chatwoot_base_url=base_url,
                    api_access_token=api_token,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    note=f"Automated Handoff: Customer requested human assistance ('{content}')",
                )
                # Send polite notification to customer
                await send_bot_message(
                    chatwoot_base_url=base_url,
                    api_access_token=api_token,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    content="I have transferred your request to a team member. An agent will be with you shortly!",
                )
            except Exception as exc:
                logger.error(
                    "Error performing live handoff to human for conversation=%s: %s",
                    conversation_id,
                    exc,
                )

        return {
            "status": "handled",
            "action": "human_handoff",
            "conversation_id": conversation_id,
            "account_id": account_id,
            "reason": "Customer requested human agent assistance",
            "handoff_details": handoff_details,
        }

    # 4. Message requires AI agent execution via LangGraph Dialogue Engine
    logger.info(
        "Message routed to automated dialogue engine for conversation=%s",
        conversation_id,
    )

    # Resolve tenant and provider bindings for Chatwoot account
    binding = None
    try:
        binding_stmt = select(SmsChatwootBinding).where(
            SmsChatwootBinding.chatwoot_account_id == account_id
        )
        binding_res = await db.execute(binding_stmt)
        binding = binding_res.scalars().first()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning(
            "Could not query SmsChatwootBinding (%s); falling back to account_id=%s",
            exc,
            account_id,
        )

    resolved_tenant_id = binding.tenant_id if binding else account_id
    resolved_provider_id = binding.provider_id if binding else None

    # Fallback to binding tokens if not passed via headers/settings
    if not api_token and binding and binding.chatwoot_api_token:
        api_token = binding.chatwoot_api_token
    if (
        base_url == "https://app.chatwoot.com"
        and binding
        and binding.chatwoot_base_url
    ):
        base_url = binding.chatwoot_base_url

    sender_name = payload.sender.name if payload.sender else None
    sender_email = payload.sender.email if payload.sender else None

    initial_state: AgentState = {
        "messages": [HumanMessage(content=content)],
        "tenant_id": resolved_tenant_id,
        "provider_id": resolved_provider_id,
        "customer_name": sender_name,
        "customer_email": sender_email,
        "conversation_id": conversation_id,
        "dialogue_turn": DialogueTurn(),
        "should_escalate": False,
    }

    try:
        result_state = await process_dialogue_turn(initial_state, db)
    except Exception as exc:
        logger.error(
            "Unhandled exception executing dialogue turn for conversation=%s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        result_state = initial_state
        result_state["should_escalate"] = False
        result_state["reply_text"] = (
            "I apologize, but I encountered an issue processing your request. "
            "Our team has been notified and will assist you shortly."
        )

    reply_text = result_state.get("reply_text") or (
        "Thank you for contacting us! How can we assist with your massage appointment today?"
    )
    turn = result_state.get("dialogue_turn") or DialogueTurn()
    should_escalate = bool(result_state.get("should_escalate")) or (
        turn.booking_status == "escalated"
    )

    # 5. Handle escalation vs standard bot reply dispatch
    if should_escalate:
        escalation_reason = (
            turn.escalation_reason or "Automated safety policy or handoff triggered"
        )
        logger.info(
            "Dialogue turn triggered escalation for conversation=%s: %s",
            conversation_id,
            escalation_reason,
        )

        handoff_details: Optional[dict[str, Any]] = None
        if api_token:
            try:
                handoff_details = await handoff_to_human(
                    chatwoot_base_url=base_url,
                    api_access_token=api_token,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    note=f"Automated Handoff: {escalation_reason}",
                )
                await send_bot_message(
                    chatwoot_base_url=base_url,
                    api_access_token=api_token,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    content=reply_text,
                )
            except Exception as exc:
                logger.error(
                    "Error executing handoff to human for conversation=%s: %s",
                    conversation_id,
                    exc,
                )

        return {
            "status": "handled",
            "action": "human_handoff",
            "conversation_id": conversation_id,
            "account_id": account_id,
            "reason": escalation_reason,
            "reply_sent": reply_text,
            "handoff_details": handoff_details,
        }

    # Dispatch bot reply to Chatwoot conversation
    if api_token:
        try:
            await send_bot_message(
                chatwoot_base_url=base_url,
                api_access_token=api_token,
                account_id=account_id,
                conversation_id=conversation_id,
                content=reply_text,
            )
        except Exception as exc:
            logger.error(
                "Error sending automated bot message for conversation=%s: %s",
                conversation_id,
                exc,
            )

    return {
        "status": "handled",
        "action": "agent_execution",
        "conversation_id": conversation_id,
        "account_id": account_id,
        "content": content,
        "reply_sent": reply_text,
        "booking_status": turn.booking_status,
        "hold_id": turn.hold_id,
    }


@router.post(
    "/conversations/{conversation_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Trigger background memory curation on conversation completion",
)
async def complete_conversation_hook(
    conversation_id: int,
    payload: ConversationCompletionHookPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Conversation completion hook.

    Enqueues post-conversation background memory curation following
    the Mem0 pattern using FastAPI BackgroundTasks.
    """
    logger.info(
        "Received conversation completion hook for conversation=%s, tenant=%s",
        conversation_id,
        payload.tenant_id,
    )
    background_tasks.add_task(
        curate_conversation_background,
        tenant_id=payload.tenant_id,
        transcript=payload.transcript,
        provider_id=payload.provider_id,
    )
    return {
        "status": "enqueued",
        "action": "curation_background_task",
        "conversation_id": conversation_id,
        "tenant_id": payload.tenant_id,
    }
