import httpx
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent
from ...models.client import Client
from ...models.provider import Provider
from .outbound_service import is_outbound_body_safe
from .transports.base import normalize_sms_destination

logger = logging.getLogger(__name__)

try:
    from ...core.telemetry import record_webhook_event
except ImportError:
    def record_webhook_event(status: str) -> None:
        pass

async def send_chatwoot_message(
    db: Session,
    conversation: SmsConversation,
    body: str,
    source_id: Optional[str] = None,
) -> int:
    """Send message to Chatwoot using live HTTP API client, returning Chatwoot message ID."""
    if not is_outbound_body_safe(body):
        raise ValueError("Chatwoot message failed outbound safety validation.")
    binding = (
        db.query(SmsChatwootBinding)
        .join(Provider, Provider.id == SmsChatwootBinding.provider_id)
        .filter(
            SmsChatwootBinding.tenant_id == conversation.tenant_id,
            SmsChatwootBinding.provider_id == conversation.provider_id,
            SmsChatwootBinding.chatwoot_inbox_id == conversation.chatwoot_inbox_id,
            SmsChatwootBinding.is_enabled == True,
            Provider.tenant_id == conversation.tenant_id,
        )
        .first()
    )

    if (
        not binding
        or conversation.chatwoot_conversation_id is None
        or conversation.chatwoot_inbox_id is None
        or not binding.chatwoot_api_token
    ):
        raise ValueError("No enabled Chatwoot binding found for conversation.")

    decrypted_token = binding.chatwoot_api_token
    base_url = binding.chatwoot_base_url.rstrip("/")
    url = f"{base_url}/api/v1/accounts/{binding.chatwoot_account_id}/conversations/{conversation.chatwoot_conversation_id}/messages"

    headers = {
        "api_access_token": decrypted_token,
        "Content-Type": "application/json"
    }
    payload = {
        "content": body,
        "message_type": "outgoing"
    }
    # Chatwoot includes this in the message-created webhook. It lets us
    # identify our own outbound message before the HTTP response (and its
    # Chatwoot message ID) has reached the outbox worker.
    if source_id:
        payload["source_id"] = source_id

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return int(data["id"])
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError):
        logger.error("Chatwoot outbound request failed.")
        raise

