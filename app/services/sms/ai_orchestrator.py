import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent
from ...models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from ...models.provider import Provider
from ...models.service import Service
from ...models.sms_bootcamp import SmsBootcampSettings
from .prompt_builder import UnifiedPromptBuilder
from .outbound_service import enqueue_outbound_message_transactional

logger = logging.getLogger(__name__)

async def process_pending_sms_ai_jobs(db: Session) -> None:
    """Fetch and process enqueued AI jobs after their debounce delay."""
    now = datetime.now(timezone.utc)
    query = db.query(SmsAiJob).filter(
        SmsAiJob.status == "PENDING",
        (SmsAiJob.run_at.is_(None)) | (SmsAiJob.run_at <= now)
    ).order_by(SmsAiJob.id.asc()).limit(50)

    is_pg = (db.get_bind().dialect.name == "postgresql") if db.get_bind() else False
    if is_pg:
        query = query.with_for_update(skip_locked=True)

    jobs = query.all()
    
    for job in jobs:
        try:
            # Mark job as processed
            job.status = "PROCESSED"
            job.run_at = datetime.now(timezone.utc)
            db.commit()

            conversation = db.query(SmsConversation).filter(SmsConversation.id == job.conversation_id).first()
            if (
                not conversation
                or conversation.state != "auto-reply"
                or not getattr(conversation, "ai_enabled", True)
                or getattr(conversation, "is_blocked", False)
            ):
                continue

            account = db.query(SmsAccount).filter(
                SmsAccount.id == conversation.sms_account_id,
                SmsAccount.tenant_id == conversation.tenant_id,
                SmsAccount.provider_id == conversation.provider_id,
                SmsAccount.is_enabled.is_(True),
            ).first()
            if not account or not account.ai_enabled or account.ai_mode not in {"draft", "autopilot"}:
                continue

            # Run orchestrator logic
            await run_ai_orchestration(db, account, conversation, job.customer_turn_ref)

        except Exception:
            logger.exception("SMS AI job processing failed.")
            db.rollback()

async def run_ai_orchestration(
    db: Session, 
    account: SmsAccount, 
    conversation: SmsConversation, 
    turn_ref: str
) -> None:
    """Core AI processing turn. Chooses OpenAI or Local Rules engine."""
    # 1. Fetch conversation history for this turn
    history_messages = db.query(SmsMessage).filter(
        SmsMessage.conversation_id == conversation.id,
        SmsMessage.tenant_id == conversation.tenant_id,
        SmsMessage.provider_id == conversation.provider_id,
        SmsMessage.sms_account_id == conversation.sms_account_id,
        SmsMessage.direction == "inbound",
    ).order_by(SmsMessage.occurred_at.desc()).all()

    if not history_messages:
        return

    # Consolidate burst: grab all messages in this turn (same turn_ref)
    burst_msgs = [m for m in history_messages if m.customer_turn_ref == turn_ref]
    if not burst_msgs:
        # Fallback to the latest message
        burst_msgs = [history_messages[0]]
        
    combined_body = " ".join([m.body for m in reversed(burst_msgs)])
    parent_id = burst_msgs[0].id

    # 2. Check OpenAI Key availability
    from ...core.config import settings
    openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    ai_reply = None
    
    if openai_key:
        try:
            ai_reply = await call_openai_chat_completions(db, account, conversation, combined_body, turn_ref)
        except Exception:
            logger.warning("OpenAI completion failed; switching to fail-closed local review.")
            ai_reply = run_local_rules_engine(db, account, conversation, combined_body)
    else:
        # Local Rules / Mock AI fallback (runs offline)
        ai_reply = run_local_rules_engine(db, account, conversation, combined_body)

    if not ai_reply:
        return

    dynamic_request = _requires_verified_dynamic_data(combined_body)
    if ai_reply.startswith("[[HANDOFF"):
        conversation.state = "needs-review"
        event = SmsConversationEvent(
            conversation_id=conversation.id,
            type="ai_handoff_required",
            meta={"requires_review": True, "ai_mode": account.ai_mode},
        )
        db.add(event)
        db.commit()
        return

    # 3. Determine status: draft mode or autopilot
    status = "draft"
    if account.ai_mode == "autopilot" and not dynamic_request:
        status = "queued"
    else:
        conversation.state = "needs-review"
        
    # Enqueue AI response
    ai_message = enqueue_outbound_message_transactional(
        db=db,
        account=account,
        conversation=conversation,
        body=ai_reply,
        author_type="ai",
        status=status,
        parent_message_id=parent_id,
        customer_turn_ref=turn_ref
    )
    
    # Audit log event
    shadow_meta = getattr(conversation, "_last_shadow_metrics", None)
    event_meta = {
        "message_id": ai_message.id,
        "ai_mode": account.ai_mode,
        "requires_review": status == "draft",
    }
    if shadow_meta:
        event_meta["shadow_metrics"] = shadow_meta

    event = SmsConversationEvent(
        conversation_id=conversation.id,
        type="ai_reply_generated",
        meta=event_meta,
    )
    db.add(event)
    db.commit()

