import logging
import secrets
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.client import Client
from ...models.provider import Provider
from ...models.sms_account import SmsAccount
from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent
from .outbound_service import is_outbound_body_safe
from .transports.base import normalize_sms_destination

logger = logging.getLogger(__name__)

MAX_CHATWOOT_BODY_LENGTH = 1600
MAX_CHATWOOT_SOURCE_ID_LENGTH = 128
FASTAPI_CHATWOOT_SOURCE_PREFIX = "fastapi-chatwoot-message-"

try:
    from ...core.telemetry import record_webhook_event
except ImportError:

    def record_webhook_event(status: str) -> None:
        pass


def _record_webhook_status(status: str) -> None:
    try:
        record_webhook_event(status)
    except Exception:
        logger.warning("Chatwoot webhook telemetry failed.")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _exact_chatwoot_message(
    db: Session,
    *,
    binding: SmsChatwootBinding,
    local_conversation_id: int,
    inbox_id: int,
    chatwoot_conversation_id: int,
    chatwoot_message_id: int,
) -> SmsMessage | None:
    return (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.chatwoot_message_id == chatwoot_message_id,
            SmsMessage.tenant_id == binding.tenant_id,
            SmsMessage.provider_id == binding.provider_id,
            or_(
                SmsMessage.sms_account_id == SmsConversation.sms_account_id,
                and_(
                    SmsMessage.sms_account_id.is_(None),
                    SmsConversation.sms_account_id.is_(None),
                ),
            ),
            SmsConversation.id == local_conversation_id,
            SmsConversation.tenant_id == binding.tenant_id,
            SmsConversation.provider_id == binding.provider_id,
            SmsConversation.chatwoot_inbox_id == inbox_id,
            SmsConversation.chatwoot_conversation_id == chatwoot_conversation_id,
        )
        .first()
    )


def _duplicate_response(message: SmsMessage, *, reason: str | None = None) -> dict:
    response = {
        "status": "success",
        "duplicate": True,
        "message_id": message.id,
        "conversation_id": message.conversation_id,
    }
    if reason:
        response["reason"] = reason
    return response


async def send_chatwoot_message(
    db: Session,
    conversation: SmsConversation,
    body: str,
    source_id: Optional[str] = None,
) -> int:
    """Send through the single exact enabled Chatwoot binding."""

    if not is_outbound_body_safe(body):
        raise ValueError("Chatwoot message failed outbound safety validation.")
    if conversation.id is None:
        raise ValueError("Chatwoot conversation must be persisted before delivery.")
    with db.no_autoflush:
        persisted = (
            db.query(SmsConversation)
            .filter(
                SmsConversation.id == conversation.id,
                SmsConversation.tenant_id == conversation.tenant_id,
                SmsConversation.provider_id == conversation.provider_id,
                SmsConversation.sms_account_id == conversation.sms_account_id,
                SmsConversation.chatwoot_inbox_id == conversation.chatwoot_inbox_id,
                SmsConversation.chatwoot_conversation_id
                == conversation.chatwoot_conversation_id,
                SmsConversation.chatwoot_contact_id
                == conversation.chatwoot_contact_id,
            )
            .populate_existing()
            .with_for_update()
            .first()
        )
    if persisted is None:
        raise ValueError("Chatwoot conversation scope is inconsistent.")
    bindings = (
        db.query(SmsChatwootBinding)
        .join(Provider, Provider.id == SmsChatwootBinding.provider_id)
        .filter(
            SmsChatwootBinding.tenant_id == persisted.tenant_id,
            SmsChatwootBinding.provider_id == persisted.provider_id,
            SmsChatwootBinding.chatwoot_inbox_id == persisted.chatwoot_inbox_id,
            SmsChatwootBinding.is_enabled.is_(True),
            Provider.tenant_id == persisted.tenant_id,
        )
        .limit(2)
        .all()
    )
    if (
        len(bindings) != 1
        or _positive_int(persisted.chatwoot_conversation_id) is None
        or _positive_int(persisted.chatwoot_inbox_id) is None
        or _positive_int(bindings[0].chatwoot_account_id) is None
        or (
            persisted.chatwoot_contact_id is not None
            and _positive_int(persisted.chatwoot_contact_id) is None
        )
        or not bindings[0].chatwoot_api_token
    ):
        raise ValueError("No unique enabled Chatwoot binding found for conversation.")
    if source_id is not None and (
        not isinstance(source_id, str)
        or not source_id
        or len(source_id) > MAX_CHATWOOT_SOURCE_ID_LENGTH
    ):
        raise ValueError("Invalid Chatwoot source identifier.")

    binding = bindings[0]
    url = (
        f"{binding.chatwoot_base_url.rstrip('/')}/api/v1/accounts/"
        f"{binding.chatwoot_account_id}/conversations/"
        f"{persisted.chatwoot_conversation_id}/messages"
    )
    headers = {
        "api_access_token": binding.chatwoot_api_token,
        "Content-Type": "application/json",
    }
    outbound_payload = {"content": body, "message_type": "outgoing"}
    if source_id:
        outbound_payload["source_id"] = source_id

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=outbound_payload)
            response.raise_for_status()
            message_id = _positive_int(_mapping(response.json()).get("id"))
            if message_id is None:
                raise ValueError("Chatwoot response did not contain a valid message ID.")
            return message_id
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError):
        logger.error("Chatwoot outbound request failed.")
        raise


