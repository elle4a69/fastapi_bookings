import hashlib
import hmac
import json
import logging
import random
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent
from ...models.client import Client
from ...models.provider import Provider
from ...models.location import Location, LocationProvider
from ...models.tenant import Tenant
from .transports.base import normalize_sms_destination

logger = logging.getLogger(__name__)

try:
    from ...core.telemetry import record_webhook_event
except ImportError:
    def record_webhook_event(status: str) -> None:
        pass


def resolve_chatwoot_binding(
    db: Session,
    tenant_id: int,
    provider_id: Optional[int] = None,
    location_id: Optional[int] = None,
) -> Optional[SmsChatwootBinding]:
    """Resolve the most specific active Chatwoot binding for a tenant.

    Precedence order:
    1. Provider-dedicated binding (if provider_id provided)
    2. Location-dedicated binding (if location_id provided)
    3. Tenant-default binding (provider_id IS NULL, location_id IS NULL)
    """
    if provider_id is not None:
        binding = db.query(SmsChatwootBinding).filter(
            SmsChatwootBinding.tenant_id == tenant_id,
            SmsChatwootBinding.provider_id == provider_id,
            SmsChatwootBinding.is_enabled.is_(True),
        ).first()
        if binding:
            return binding

    if location_id is not None:
        binding = db.query(SmsChatwootBinding).filter(
            SmsChatwootBinding.tenant_id == tenant_id,
            SmsChatwootBinding.location_id == location_id,
            SmsChatwootBinding.is_enabled.is_(True),
        ).first()
        if binding:
            return binding

    # Tenant default inbox fallback
    return db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant_id,
        SmsChatwootBinding.provider_id.is_(None),
        SmsChatwootBinding.location_id.is_(None),
        SmsChatwootBinding.is_enabled.is_(True),
    ).first()


async def send_chatwoot_message(
    db: Session,
    conversation: SmsConversation,
    body: str,
    source_id: Optional[str] = None,
) -> int:
    """Send message to Chatwoot using live HTTP API client, returning Chatwoot message ID."""
    binding = None
    if conversation.chatwoot_inbox_id is not None:
        binding = db.query(SmsChatwootBinding).filter(
            SmsChatwootBinding.tenant_id == conversation.tenant_id,
            SmsChatwootBinding.chatwoot_inbox_id == conversation.chatwoot_inbox_id,
            SmsChatwootBinding.is_enabled.is_(True),
        ).first()

    if not binding:
        binding = resolve_chatwoot_binding(
            db,
            tenant_id=conversation.tenant_id,
            provider_id=conversation.provider_id,
        )

    if not binding:
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
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as e:
        logger.error(f"Failed to send Chatwoot message: {e}")
        raise

