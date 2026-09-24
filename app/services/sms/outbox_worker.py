import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ...db.database import SessionLocal
from ...models.sms_outbox import SmsConversationEvent, SmsOutboundJob
from ...models.sms_account import SmsAccount
from ...models.sms_message import SmsMessage
from ...models.sms_conversation import SmsConversation
from .transports import get_transport_adapter
from .transports.base import OutboundSmsCommand
from .outbound_service import is_outbound_body_safe
from .operations_service import SmsOperationConflict, ensure_message_delivery_allowed

logger = logging.getLogger(__name__)

CHATWOOT_ACCEPTED_MESSAGE_STATUSES = frozenset(
    {"queued", "sending", "sent", "delivered"}
)
CHATWOOT_ACCEPTED_AUTHOR_TYPES = frozenset({"staff", "ai"})


def _positive_non_bool_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _has_exact_chatwoot_acceptance(
    *,
    job: SmsOutboundJob,
    message: SmsMessage,
    conversation: SmsConversation,
) -> bool:
    """Validate durable Chatwoot acceptance without reapplying live controls."""

    return (
        _positive_non_bool_int(message.chatwoot_message_id)
        and _positive_non_bool_int(conversation.chatwoot_conversation_id)
        and _positive_non_bool_int(conversation.chatwoot_inbox_id)
        and job.status == "PROCESSING"
        and job.message_id == message.id
        and job.sms_account_id == message.sms_account_id
        and message.conversation_id == conversation.id
        and message.tenant_id == conversation.tenant_id
        and message.provider_id == conversation.provider_id
        and message.sms_account_id == conversation.sms_account_id
        and message.direction == "outbound"
        and message.author_type in CHATWOOT_ACCEPTED_AUTHOR_TYPES
        and message.status in CHATWOOT_ACCEPTED_MESSAGE_STATUSES
    )


def _delivery_lock_statements(
    *, conversation_id: int, message_id: int, job_id: int
):
    """Build the canonical conversation -> message -> job lock sequence."""

    return (
        select(SmsConversation)
        .where(SmsConversation.id == conversation_id)
        .execution_options(populate_existing=True)
        .with_for_update(),
        select(SmsMessage)
        .where(SmsMessage.id == message_id)
        .execution_options(populate_existing=True)
        .with_for_update(),
        select(SmsOutboundJob)
        .where(SmsOutboundJob.id == job_id)
        .execution_options(populate_existing=True)
        .with_for_update(),
    )


def _load_locked_delivery_context(
    db: Session, job_id: int
) -> tuple[SmsOutboundJob, SmsMessage, SmsConversation] | None:
    """Lock one delivery in conversation -> message -> job order."""

    job_probe = db.query(SmsOutboundJob).filter(SmsOutboundJob.id == job_id).first()
    if job_probe is None:
        return None
    message_probe = (
        db.query(SmsMessage).filter(SmsMessage.id == job_probe.message_id).first()
    )
    if message_probe is None:
        return None
    conversation_stmt, message_stmt, job_stmt = _delivery_lock_statements(
        conversation_id=message_probe.conversation_id,
        message_id=message_probe.id,
        job_id=job_id,
    )
    conversation = db.execute(conversation_stmt).scalar_one_or_none()
    if conversation is None:
        return None
    message = db.execute(message_stmt).scalar_one_or_none()
    job = db.execute(job_stmt).scalar_one_or_none()
    if (
        message is None
        or job is None
        or job.status != "PROCESSING"
        or job.message_id != message.id
    ):
        return None
    return job, message, conversation


