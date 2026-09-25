import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException

from .transports import get_transport_adapter
from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_receipt import SmsInboundReceipt
from ...models.sms_outbox import SmsOutboundJob, SmsConversationEvent, SmsAiJob
from ...models.client import Client
from .outbound_service import enqueue_outbound_message_transactional

logger = logging.getLogger(__name__)

async def process_inbound_webhook(
    db: Session,
    transport_type: str,
    account_public_id: str,
    request: Request
) -> dict:
    """Intake pipeline for incoming SMS webhooks."""
    # 1. Resolve enabled SMS account
    account = db.query(SmsAccount).filter(
        SmsAccount.public_id == account_public_id,
        SmsAccount.transport_type == transport_type,
        SmsAccount.is_enabled == True
    ).first()
    
    if not account:
        logger.warning("Inbound webhook rejected for an unknown or disabled SMS account.")
        raise HTTPException(status_code=404, detail="SMS account not found or disabled.")

    adapter = get_transport_adapter(transport_type)

    # 2. Verify signature
    await adapter.verify_webhook(request, account)

    # 3. Parse and normalize
    norm_msg = await adapter.parse_inbound(request, account)
    
    if not norm_msg.sender:
        logger.warning("Inbound SMS rejected: Customer phone number is invalid or cannot be normalized.")
        raise HTTPException(status_code=422, detail="Customer phone number format is invalid.")

    # 4. Idempotency Check using Inbound Receipts
    receipt_key = hashlib.sha256(
        f"{account.id}:{norm_msg.event_key}".encode("utf-8")
    ).hexdigest()
    existing_receipt = db.query(SmsInboundReceipt).filter(
        SmsInboundReceipt.sms_account_id == account.id,
        SmsInboundReceipt.event_key == receipt_key,
    ).first()
    
    if existing_receipt:
        logger.info("Duplicate inbound event was deduplicated.")
        # Resolve conversation to return correct status
        conversation = db.query(SmsConversation).filter(
            SmsConversation.sms_account_id == account.id,
            SmsConversation.customer_address == norm_msg.sender
        ).first()
        return {
            "status": "success",
            "duplicate": True,
            "conversation_id": conversation.id if conversation else None
        }

    # 5. Resolve or create conversation
    customer_address = norm_msg.sender
    conversation = db.query(SmsConversation).filter(
        SmsConversation.sms_account_id == account.id,
        SmsConversation.customer_address == customer_address
    ).first()

    is_new_conversation = False
    if not conversation:
        is_new_conversation = True
        # Try to find matching Client in the tenant
        candidate_phones = [customer_address]
        if not customer_address.startswith("+"):
            candidate_phones.append(f"+{customer_address}")
        if customer_address.startswith("61") and len(customer_address) == 11:
            candidate_phones.append(f"0{customer_address[2:]}")
        elif customer_address.startswith("+61") and len(customer_address) == 12:
            candidate_phones.append(f"0{customer_address[3:]}")

        matching_client = (
            db.query(Client)
            .filter(
                Client.tenant_id == account.tenant_id,
                Client.phone.in_(candidate_phones),
            )
            .first()
        )
        if not matching_client and len(customer_address) >= 8:
            suffix = customer_address[-8:]
            candidates = (
                db.query(Client)
                .filter(
                    Client.tenant_id == account.tenant_id,
                    Client.phone.like(f"%{suffix}"),
                )
                .limit(10)
                .all()
            )
            for c in candidates:
                if c.phone and adapter.normalise_address(c.phone) == customer_address:
                    matching_client = c
                    break
                
        conversation = SmsConversation(
            tenant_id=account.tenant_id,
            provider_id=account.provider_id,
            sms_account_id=account.id,
            customer_address=customer_address,
            client_id=matching_client.id if matching_client else None,
            state=(
                "auto-reply"
                if account.ai_enabled and account.ai_mode in {"draft", "autopilot"}
                else "paused"
            ),
            unread_count=0
        )
        db.add(conversation)
        db.flush()  # populate conversation.id

    # 6. Save receipt, message, and update conversation
    receipt = SmsInboundReceipt(
        sms_account_id=account.id,
        event_key=receipt_key,
        raw_payload=None,
    )
    db.add(receipt)

    # Determine unique turn identifier for grouping bursts
    # If the last message was inbound and within 5 seconds, reuse its turn ref, otherwise new turn ref
    turn_ref = f"turn_{norm_msg.event_key}"
    last_msg = db.query(SmsMessage).filter(
        SmsMessage.conversation_id == conversation.id
    ).order_by(SmsMessage.occurred_at.desc()).first()
    
    if last_msg and last_msg.direction == "inbound" and last_msg.received_at:
        t1 = norm_msg.received_at
        t2 = last_msg.received_at
        if t1.tzinfo is not None and t2.tzinfo is None:
            t2 = t2.replace(tzinfo=timezone.utc)
        elif t1.tzinfo is None and t2.tzinfo is not None:
            t1 = t1.replace(tzinfo=timezone.utc)
        time_diff = t1 - t2
        if time_diff.total_seconds() <= 10.0:
            turn_ref = last_msg.customer_turn_ref or turn_ref

    inbound_message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body=norm_msg.body,
        normalized_body=norm_msg.body.strip().lower(),
        direction="inbound",
        author_type="customer",
        status="received",
        provider_message_id=norm_msg.event_key,
        customer_turn_ref=turn_ref,
        occurred_at=norm_msg.received_at,
        received_at=datetime.now(timezone.utc)
    )
    db.add(inbound_message)

    # Update conversation status
    conversation.unread_count += 1
    conversation.last_activity_at = datetime.now(timezone.utc)
    db.flush()

    # 7. Check for First-Contact Fixed Autoresponder
    autoresponder_sent = False
    if (
        account.autoresponder_enabled
        and account.autoresponder_text
        and conversation.state == "auto-reply"
        and not getattr(conversation, "is_blocked", False)
    ):
        # Check if autoresponder has already been sent in this conversation
        prior_autoresponder = db.query(SmsMessage).filter(
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.author_type == "fixed_autoresponder"
        ).first()
        
        if not prior_autoresponder:
            # Enqueue autoresponder reply
            # Replace placeholder variables if client context exists
            reply_body = account.autoresponder_text
            if conversation.client:
                reply_body = reply_body.replace("{name}", conversation.client.name or "there")
            else:
                reply_body = reply_body.replace("{name}", "there")
                
            enqueue_outbound_message_transactional(
                db=db,
                account=account,
                conversation=conversation,
                body=reply_body,
                author_type="fixed_autoresponder",
                parent_message_id=inbound_message.id,
                customer_turn_ref=turn_ref
            )
            
            # Log event
            event = SmsConversationEvent(
                conversation_id=conversation.id,
                type="autoresponder_triggered",
                meta={"message_id": inbound_message.id}
            )
            db.add(event)
            autoresponder_sent = True

    # 8. Check for AI Reply enqueuing (if enabled, not taken over, not blocked, and not autoresponder_only/autoresponder_sent)
    ai_job_enqueued = False
    if (
        account.ai_enabled
        and account.ai_mode in {"draft", "autopilot"}
        and conversation.state == "auto-reply"
        and getattr(conversation, "ai_enabled", True)
        and not getattr(conversation, "is_blocked", False)
        and not autoresponder_sent
    ):
        # Cancel any pending AI jobs for this conversation (burst debounce)
        db.query(SmsAiJob).filter(
            SmsAiJob.conversation_id == conversation.id,
            SmsAiJob.status == "PENDING"
        ).update({"status": "CANCELLED"})
        
        # Enqueue new AI job with 5-second debounce delay
        ai_job = SmsAiJob(
            conversation_id=conversation.id,
            customer_turn_ref=turn_ref,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            run_at=datetime.now(timezone.utc) + timedelta(seconds=5)
        )
        db.add(ai_job)
        ai_job_enqueued = True

    db.commit()
    
    return {
        "status": "success",
        "duplicate": False,
        "conversation_id": conversation.id,
        "autoresponder_sent": autoresponder_sent,
        "ai_job_enqueued": ai_job_enqueued
    }