def process_chatwoot_webhook(
    db: Session,
    payload: dict,
    token: Optional[str] = None,
    raw_body: Optional[Union[bytes, str]] = None,
    signature_header: Optional[str] = None,
    timestamp_header: Optional[Union[int, str]] = None,
) -> dict:
    """Intake pipeline for incoming Chatwoot webhook events."""
    # 1. Extract Chatwoot identifiers
    chatwoot_inbox_id = payload.get("inbox", {}).get("id") or payload.get("conversation", {}).get("inbox_id")
    if not chatwoot_inbox_id:
        logger.warning("Rejecting Chatwoot webhook: missing inbox identification.")
        raise HTTPException(status_code=400, detail="Missing inbox identification in payload.")

    chatwoot_account_id = payload.get("account", {}).get("id") or payload.get("conversation", {}).get("account_id")

    chatwoot_msg_id = payload.get("id")
    if not chatwoot_msg_id:
        # Fallback to check message field
        chatwoot_msg_id = payload.get("message", {}).get("id")
    if not chatwoot_msg_id:
        logger.warning("Rejecting Chatwoot webhook: missing message ID.")
        raise HTTPException(status_code=400, detail="Missing message ID in payload.")

    # 2. Resolve enabled binding by exact inbox (and account if present in payload)
    query = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.chatwoot_inbox_id == chatwoot_inbox_id,
        SmsChatwootBinding.is_enabled == True
    )
    if chatwoot_account_id is not None:
        query = query.filter(SmsChatwootBinding.chatwoot_account_id == chatwoot_account_id)
    binding = query.first()

    if not binding:
        logger.warning(
            f"Chatwoot webhook rejected: binding not found or disabled for chatwoot_inbox_id={chatwoot_inbox_id}, account_id={chatwoot_account_id}"
        )
        record_webhook_event("rejected")
        raise HTTPException(status_code=404, detail="Chatwoot binding not found or disabled.")

    # Scoping Validation:
    # 1) Location scoping (if location-dedicated): validate location belongs to mapped tenant
    if binding.location_id is not None:
        location = db.query(Location).filter(
            Location.id == binding.location_id,
            Location.tenant_id == binding.tenant_id,
        ).first()
        if not location or not location.active:
            logger.warning(
                f"Chatwoot webhook scoping rejected: location {binding.location_id} does not belong to tenant {binding.tenant_id} or is inactive"
            )
            record_webhook_event("rejected")
            raise HTTPException(status_code=403, detail="Location scoping validation failed: location does not belong to mapped tenant.")

    # 2) Provider scoping (if provider-dedicated): validate provider belongs to mapped tenant
    if binding.provider_id is not None:
        provider = db.query(Provider).filter(
            Provider.id == binding.provider_id,
            Provider.tenant_id == binding.tenant_id,
        ).first()
        if not provider or not provider.active:
            logger.warning(f"Chatwoot webhook scoping rejected: provider {binding.provider_id} does not belong to tenant {binding.tenant_id}")
            record_webhook_event("rejected")
            raise HTTPException(status_code=403, detail="Provider scoping validation failed: provider does not belong to mapped tenant.")

    # 3) Tenant scoping: validate tenant chatwoot_account_id mapping if established
    tenant = db.query(Tenant).filter(Tenant.id == binding.tenant_id).first()
    if not tenant:
        record_webhook_event("rejected")
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if tenant and tenant.chatwoot_account_id is not None and tenant.chatwoot_account_id != binding.chatwoot_account_id:
        logger.warning(
            f"Chatwoot webhook scoping rejected: tenant {tenant.id} mapped chatwoot_account_id {tenant.chatwoot_account_id} does not match binding {binding.chatwoot_account_id}"
        )
        record_webhook_event("rejected")
        raise HTTPException(status_code=403, detail="Tenant Chatwoot account scoping validation failed.")

    # Resolve effective provider ID for DB models that require provider_id
    effective_provider_id = binding.provider_id
    if effective_provider_id is None:
        if binding.location_id is not None:
            loc_prov = (
                db.query(Provider)
                .join(LocationProvider, LocationProvider.provider_id == Provider.id)
                .filter(
                    LocationProvider.location_id == binding.location_id,
                    LocationProvider.tenant_id == binding.tenant_id,
                    Provider.deleted_at.is_(None),
                    Provider.active.is_(True),
                )
                .first()
            )
            if loc_prov:
                effective_provider_id = loc_prov.id
        if effective_provider_id is None:
            tenant_prov = db.query(Provider).filter(
                Provider.tenant_id == binding.tenant_id,
                Provider.deleted_at.is_(None),
                Provider.active.is_(True),
            ).first()
            if tenant_prov:
                effective_provider_id = tenant_prov.id

    # 3. Validate authenticity (HMAC-SHA256 signature or shared token)
    binding_secret = binding.webhook_secret
    if not binding_secret:
        logger.warning(f"Chatwoot webhook authentication failed: no webhook_secret on binding {binding.id}")
        record_webhook_event("rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    if signature_header:
        extracted_sig: Optional[str] = None
        extracted_ts: Optional[int] = None

        # Parse signature and timestamp from header (handles t=ts,sha256=hex or sha256=hex)
        parts = [p.strip() for p in signature_header.replace(";", ",").split(",") if p.strip()]
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ("t", "timestamp"):
                    try:
                        extracted_ts = int(v)
                    except ValueError:
                        pass
                elif k in ("sha256", "v1", "sig", "signature"):
                    extracted_sig = v
            elif len(part) == 64 and all(c in "0123456789abcdefABCDEF" for c in part):
                extracted_sig = part

        if extracted_ts is None and timestamp_header:
            try:
                extracted_ts = int(str(timestamp_header).strip())
            except ValueError:
                pass

        if not extracted_sig or extracted_ts is None:
            logger.warning("Chatwoot webhook signature header malformed or missing timestamp.")
            record_webhook_event("rejected")
            raise HTTPException(status_code=401, detail="Malformed webhook signature or missing timestamp.")

        # 300-second timestamp replay defense guard
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - extracted_ts) > 300:
            logger.warning(
                f"Chatwoot webhook replay guard: timestamp {extracted_ts} outside 300s window (now={now_ts})"
            )
            record_webhook_event("rejected")
            raise HTTPException(status_code=401, detail="Webhook signature timestamp expired or outside replay window.")

        # Compute HMAC-SHA256 over {timestamp}.{raw_body}
        if isinstance(raw_body, bytes):
            body_bytes = raw_body
        elif isinstance(raw_body, str):
            body_bytes = raw_body.encode("utf-8")
        else:
            body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        msg_to_sign = f"{extracted_ts}.".encode("utf-8") + body_bytes
        computed_sig = hmac.new(
            key=binding_secret.encode("utf-8"),
            msg=msg_to_sign,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed_sig.lower(), extracted_sig.lower()):
            logger.warning("Chatwoot webhook HMAC signature verification failed.")
            record_webhook_event("rejected")
            raise HTTPException(status_code=401, detail="Invalid webhook HMAC signature.")

    elif token:
        if not secrets.compare_digest(token, binding_secret):
            logger.warning(f"Chatwoot webhook authentication failed for binding {binding.id}")
            record_webhook_event("rejected")
            raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    else:
        logger.warning(f"Chatwoot webhook missing authentication for binding {binding.id}")
        record_webhook_event("rejected")
        raise HTTPException(status_code=401, detail="Missing webhook authentication token or signature.")

    # 4. Enforce Idempotency using external Chatwoot message ID
    existing_message = db.query(SmsMessage).filter(
        SmsMessage.chatwoot_message_id == chatwoot_msg_id
    ).first()

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
        internal_outbound = db.query(SmsMessage).filter(
            SmsMessage.client_request_id == chatwoot_source_id,
            SmsMessage.direction == "outbound",
            SmsMessage.author_type.in_(["ai", "fixed_autoresponder", "system"]),
        ).first()
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
        SmsConversation.chatwoot_conversation_id == chatwoot_conv_id
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
            SmsConversation.provider_id == effective_provider_id,
            SmsConversation.customer_address == normalized_phone
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
            provider_id=effective_provider_id,
            sms_account_id=None,
            customer_address=normalized_phone or f"chatwoot_contact_{chatwoot_contact_id}",
            client_id=matching_client.id if matching_client else None,
            state="auto-reply",
            unread_count=0,
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
            provider_id=effective_provider_id,
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

        # Webhook Triage & Human Takeover Handshake
        conv_payload = payload.get("conversation", {}) or {}
        raw_labels = (
            conv_payload.get("labels")
            or conv_payload.get("label_list")
            or payload.get("labels")
            or []
        )
        if isinstance(raw_labels, str):
            label_list = [lb.strip() for lb in raw_labels.split(",") if lb.strip()]
        elif isinstance(raw_labels, list):
            label_list = [str(lb).strip() for lb in raw_labels if lb]
        else:
            label_list = []

        normalized_labels = {lb.lower().lstrip("#") for lb in label_list}

        assignee_id = conv_payload.get("assignee_id")
        if assignee_id is None:
            assignee_data = conv_payload.get("assignee")
            if isinstance(assignee_data, dict):
                assignee_id = assignee_data.get("id")

        is_human_labeled = bool(normalized_labels.intersection({"human-intervention-required", "needs-human"}))
        is_human_assigned = bool(assignee_id)
        is_human_takeover = is_human_labeled or is_human_assigned

        if is_human_takeover:
            conversation.state = "taken-over"
            # Cancel any existing pending AI jobs immediately
            db.query(SmsAiJob).filter(
                SmsAiJob.conversation_id == conversation.id,
                SmsAiJob.status == "PENDING"
            ).update({"status": "CANCELLED"})

            takeover_event = SmsConversationEvent(
                conversation_id=conversation.id,
                type="takeover",
                meta={
                    "by": "chatwoot_webhook_triage",
                    "reason": "human_intervention_label" if is_human_labeled else "assignee_set",
                    "labels": label_list,
                    "assignee_id": assignee_id,
                    "chatwoot_message_id": chatwoot_msg_id,
                }
            )
            db.add(takeover_event)
            db.commit()
            record_webhook_event("accepted")
            return {
                "status": "success",
                "duplicate": False,
                "conversation_id": conversation.id,
                "state": "taken-over",
                "ai_job_enqueued": False,
                "human_takeover": True,
            }

        # Trigger AI Job (burst debounce)
        if conversation.state == "auto-reply":
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
        outbound_message = SmsMessage(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=None,
            conversation_id=conversation.id,
            body=content,
            normalized_body=content.strip().lower(),
            direction="outbound",
            author_type="staff",
            status="sent",
            chatwoot_message_id=chatwoot_msg_id,
            customer_turn_ref=turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc)
        )
        db.add(outbound_message)

        # Trigger takeover state
        conversation.state = "taken-over"
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
            type="takeover",
            meta={"by": "chatwoot_webhook", "chatwoot_message_id": chatwoot_msg_id}
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