def _recover_chatwoot_delivery_after_error(
    db: Session,
    *,
    job_id: int,
    message_id: int,
) -> bool:
    """Re-lock after rollback, then reconcile acceptance or schedule retry.

    The webhook uses the same conversation lock. Whichever path acquires it
    first establishes the next durable state without a stale last-writer
    update from the worker.
    """

    locked_context = _load_locked_delivery_context(db, job_id)
    if locked_context is None:
        return False
    job, message, conversation = locked_context
    if (
        message.id != message_id
        or message.tenant_id != conversation.tenant_id
        or message.provider_id != conversation.provider_id
        or message.sms_account_id != conversation.sms_account_id
        or message.conversation_id != conversation.id
        or job.message_id != message.id
        or job.sms_account_id != message.sms_account_id
        or conversation.chatwoot_conversation_id is None
        or conversation.chatwoot_inbox_id is None
    ):
        _quarantine_delivery_job(
            db,
            job=job,
            message=message,
            conversation=conversation,
            reason="DELIVERY_SCOPE_MISMATCH",
        )
        return True

    if message.chatwoot_message_id is not None:
        if not _has_exact_chatwoot_acceptance(
            job=job,
            message=message,
            conversation=conversation,
        ):
            _quarantine_delivery_job(
                db,
                job=job,
                message=message,
                conversation=conversation,
                reason="CHATWOOT_ACCEPTANCE_INVALID",
            )
            return True
        if message.status != "delivered":
            message.status = "sent"
        job.status = "SUCCESS"
        job.error_log = None
        job.lease_expires_at = None
        job.processed_at = datetime.now(timezone.utc)
    else:
        job.retry_count += 1
        job.error_log = "CHATWOOT_DELIVERY_FAILED"
        if job.retry_count >= 5:
            job.status = "FAILED"
            job.lease_expires_at = None
            job.processed_at = datetime.now(timezone.utc)
            if message.status in {"queued", "sending"}:
                message.status = "failed"
        else:
            job.status = "PENDING"
            job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
            if message.status in {"queued", "sending"}:
                message.status = "queued"
    db.commit()
    return True


