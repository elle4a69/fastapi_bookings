import logging
import traceback
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from ...db.database import SessionLocal
from ...models.sms_outbox import SmsOutboundJob
from ...models.sms_account import SmsAccount
from ...models.sms_message import SmsMessage
from ...models.sms_conversation import SmsConversation
from .transports import get_transport_adapter
from .transports.base import OutboundSmsCommand

logger = logging.getLogger(__name__)

async def process_pending_sms_outbound_jobs(db: Session = None) -> None:
    """Fetch and process enqueued SMS outbound jobs with lease locking."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        now = datetime.now(timezone.utc)
        
        # 1. Fetch eligible jobs: PENDING (with no lease or expired lease) or stale PROCESSING (expired lease)
        jobs = db.query(SmsOutboundJob).filter(
            SmsOutboundJob.status.in_(["PENDING", "PROCESSING"]),
            SmsOutboundJob.retry_count < 5,
            (
                ((SmsOutboundJob.status == "PENDING") & ((SmsOutboundJob.lease_expires_at.is_(None)) | (SmsOutboundJob.lease_expires_at < now))) |
                ((SmsOutboundJob.status == "PROCESSING") & (SmsOutboundJob.lease_expires_at < now))
            )
        ).limit(10).all()

        if not jobs:
            return

        # 2. Acquire leases for processing (lock database rows atomically)
        leased_jobs = []
        for job in jobs:
            try:
                # Atomically try to update status from PENDING/stale to PROCESSING
                rows_updated = db.query(SmsOutboundJob).filter(
                    SmsOutboundJob.id == job.id,
                    (
                        ((SmsOutboundJob.status == "PENDING") & ((SmsOutboundJob.lease_expires_at.is_(None)) | (SmsOutboundJob.lease_expires_at < now))) |
                        ((SmsOutboundJob.status == "PROCESSING") & (SmsOutboundJob.lease_expires_at < now))
                    )
                ).update({
                    "status": "PROCESSING",
                    "lease_expires_at": datetime.now(timezone.utc) + timedelta(minutes=2)
                }, synchronize_session=False)
                
                db.commit()
                if rows_updated > 0:
                    leased_jobs.append(job.id)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to acquire lease on SmsOutboundJob {job.id}: {e}")

        # 3. Process each leased job in its own transaction
        for job_id in leased_jobs:
            # Re-fetch job in a fresh session block or transaction
            job = db.query(SmsOutboundJob).filter(SmsOutboundJob.id == job_id).first()
            if not job or job.status != "PROCESSING":
                continue

            message = db.query(SmsMessage).filter(SmsMessage.id == job.message_id).first()
            if not message:
                logger.error(f"SmsOutboundJob {job.id} refers to non-existent message.")
                job.status = "FAILED"
                job.error_log = "Message record missing."
                db.commit()
                continue

            conversation = db.query(SmsConversation).filter(SmsConversation.id == message.conversation_id).first()
            if not conversation:
                logger.error(f"SmsOutboundJob {job.id} message refers to non-existent conversation.")
                job.status = "FAILED"
                job.error_log = "Conversation record missing."
                db.commit()
                continue

            # Route Chatwoot-bound outbound messages directly
            if conversation.chatwoot_conversation_id is not None:
                try:
                    from .chatwoot_service import send_chatwoot_message
                    # Persist a deterministic source ID before the network
                    # call. Chatwoot echoes it in its webhook, which closes
                    # the race where the echo can arrive before this worker
                    # receives Chatwoot's response message ID.
                    if not message.client_request_id:
                        message.client_request_id = f"fastapi-chatwoot-message-{message.id}"
                    message.status = "sending"
                    db.commit()

                    mock_msg_id = await send_chatwoot_message(
                        db,
                        conversation,
                        message.body,
                        source_id=message.client_request_id,
                    )

                    job.status = "SUCCESS"
                    job.processed_at = datetime.now(timezone.utc)
                    message.status = "sent"
                    message.chatwoot_message_id = mock_msg_id
                    db.commit()
                    logger.info(f"Successfully sent outbound Chatwoot message (id={message.id}) via send_chatwoot_message")
                    continue
                except Exception as ex:
                    db.rollback()
                    job.retry_count += 1
                    job.error_log = f"{str(ex)}\n{traceback.format_exc()}"
                    if job.retry_count >= 5:
                        job.status = "FAILED"
                        message.status = "failed"
                    else:
                        job.status = "PENDING"
                        job.lease_expires_at = None
                        message.status = "queued"
                    db.commit()
                    continue

            # SMS specific flow requires account
            account = db.query(SmsAccount).filter(SmsAccount.id == job.sms_account_id).first()
            if not account:
                logger.error(f"SmsOutboundJob {job.id} refers to non-existent account.")
                job.status = "FAILED"
                job.error_log = "Account record missing."
                db.commit()
                continue

            # Check if account is enabled
            if not account.is_enabled:
                logger.warning(f"SMS Account {account.id} is disabled. Skipping outbound job {job.id}.")
                job.status = "FAILED"
                job.error_log = "SMS Account is disabled."
                message.status = "failed"
                db.commit()
                continue

            # Check rate limits & quiet hours
            from .rate_limit_service import check_rate_limit_and_quiet_hours
            if not check_rate_limit_and_quiet_hours(db, account):
                job.status = "PENDING"
                job.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
                db.commit()
                continue

            try:
                # Resolve transport adapter
                adapter = get_transport_adapter(account.transport_type)
                
                # Normalize target address
                clean_to = adapter.normalise_address(conversation.customer_address)
                if not clean_to:
                    raise ValueError(f"Invalid customer phone number: {conversation.customer_address}")

                # Prepare command
                command = OutboundSmsCommand(
                    to=clean_to,
                    body=message.body,
                    # Stable idempotency key across retries
                    idempotency_key=f"outbound-{message.id}"
                )

                # Send via transport adapter
                message.status = "sending"
                db.commit()

                result = await adapter.send(account, command)

                if result.status == "success":
                    job.status = "SUCCESS"
                    job.processed_at = datetime.now(timezone.utc)
                    message.status = "sent"
                    message.provider_message_id = result.provider_message_id
                    logger.info(f"Successfully sent outbound SMS (id={message.id}) via {account.transport_type}")
                else:
                    raise RuntimeError(f"Transport send failure: {result.error_message} ({result.error_code})")

            except Exception as ex:
                db.rollback()
                job.retry_count += 1
                job.error_log = f"{str(ex)}\n{traceback.format_exc()}"
                
                if job.retry_count >= 5:
                    job.status = "FAILED"
                    message.status = "failed"
                    logger.error(f"Permanent failure for SmsOutboundJob {job.id} (retries exhausted): {ex}")
                else:
                    # Return to PENDING for retry
                    job.status = "PENDING"
                    job.lease_expires_at = None
                    message.status = "queued"
                    logger.warning(f"Temporary failure for SmsOutboundJob {job.id} (attempt {job.retry_count}): {ex}")

            db.commit()

        # Run AI jobs processing turn
        try:
            from .ai_orchestrator import process_pending_sms_ai_jobs
            await process_pending_sms_ai_jobs(db)
        except Exception as ai_ex:
            logger.error(f"Error in background AI job execution: {ai_ex}")

        # Run repeated arrival alerts processing
        try:
            from .arrival_service import process_repeated_arrival_alerts
            process_repeated_arrival_alerts(db)
        except Exception as arrival_ex:
            logger.error(f"Error in repeated arrival alerts execution: {arrival_ex}")

    finally:
        if should_close:
            db.close()