def process_chatwoot_webhook(
    db: Session, payload: dict, token: Optional[str]
) -> dict:
    """Validate and ingest one text-message Chatwoot webhook event."""

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Chatwoot payload.")
    inbox_payload = _mapping(payload.get("inbox"))
    account_supplied = "account" in payload
    account_payload = _mapping(payload.get("account"))
    conversation_payload = _mapping(payload.get("conversation"))
    message_payload = _mapping(payload.get("message"))
    contact_payload = _mapping(payload.get("contact"))
    conversation_contact = _mapping(conversation_payload.get("contact"))
    sender_payload = _mapping(payload.get("sender"))

    inbox_id = _positive_int(
        inbox_payload.get("id") or conversation_payload.get("inbox_id")
    )
    message_id = _positive_int(payload.get("id") or message_payload.get("id"))
    chatwoot_conversation_id = _positive_int(conversation_payload.get("id"))
    if inbox_id is None or message_id is None or chatwoot_conversation_id is None:
        logger.warning("Chatwoot webhook rejected for invalid structural identifiers.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=400, detail="Invalid Chatwoot payload identifiers.")

    bindings = (
        db.query(SmsChatwootBinding)
        .join(Provider, Provider.id == SmsChatwootBinding.provider_id)
        .filter(
            SmsChatwootBinding.chatwoot_inbox_id == inbox_id,
            SmsChatwootBinding.is_enabled.is_(True),
            Provider.tenant_id == SmsChatwootBinding.tenant_id,
        )
        .all()
    )
    if not bindings:
        logger.warning("Chatwoot webhook rejected because no enabled binding exists.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=404, detail="Chatwoot binding not found or disabled.")
    matching_bindings = [
        candidate
        for candidate in bindings
        if token
        and candidate.webhook_secret
        and secrets.compare_digest(token, candidate.webhook_secret)
    ]
    if len(matching_bindings) != 1:
        logger.warning("Chatwoot webhook authentication failed.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    binding = matching_bindings[0]
    if account_supplied:
        webhook_account_id = _positive_int(account_payload.get("id"))
        if webhook_account_id != binding.chatwoot_account_id:
            logger.warning("Chatwoot webhook account binding did not match.")
            _record_webhook_status("rejected")
            raise HTTPException(status_code=401, detail="Invalid webhook binding.")

    message_type = payload.get("message_type")
    if message_type not in {"incoming", "outgoing"}:
        logger.info("Chatwoot webhook skipped for unsupported message type.")
        return {"status": "skipped", "reason": "unsupported_message_type"}
    if payload.get("private") is True:
        logger.info("Chatwoot private-note webhook skipped.")
        return {"status": "skipped", "reason": "private_note"}

    content = payload.get("content")
    if (
        not isinstance(content, str)
        or not content.strip()
        or len(content) > MAX_CHATWOOT_BODY_LENGTH
    ):
        logger.warning("Chatwoot webhook rejected for invalid text content.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=422, detail="Invalid Chatwoot message content.")
    source_id = payload.get("source_id") or message_payload.get("source_id")
    if source_id is not None and (
        not isinstance(source_id, str)
        or not source_id
        or len(source_id) > MAX_CHATWOOT_SOURCE_ID_LENGTH
    ):
        logger.warning("Chatwoot webhook rejected for invalid source identifier.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=400, detail="Invalid Chatwoot source identifier.")

    exact_conversations = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.tenant_id == binding.tenant_id,
            SmsConversation.provider_id == binding.provider_id,
            SmsConversation.chatwoot_inbox_id == inbox_id,
            SmsConversation.chatwoot_conversation_id == chatwoot_conversation_id,
        )
        .with_for_update()
        .limit(2)
        .all()
    )
    if len(exact_conversations) > 1:
        logger.error("Chatwoot webhook found ambiguous conversation ownership.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=409, detail="Ambiguous Chatwoot conversation binding.")
    conversation = exact_conversations[0] if exact_conversations else None

    customer_phone = (
        conversation_contact.get("phone_number")
        or contact_payload.get("phone_number")
        or sender_payload.get("phone_number")
    )
    normalized_phone = (
        normalize_sms_destination(customer_phone)
        if isinstance(customer_phone, str) and customer_phone
        else None
    )
    chatwoot_contact_id = _positive_int(
        conversation_contact.get("id") or contact_payload.get("id")
    )
    if (
        conversation is not None
        and conversation.chatwoot_contact_id is not None
        and chatwoot_contact_id is not None
        and conversation.chatwoot_contact_id != chatwoot_contact_id
    ):
        logger.warning("Chatwoot webhook contact binding did not match.")
        _record_webhook_status("rejected")
        raise HTTPException(status_code=409, detail="Chatwoot contact conflict.")
    if conversation is None and normalized_phone:
        unbound_candidates = (
            db.query(SmsConversation)
            .filter(
                SmsConversation.tenant_id == binding.tenant_id,
                SmsConversation.provider_id == binding.provider_id,
                SmsConversation.customer_address == normalized_phone,
                SmsConversation.chatwoot_inbox_id.is_(None),
                SmsConversation.chatwoot_conversation_id.is_(None),
                SmsConversation.chatwoot_contact_id.is_(None),
            )
            .with_for_update()
            .limit(2)
            .all()
        )
        if len(unbound_candidates) > 1:
            logger.error("Chatwoot webhook found ambiguous unbound conversations.")
            _record_webhook_status("rejected")
            raise HTTPException(status_code=409, detail="Ambiguous local conversation binding.")
        if unbound_candidates:
            conversation = unbound_candidates[0]
            conversation.chatwoot_conversation_id = chatwoot_conversation_id
            conversation.chatwoot_contact_id = chatwoot_contact_id
            conversation.chatwoot_inbox_id = inbox_id
            db.flush()

    if conversation is None:
        if normalized_phone is None and chatwoot_contact_id is None:
            raise HTTPException(status_code=422, detail="Chatwoot contact identity is required.")
        matching_client = None
        if normalized_phone:
            clients = db.query(Client).filter(Client.tenant_id == binding.tenant_id).all()
            matching_client = next(
                (
                    client
                    for client in clients
                    if client.phone
                    and normalize_sms_destination(client.phone) == normalized_phone
                ),
                None,
            )
        conversation = SmsConversation(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=None,
            customer_address=normalized_phone or f"chatwoot_contact_{chatwoot_contact_id}",
            client_id=matching_client.id if matching_client else None,
            state="paused",
            unread_count=0,
            ai_enabled=False,
            chatwoot_conversation_id=chatwoot_conversation_id,
            chatwoot_contact_id=chatwoot_contact_id,
            chatwoot_inbox_id=inbox_id,
        )
        db.add(conversation)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            recovered = (
                db.query(SmsConversation)
                .filter(
                    SmsConversation.tenant_id == binding.tenant_id,
                    SmsConversation.provider_id == binding.provider_id,
                    SmsConversation.chatwoot_inbox_id == inbox_id,
                    SmsConversation.chatwoot_conversation_id
                    == chatwoot_conversation_id,
                )
                .limit(2)
                .all()
            )
            if len(recovered) != 1:
                logger.error(
                    "Chatwoot conversation claim conflicted without an exact winner."
                )
                raise HTTPException(
                    status_code=409, detail="Chatwoot conversation conflict."
                ) from exc
            conversation = recovered[0]

    existing_message = _exact_chatwoot_message(
        db,
        binding=binding,
        local_conversation_id=conversation.id,
        inbox_id=inbox_id,
        chatwoot_conversation_id=chatwoot_conversation_id,
        chatwoot_message_id=message_id,
    )
    if existing_message:
        logger.info("Duplicate Chatwoot message was deduplicated.")
        _record_webhook_status("duplicate")
        return _duplicate_response(existing_message)

    if source_id and message_type == "outgoing":
        source_query = db.query(SmsMessage).filter(
            SmsMessage.tenant_id == binding.tenant_id,
            SmsMessage.provider_id == binding.provider_id,
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.sms_account_id == conversation.sms_account_id,
            SmsMessage.direction == "outbound",
            SmsMessage.author_type.in_(["ai", "fixed_autoresponder", "system", "staff"]),
            SmsMessage.status.in_(["queued", "sending", "sent", "delivered"]),
        )
        internal_id = None
        if source_id.startswith(FASTAPI_CHATWOOT_SOURCE_PREFIX):
            source_suffix = source_id[len(FASTAPI_CHATWOOT_SOURCE_PREFIX) :]
            if source_suffix.isdigit():
                internal_id = _positive_int(int(source_suffix))
        if internal_id is not None:
            source_query = source_query.filter(SmsMessage.id == internal_id)
        else:
            source_query = source_query.filter(SmsMessage.client_request_id == source_id)
        internal_outbound = source_query.first()
        if internal_outbound:
            if not secrets.compare_digest(internal_outbound.body, content):
                raise HTTPException(status_code=409, detail="Chatwoot source conflict.")
            if internal_outbound.chatwoot_message_id is None:
                internal_outbound.chatwoot_message_id = message_id
            elif internal_outbound.chatwoot_message_id != message_id:
                raise HTTPException(status_code=409, detail="Chatwoot source conflict.")
            if internal_outbound.status in {"queued", "sending"}:
                internal_outbound.status = "sent"
            db.commit()
            logger.info(
                "Chatwoot outbound echo was reconciled (message_id=%s).",
                internal_outbound.id,
            )
            _record_webhook_status("duplicate")
            return _duplicate_response(internal_outbound, reason="internal_outbound_echo")

    turn_ref = f"chatwoot_turn_{message_id}"
    if message_type == "incoming":
        webhook_message = SmsMessage(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=conversation.sms_account_id,
            conversation_id=conversation.id,
            body=content,
            normalized_body=content.strip().lower(),
            direction="inbound",
            author_type="customer",
            status="received",
            chatwoot_message_id=message_id,
            customer_turn_ref=turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
        )
        db.add(webhook_message)
        conversation.unread_count += 1
        conversation.last_activity_at = datetime.now(timezone.utc)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            winner = _exact_chatwoot_message(
                db,
                binding=binding,
                local_conversation_id=conversation.id,
                inbox_id=inbox_id,
                chatwoot_conversation_id=chatwoot_conversation_id,
                chatwoot_message_id=message_id,
            )
            if winner is None:
                logger.error(
                    "Chatwoot message claim conflicted without an exact winner."
                )
                raise HTTPException(
                    status_code=409, detail="Chatwoot webhook conflict."
                ) from exc
            _record_webhook_status("duplicate")
            return _duplicate_response(winner)
        account = None
        if conversation.sms_account_id is not None:
            account = (
                db.query(SmsAccount)
                .filter(
                    SmsAccount.id == conversation.sms_account_id,
                    SmsAccount.tenant_id == binding.tenant_id,
                    SmsAccount.provider_id == binding.provider_id,
                    SmsAccount.is_enabled.is_(True),
                    SmsAccount.ai_enabled.is_(True),
                    SmsAccount.ai_mode.in_(("draft", "autopilot")),
                )
                .first()
            )
        ai_job_enqueued = False
        if (
            conversation.state == "auto-reply"
            and conversation.ai_enabled
            and not conversation.is_blocked
            and account is not None
        ):
            db.query(SmsAiJob).filter(
                SmsAiJob.conversation_id == conversation.id,
                SmsAiJob.status == "PENDING",
            ).update({"status": "CANCELLED"})
            db.add(
                SmsAiJob(
                    conversation_id=conversation.id,
                    customer_turn_ref=turn_ref,
                    status="PENDING",
                    created_at=datetime.now(timezone.utc),
                    run_at=datetime.now(timezone.utc) + timedelta(seconds=5),
                )
            )
            ai_job_enqueued = True
    else:
        stored_content = content if is_outbound_body_safe(content) else "[withheld by outbound safety policy]"
        webhook_message = SmsMessage(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=conversation.sms_account_id,
            conversation_id=conversation.id,
            body=stored_content,
            normalized_body=stored_content.strip().lower(),
            direction="outbound",
            author_type="staff",
            status="sent",
            chatwoot_message_id=message_id,
            customer_turn_ref=turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
        )
        db.add(webhook_message)
        previous_state = conversation.state
        if not conversation.is_blocked and conversation.state == "auto-reply":
            conversation.state = "taken-over"
        conversation.ai_enabled = False
        conversation.unread_count = 0
        conversation.last_activity_at = datetime.now(timezone.utc)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            winner = _exact_chatwoot_message(
                db,
                binding=binding,
                local_conversation_id=conversation.id,
                inbox_id=inbox_id,
                chatwoot_conversation_id=chatwoot_conversation_id,
                chatwoot_message_id=message_id,
            )
            if winner is None:
                logger.error(
                    "Chatwoot message claim conflicted without an exact winner."
                )
                raise HTTPException(
                    status_code=409, detail="Chatwoot webhook conflict."
                ) from exc
            _record_webhook_status("duplicate")
            return _duplicate_response(winner)
        db.query(SmsAiJob).filter(
            SmsAiJob.conversation_id == conversation.id,
            SmsAiJob.status == "PENDING",
        ).update({"status": "CANCELLED"})
        db.add(
            SmsConversationEvent(
                conversation_id=conversation.id,
                type=(
                    "takeover"
                    if previous_state == "auto-reply"
                    and conversation.state == "taken-over"
                    else "chatwoot_staff_message_received"
                ),
                meta={
                    "trigger": "chatwoot_webhook",
                    "message_id": webhook_message.id,
                    "chatwoot_message_id": message_id,
                    "from_state": previous_state,
                    "to_state": conversation.state,
                    "safety_withheld": stored_content != content,
                },
            )
        )
        ai_job_enqueued = False

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = _exact_chatwoot_message(
            db,
            binding=binding,
            local_conversation_id=conversation.id,
            inbox_id=inbox_id,
            chatwoot_conversation_id=chatwoot_conversation_id,
            chatwoot_message_id=message_id,
        )
        if winner is None:
            logger.error("Chatwoot webhook transaction conflicted without an exact winner.")
            raise HTTPException(status_code=409, detail="Chatwoot webhook conflict.") from exc
        _record_webhook_status("duplicate")
        return _duplicate_response(winner)

    _record_webhook_status("accepted")
    response = {
        "status": "success",
        "duplicate": False,
        "conversation_id": conversation.id,
    }
    if message_type == "incoming":
        response["ai_job_enqueued"] = ai_job_enqueued
    else:
        response["state"] = conversation.state
    return response