def _quarantine_delivery_job(
    db: Session,
    *,
    job: SmsOutboundJob,
    message: SmsMessage | None,
    conversation: SmsConversation | None,
    reason: str,
) -> None:
    """Terminally reject an unsafe job and retain structural audit evidence."""

    job.status = "FAILED"
    job.error_log = reason
    job.lease_expires_at = None
    job.processed_at = datetime.now(timezone.utc)
    if message is not None and message.status in {"queued", "sending"}:
        message.status = "failed"
    if conversation is not None and message is not None:
        db.add(
            SmsConversationEvent(
                conversation_id=conversation.id,
                type="outbound_delivery_quarantined",
                meta={
                    "message_id": message.id,
                    "job_id": job.id,
                    "reason": reason,
                },
            )
        )
    db.commit()

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
            except Exception:
                db.rollback()
                logger.error("Outbound job lease acquisition failed (job_id=%s).", job.id)

        # 3. Process each leased job in its own transaction
        for job_id in leased_jobs:
            job_probe = db.query(SmsOutboundJob).filter(
                SmsOutboundJob.id == job_id
            ).first()
            if job_probe is None or job_probe.status != "PROCESSING":
                continue
            message_probe = db.query(SmsMessage).filter(
                SmsMessage.id == job_probe.message_id
            ).first()
            if message_probe is None:
                logger.error("Outbound job has no message (job_id=%s).", job_probe.id)
                _quarantine_delivery_job(
                    db,
                    job=job_probe,
                    message=None,
                    conversation=None,
                    reason="MESSAGE_MISSING",
                )
                continue
            conversation_probe = db.query(SmsConversation).filter(
                SmsConversation.id == message_probe.conversation_id
            ).first()
            if conversation_probe is None:
                logger.error(
                    "Outbound job has no conversation (job_id=%s).", job_probe.id
                )
                _quarantine_delivery_job(
                    db,
                    job=job_probe,
                    message=message_probe,
                    conversation=None,
                    reason="CONVERSATION_MISSING",
                )
                continue
            # Lock in the same order used by operations mutations. The
            # conversation lock is intentionally held through provider
            # acceptance so a protected lifecycle transition cannot return
            # while a stale automated send is still in flight.
            locked_context = _load_locked_delivery_context(db, job_id)
            if locked_context is None:
                continue
            job, message, conversation = locked_context

            scope_is_valid = (
                message.tenant_id == conversation.tenant_id
                and message.provider_id == conversation.provider_id
                and message.sms_account_id == conversation.sms_account_id
                and job.sms_account_id == message.sms_account_id
            )
            if not scope_is_valid:
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="DELIVERY_SCOPE_MISMATCH",
                )
                continue

            is_chatwoot_thread = (
                conversation.chatwoot_conversation_id is not None
                and conversation.chatwoot_inbox_id is not None
            )
            if message.chatwoot_message_id is not None:
                if not _has_exact_chatwoot_acceptance(
                    job=job,
                    message=message,
                    conversation=conversation,
                ):
                    _quarantine_delivery_job(
                        db,
                        job=job,
                        message=message,
                        conversation=conversation,
                        reason="CHATWOOT_ACCEPTANCE_INVALID",
                    )
                    continue
                if message.status != "delivered":
                    message.status = "sent"
                job.status = "SUCCESS"
                job.error_log = None
                job.lease_expires_at = None
                job.processed_at = datetime.now(timezone.utc)
                db.commit()
                continue
            try:
                ensure_message_delivery_allowed(
                    db,
                    conversation=conversation,
                    message=message,
                )
            except SmsOperationConflict:
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="DELIVERY_STATE_BLOCKED",
                )
                continue
            if not is_outbound_body_safe(message.body):
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="DELIVERY_SAFETY_BLOCKED",
                )
                continue

            # Route Chatwoot-bound outbound messages directly
            if is_chatwoot_thread:
                current_message_id = message.id
                try:
                    from .chatwoot_service import send_chatwoot_message
                    # Persist a deterministic source ID before the network
                    # call. Chatwoot echoes it in its webhook, which closes
                    # the race where the echo can arrive before this worker
                    # receives Chatwoot's response message ID.
                    source_id = f"fastapi-chatwoot-message-{current_message_id}"
                    message.status = "sending"
                    db.flush()

                    mock_msg_id = await send_chatwoot_message(
                        db,
                        conversation,
                        message.body,
                        source_id=source_id,
                    )

                    job.status = "SUCCESS"
                    job.processed_at = datetime.now(timezone.utc)
                    message.status = "sent"
                    message.chatwoot_message_id = mock_msg_id
                    db.commit()
                    logger.info(
                        "Outbound Chatwoot delivery succeeded (message_id=%s).",
                        message.id,
                    )
                    continue
                except Exception:
                    db.rollback()
                    if _recover_chatwoot_delivery_after_error(
                        db,
                        job_id=job_id,
                        message_id=current_message_id,
                    ):
                        continue
                    continue

            if (
                conversation.chatwoot_conversation_id is not None
                or conversation.chatwoot_inbox_id is not None
                or conversation.sms_account_id is None
            ):
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="DELIVERY_CHANNEL_UNAVAILABLE",
                )
                continue

            # SMS specific flow requires account
            account = db.query(SmsAccount).filter(
                SmsAccount.id == job.sms_account_id,
                SmsAccount.tenant_id == conversation.tenant_id,
                SmsAccount.provider_id == conversation.provider_id,
                SmsAccount.id == conversation.sms_account_id,
            ).first()
            if not account:
                logger.error("Outbound job has no scoped SMS account (job_id=%s).", job.id)
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="ACCOUNT_MISSING",
                )
                continue

            # Check if account is enabled
            if not account.is_enabled:
                logger.warning("Outbound job account is disabled (job_id=%s).", job.id)
                _quarantine_delivery_job(
                    db,
                    job=job,
                    message=message,
                    conversation=conversation,
                    reason="ACCOUNT_DISABLED",
                )
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
                    raise ValueError("Invalid customer destination.")

                # Prepare command
                command = OutboundSmsCommand(
                    to=clean_to,
                    body=message.body,
                    # Stable idempotency key across retries
                    idempotency_key=f"outbound-{message.id}"
                )

                # Send via transport adapter
                message.status = "sending"
                db.flush()

                result = await adapter.send(account, command)

                if result.status == "success":
                    job.status = "SUCCESS"
                    job.processed_at = datetime.now(timezone.utc)
                    message.status = "sent"
                    message.provider_message_id = result.provider_message_id
                    logger.info("Outbound SMS delivery succeeded (message_id=%s).", message.id)
                else:
                    raise RuntimeError("Transport rejected outbound command.")

            except Exception:
                db.rollback()
                job.retry_count += 1
                job.error_log = "CARRIER_DELIVERY_FAILED"
                
                if job.retry_count >= 5:
                    job.status = "FAILED"
                    message.status = "failed"
                    logger.error(
                        "Permanent outbound delivery failure (job_id=%s).", job.id
                    )
                else:
                    # Return to PENDING for retry
                    job.status = "PENDING"
                    job.lease_expires_at = None
                    message.status = "queued"
                    logger.warning(
                        "Temporary outbound delivery failure (job_id=%s, attempt=%s).",
                        job.id,
                        job.retry_count,
                    )

            db.commit()

        # Run AI jobs processing turn
        try:
            from .ai_orchestrator import process_pending_sms_ai_jobs
            await process_pending_sms_ai_jobs(db)
        except Exception:
            db.rollback()
            logger.error("Background AI job execution failed.")

        # Run repeated arrival alerts processing
        try:
            from .arrival_service import process_repeated_arrival_alerts
            process_repeated_arrival_alerts(db)
        except Exception:
            db.rollback()
            logger.error("Repeated arrival alert execution failed.")

    finally:
        if should_close:
            db.close()