async def call_openai_chat_completions(
    db: Session, 
    account: SmsAccount, 
    conversation: SmsConversation, 
    message_body: str,
    turn_ref: str
) -> str:
    """Extract credentials, assemble prompt payload, call OpenAI, and parse response."""
    import os
    import time
    import httpx
    from sqlalchemy import or_

    # 1. Extract API key from server-side config only
    from ...core.config import settings
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API Key is missing.")

    # 2. Assemble prompt hierarchy via UnifiedPromptBuilder
    # Global tenant prompt
    global_prompt = db.query(SmsPromptProfile).filter(
        SmsPromptProfile.tenant_id == conversation.tenant_id,
        SmsPromptProfile.provider_id.is_(None),
        SmsPromptProfile.sms_account_id.is_(None),
        SmsPromptProfile.is_active == True,
    ).first()
    tenant_policy = global_prompt.system_prompt if (global_prompt and global_prompt.system_prompt) else None

    # Provider instructions / line prompt fallback
    provider_instructions = None
    if conversation.provider_id is not None:
        p_profile = db.query(SmsPromptProfile).filter(
            SmsPromptProfile.tenant_id == conversation.tenant_id,
            SmsPromptProfile.provider_id == conversation.provider_id,
            SmsPromptProfile.sms_account_id.is_(None),
            SmsPromptProfile.is_active == True,
        ).first()
        if p_profile and p_profile.system_prompt:
            provider_instructions = p_profile.system_prompt
    if not provider_instructions and account.line_prompt:
        provider_instructions = account.line_prompt

    # Style Lab profile & custom training notes from SmsBootcampSettings
    bootcamp_settings = db.query(SmsBootcampSettings).filter(
        SmsBootcampSettings.tenant_id == conversation.tenant_id
    ).first()
    style_profile = bootcamp_settings.active_style_profile if (bootcamp_settings and bootcamp_settings.active_style_profile) else None
    custom_notes = bootcamp_settings.custom_training_notes if (bootcamp_settings and bootcamp_settings.custom_training_notes) else None

    # Structured provider & services configuration
    provider = None
    services = []
    if conversation.provider_id is not None:
        provider = db.query(Provider).filter(
            Provider.id == conversation.provider_id,
            Provider.tenant_id == conversation.tenant_id,
        ).first()
        services = db.query(Service).filter(
            Service.tenant_id == conversation.tenant_id,
            Service.active == True,
        ).all()

    # Phase 11 & 13: Live learned-context retrieval exclusively via Knowledge Gateway / Graphiti (Specs 26, 46, 54, 65)
    from ..knowledge.gateway import knowledge_gateway
    from ..knowledge.types import RetrievalQuery

    retrieval_query = RetrievalQuery(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        query=message_body,
    )
    retrieval_result = knowledge_gateway.retrieve(retrieval_query, db=db)

    if hasattr(conversation, "id") and conversation.id:
        conversation._last_shadow_metrics = retrieval_result.metadata if retrieval_result else None
        try:
            from ...models.sms_outbox import SmsConversationEvent
            event = SmsConversationEvent(
                conversation_id=conversation.id,
                type="knowledge_retrieved",
                meta=retrieval_result.metadata if retrieval_result else {},
            )
            db.add(event)
        except Exception:
            pass

    # Chronological conversation history
    prior_db_messages = db.query(SmsMessage).filter(
        SmsMessage.conversation_id == conversation.id,
        SmsMessage.tenant_id == conversation.tenant_id,
        SmsMessage.provider_id == conversation.provider_id,
        SmsMessage.sms_account_id == conversation.sms_account_id,
        SmsMessage.direction.in_(("inbound", "outbound")),
        SmsMessage.status.notin_(("failed", "discarded")),
    ).order_by(SmsMessage.occurred_at.asc()).all()

    prior_messages = [m for m in prior_db_messages if m.customer_turn_ref != turn_ref]

    # Customer familiarity
    is_new_customer = getattr(conversation, "client_id", None) is None or len(prior_db_messages) <= 1

    # Compile layered prompt hierarchy via UnifiedPromptBuilder
    builder = (
        UnifiedPromptBuilder(tenant_id=conversation.tenant_id, provider_id=conversation.provider_id)
        .with_core_safety()
        .with_tenant_policy(tenant_policy)
        .with_provider_profile(
            text=provider_instructions,
            style_profile=style_profile,
            custom_notes=custom_notes,
        )
    )
    # Only attach structured configuration when active provider profile exists or services are configured
    if services and (provider_instructions != account.line_prompt or not account.line_prompt):
        builder.with_structured_config(provider=provider, services=services)

    builder.with_retrieval_result(retrieval_result).with_spec_54(True)

    builder.apply_situational_modulation(
        customer_text=message_body,
        prior_turns=prior_messages,
        is_new_customer=is_new_customer,
    ).with_history(history=prior_messages, current_message=message_body)

    messages = builder.build_messages_payload(discrete_system_messages=True)

    # 6. Call OpenAI using Gateway
    from ..gateway.responses_client import generate_response

    try:
        result = await generate_response(
            tenant_id=conversation.tenant_id,
            messages=messages,
            policy_name="luna",
            api_key=api_key
        )
        reply = result["choices"][0]["message"]["content"].strip()
        return reply
    except Exception:
        logger.exception("OpenAI gateway request failed.")
        raise