def process_chatwoot_webhook(db: Session, payload: dict, token: Optional[str]) -> dict:
    """Intake pipeline for incoming Chatwoot webhook events."""
    # 1. Extract Chatwoot identifiers
    chatwoot_inbox_id = payload.get("inbox", {}).get("id") or payload.get("conversation", {}).get("inbox_id")
    if not chatwoot_inbox_id:
        logger.warning("Rejecting Chatwoot webhook: missing inbox identification.")
        raise HTTPException(status_code=400, detail="Missing inbox identification in payload.")

    chatwoot_msg_id = payload.get("id")
    if not chatwoot_msg_id:
        # Fallback to check message field
        chatwoot_msg_id = payload.get("message", {}).get("id")
    if not chatwoot_msg_id:
        logger.warning("Rejecting Chatwoot webhook: missing message ID.")
        raise HTTPException(status_code=400, detail="Missing message ID in payload.")

    # 2. Resolve enabled binding
    bindings = (
        db.query(SmsChatwootBinding)
        .join(Provider, Provider.id == SmsChatwootBinding.provider_id)
        .filter(
            SmsChatwootBinding.chatwoot_inbox_id == chatwoot_inbox_id,
            SmsChatwootBinding.is_enabled == True,
            Provider.tenant_id == SmsChatwootBinding.tenant_id,
        )
        .all()
    )

    if not bindings:
        logger.warning(f"Chatwoot webhook rejected: binding not found or disabled for chatwoot_inbox_id={chatwoot_inbox_id}")
        record_webhook_event("rejected")
        raise HTTPException(status_code=404, detail="Chatwoot binding not found or disabled.")

    # 3. Validate authenticity
    import secrets
    matching_bindings = [
        candidate
        for candidate in bindings
        if token
        and candidate.webhook_secret
        and secrets.compare_digest(token, candidate.webhook_secret)
    ]
    if len(matching_bindings) != 1:
        logger.warning("Chatwoot webhook authentication failed.")
        record_webhook_event("rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    binding = matching_bindings[0]

    # 4. Enforce Idempotency using external Chatwoot message ID
    existing_message = (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.chatwoot_message_id == chatwoot_msg_id,
            SmsMessage.tenant_id == binding.tenant_id,
            SmsMessage.provider_id == binding.provider_id,
            SmsConversation.tenant_id == binding.tenant_id,
            SmsConversation.provider_id == binding.provider_id,
            SmsConversation.chatwoot_inbox_id == chatwoot_inbox_id,
        )
        .first()
    )

    if existing_message:
        logger.info(f"Duplicate Chatwoot message detected and deduplicated: {chatwoot_msg_id}")
        record_webhook_event("duplicate")
        return {
            "status": "success",
            "duplicate": True,
            "message_id": existing_message.id,
            "conversation_id": existing_message.conversation_id
        }

    # A Chatwoot webhook can arrive before the outbound worker receives the
    # POST response containing chatwoot_msg_id. Match the source ID persisted
    # before dispatch so that our own AI/system reply is never mistaken for a
    # staff message and never triggers human takeover.
    chatwoot_source_id = payload.get("source_id") or payload.get("message", {}).get("source_id")
    if chatwoot_source_id:
        internal_outbound = (
            db.query(SmsMessage)
            .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
            .filter(
                SmsMessage.client_request_id == chatwoot_source_id,
                SmsMessage.tenant_id == binding.tenant_id,
                SmsMessage.provider_id == binding.provider_id,
                SmsConversation.tenant_id == binding.tenant_id,
                SmsConversation.provider_id == binding.provider_id,
                SmsConversation.chatwoot_inbox_id == chatwoot_inbox_id,
                SmsMessage.direction == "outbound",
                SmsMessage.author_type.in_(["ai", "fixed_autoresponder", "system"]),
            )
            .first()
        )
        if internal_outbound:
            if internal_outbound.chatwoot_message_id is None:
                internal_outbound.chatwoot_message_id = chatwoot_msg_id
            if internal_outbound.status in ("queued", "sending"):
                internal_outbound.status = "sent"
            db.commit()
            logger.info(
                "Ignoring internal Chatwoot outbound echo for SmsMessage %s",
                internal_outbound.id,
            )
            record_webhook_event("duplicate")
            return {
                "status": "success",
                "duplicate": True,
                "reason": "internal_outbound_echo",
                "message_id": internal_outbound.id,
                "conversation_id": internal_outbound.conversation_id,
            }

    # Extract details
    content = payload.get("content") or ""
    message_type = payload.get("message_type")
    
    # Check if private note
    is_private = payload.get("private", False)
    if is_private:
        logger.info(f"Skipping private note with Chatwoot message ID {chatwoot_msg_id}")
        return {"status": "skipped", "reason": "private_note"}

    if message_type not in ("incoming", "outgoing"):
        logger.info(f"Skipping non-chatwoot-customer-facing message type: {message_type}")
        return {"status": "skipped", "reason": f"unhandled_message_type: {message_type}"}

    # 5. Resolve or create conversation
    chatwoot_conv_id = payload.get("conversation", {}).get("id")
    chatwoot_contact_id = payload.get("conversation", {}).get("contact", {}).get("id") or payload.get("contact", {}).get("id")

    conversation = db.query(SmsConversation).filter(
        SmsConversation.tenant_id == binding.tenant_id,
        SmsConversation.provider_id == binding.provider_id,
        SmsConversation.chatwoot_inbox_id == chatwoot_inbox_id,
        SmsConversation.chatwoot_conversation_id == chatwoot_conv_id,
    ).first()

    # Fallback to phone mapping if conversation not found by ID
    customer_phone = (
        payload.get("conversation", {}).get("contact", {}).get("phone_number")
        or payload.get("contact", {}).get("phone_number")
        or payload.get("sender", {}).get("phone_number")
    )
    normalized_phone = normalize_sms_destination(customer_phone) if customer_phone else None

    if not conversation and normalized_phone:
        conversation = db.query(SmsConversation).filter(
            SmsConversation.tenant_id == binding.tenant_id,
            SmsConversation.provider_id == binding.provider_id,
            SmsConversation.customer_address == normalized_phone,
            or_(
                SmsConversation.chatwoot_inbox_id.is_(None),
                SmsConversation.chatwoot_inbox_id == chatwoot_inbox_id,
            ),
        ).first()
        if conversation:
            # Sync existing conversation to Chatwoot columns
            conversation.chatwoot_conversation_id = chatwoot_conv_id
            conversation.chatwoot_contact_id = chatwoot_contact_id
            conversation.chatwoot_inbox_id = chatwoot_inbox_id
            db.flush()

    if not conversation:
        # Resolve Client if possible
        matching_client = None
        if normalized_phone:
            clients = db.query(Client).filter(Client.tenant_id == binding.tenant_id).all()
            for client in clients:
                if client.phone and normalize_sms_destination(client.phone) == normalized_phone:
                    matching_client = client
                    break

        conversation = SmsConversation(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=None,
            customer_address=normalized_phone or f"chatwoot_contact_{chatwoot_contact_id}",
            client_id=matching_client.id if matching_client else None,
            state="paused",
            unread_count=0,
            ai_enabled=False,
            chatwoot_conversation_id=chatwoot_conv_id,
            chatwoot_contact_id=chatwoot_contact_id,
            chatwoot_inbox_id=chatwoot_inbox_id
        )
        db.add(conversation)
        db.flush()

    # Determine turn ref for AI debounce
    turn_ref = f"chatwoot_turn_{chatwoot_msg_id}"
    
    # 6. Map inbound conversations/messages and trigger AI reply enqueuing
    if message_type == "incoming":
        inbound_message = SmsMessage(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=None,
            conversation_id=conversation.id,
            body=content,
            normalized_body=content.strip().lower(),
            direction="inbound",
            author_type="customer",
            status="received",
            chatwoot_message_id=chatwoot_msg_id,
            customer_turn_ref=turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc)
        )
        db.add(inbound_message)

        conversation.unread_count += 1
        conversation.last_activity_at = datetime.now(timezone.utc)
        db.flush()

        account = None
        if conversation.sms_account_id is not None:
            account = db.query(SmsAccount).filter(
                SmsAccount.id == conversation.sms_account_id,
                SmsAccount.tenant_id == binding.tenant_id,
                SmsAccount.provider_id == binding.provider_id,
                SmsAccount.is_enabled.is_(True),
                SmsAccount.ai_enabled.is_(True),
                SmsAccount.ai_mode.in_(("draft", "autopilot")),
            ).first()

        # Chatwoot-only threads have no line-scoped AI configuration and fail
        # closed. A carrier-backed thread may enqueue only with its exact line.
        if (
            conversation.state == "auto-reply"
            and conversation.ai_enabled
            and not conversation.is_blocked
            and account is not None
        ):
            db.query(SmsAiJob).filter(
                SmsAiJob.conversation_id == conversation.id,
                SmsAiJob.status == "PENDING"
            ).update({"status": "CANCELLED"})

            ai_job = SmsAiJob(
                conversation_id=conversation.id,
                customer_turn_ref=turn_ref,
                status="PENDING",
                created_at=datetime.now(timezone.utc),
                run_at=datetime.now(timezone.utc) + timedelta(seconds=5)
            )
            db.add(ai_job)
            db.flush()
            ai_job_enqueued = True
        else:
            ai_job_enqueued = False

        db.commit()
        record_webhook_event("accepted")
        return {
            "status": "success",
            "duplicate": False,
            "conversation_id": conversation.id,
            "ai_job_enqueued": ai_job_enqueued
        }

    # 7. For outgoing messages by staff/user
    elif message_type == "outgoing":
        stored_content = (
            content
            if is_outbound_body_safe(content)
            else "[withheld by outbound safety policy]"
        )
        outbound_message = SmsMessage(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=conversation.sms_account_id,
            conversation_id=conversation.id,
            body=stored_content,
            normalized_body=stored_content.strip().lower(),
            direction="outbound",
            author_type="staff",
            status="sent",
            chatwoot_message_id=chatwoot_msg_id,
            customer_turn_ref=turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc)
        )
        db.add(outbound_message)

        # Staff messages stop automation but do not erase stronger operational
        # states such as needs-review, escalated, resolved, or blocked/paused.
        previous_state = conversation.state
        if not conversation.is_blocked and conversation.state == "auto-reply":
            conversation.state = "taken-over"
        conversation.ai_enabled = False
        conversation.unread_count = 0
        conversation.last_activity_at = datetime.now(timezone.utc)
        db.flush()

        # Cancel pending AI jobs
        db.query(SmsAiJob).filter(
            SmsAiJob.conversation_id == conversation.id,
            SmsAiJob.status == "PENDING"
        ).update({"status": "CANCELLED"})

        # Record takeover event
        takeover_event = SmsConversationEvent(
            conversation_id=conversation.id,
            type=(
                "takeover"
                if previous_state == "auto-reply" and conversation.state == "taken-over"
                else "chatwoot_staff_message_received"
            ),
            meta={
                "trigger": "chatwoot_webhook",
                "message_id": outbound_message.id,
                "chatwoot_message_id": chatwoot_msg_id,
                "from_state": previous_state,
                "to_state": conversation.state,
                "safety_withheld": stored_content != content,
            }
        )
        db.add(takeover_event)
        
        db.commit()
        record_webhook_event("accepted")
        return {
            "status": "success",
            "duplicate": False,
            "conversation_id": conversation.id,
            "state": "taken-over"
        }