def _requires_verified_dynamic_data(message_body: str) -> bool:
    normalized = message_body.lower()
    dynamic_terms = (
        "available",
        "availability",
        "appointment",
        "book",
        "cancel",
        "cost",
        "date",
        "link",
        "pay",
        "price",
        "reschedule",
        "slot",
        "time",
        "today",
        "tomorrow",
    )
    return any(term in normalized for term in dynamic_terms)


def _safe_local_reply(
    db: Session,
    conversation: SmsConversation,
    message_body: str,
) -> str:
    """Answer only static approved knowledge; dynamic requests require review."""

    if _requires_verified_dynamic_data(message_body):
        return "[[HANDOFF: live data verification required]]"

    normalized = message_body.strip().lower()
    from ..knowledge.gateway import knowledge_gateway
    from ..knowledge.types import RetrievalQuery
    from ...core.config import settings
    try:
        res = knowledge_gateway.retrieve(
            RetrievalQuery(
                tenant_id=conversation.tenant_id,
                provider_id=conversation.provider_id,
                query=message_body,
            ),
            db=db,
        )
        if res and res.facts:
            for fact in res.facts:
                fact_text = fact.text if hasattr(fact, "text") else str(fact)
                keywords = [word.lower() for word in fact_text.split() if len(word) > 2]
                if any(word in normalized for word in keywords) or fact_text.lower() in normalized or normalized in fact_text.lower():
                    return fact_text
    except Exception:
        pass

    if settings.GRAPH_KNOWLEDGE_ENABLED:
        # Phase 13: Stop legacy reads of SmsKnowledgeEntry when GRAPH_KNOWLEDGE_ENABLED is True (Spec 27, 46)
        return "[[HANDOFF: inquiry requires staff assistance]]"

    entries = (
        db.query(SmsKnowledgeEntry)
        .filter(
            SmsKnowledgeEntry.tenant_id == conversation.tenant_id,
            SmsKnowledgeEntry.status == "approved",
            or_(
                SmsKnowledgeEntry.provider_id.is_(None),
                SmsKnowledgeEntry.provider_id == conversation.provider_id,
            ),
            or_(
                SmsKnowledgeEntry.sms_account_id.is_(None),
                SmsKnowledgeEntry.sms_account_id == conversation.sms_account_id,
            ),
        )
        .all()
    )
    for entry in entries:
        category = (entry.category or "").lower()
        keywords = [word.lower() for word in entry.text.split() if len(word) > 4]
        if (category and category in normalized) or any(word in normalized for word in keywords):
            return entry.text
    return "[[HANDOFF: inquiry requires staff assistance]]"

def run_local_rules_engine(
    db: Session, 
    account: SmsAccount, 
    conversation: SmsConversation, 
    message_body: str,
    compiled_rules: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Return approved static knowledge or fail closed for staff review.

    Booking, cancellation, pricing, and availability actions deliberately do
    not exist in this fallback. Those actions require the authoritative,
    explicitly confirmed conversational-booking workflow.
    """

    return _safe_local_reply(db, conversation, message_body)
