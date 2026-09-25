"""Autonomous background worker for processing pending LearningEvents.

Spec references: Sections 30, 31, 70, 71, 72, 73.
Implements worker leasing, retry with exponential backoff, max retry exhaustion,
and multi-tenant safe curation execution.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.learning_event import LearningEvent
from app.services.knowledge.curator import unified_curator

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def process_pending_learning_events_worker(
    db: Optional[Session] = None,
    batch_size: int = 20,
    max_retries: int = 5,
    worker_id: Optional[str] = None,
) -> Dict[str, int]:
    """Fetch, lease, and process pending/retry LearningEvents across all tenants.

    Executes:
      Step 1 (Claiming): Select eligible events (pending/retry or stale processing where lease_expires_at < now()).
      Step 2 (Atomic Lease): Set status="processing", lease_owner=worker_uuid, lease_expires_at=now + 2m.
      Step 3 (Execution): Run UnifiedCurator on each event with expected_tenant_id.
             On success: status="processed", processed_at=now, clear lease.
             On failure: increment attempt_count, record last_error, compute exponential backoff or mark failed.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    effective_worker_id = worker_id or f"curator-worker-{uuid.uuid4()}"

    try:
        now = utc_now()

        # Step 1: Claiming filter
        claim_filter = and_(
            or_(
                LearningEvent.status.in_(["pending", "retry"]),
                and_(
                    LearningEvent.status == "processing",
                    LearningEvent.lease_expires_at.is_not(None),
                    LearningEvent.lease_expires_at < now,
                ),
            ),
            or_(
                LearningEvent.next_attempt_at.is_(None),
                LearningEvent.next_attempt_at <= now,
            ),
            LearningEvent.attempt_count < max_retries,
        )

        query = (
            db.query(LearningEvent)
            .filter(claim_filter)
            .order_by(LearningEvent.created_at.asc())
            .limit(batch_size)
        )

        is_pg = (db.get_bind().dialect.name == "postgresql") if db.get_bind() else False
        if is_pg:
            query = query.with_for_update(skip_locked=True)

        candidates = query.all()
        if not candidates:
            return {"claimed": 0, "processed": 0, "failed": 0, "retried": 0}

        # Step 2: Atomic Lease Acquisition
        claimed_event_ids: List[str] = []
        lease_expires = now + timedelta(minutes=2)

        for candidate in candidates:
            try:
                rows = (
                    db.query(LearningEvent)
                    .filter(
                        LearningEvent.id == candidate.id,
                        claim_filter,
                    )
                    .update(
                        {
                            "status": "processing",
                            "lease_owner": effective_worker_id,
                            "lease_expires_at": lease_expires,
                        },
                        synchronize_session=False,
                    )
                )
                if rows > 0:
                    claimed_event_ids.append(candidate.id)
            except Exception as lease_err:
                logger.error("Failed to lease LearningEvent %s: %s", candidate.id, lease_err)

        db.commit()

        # Step 3: Execution of Claimed Events
        processed_count = 0
        failed_count = 0
        retried_count = 0

        for event_id in claimed_event_ids:
            event = (
                db.query(LearningEvent)
                .filter(
                    LearningEvent.id == event_id,
                    LearningEvent.lease_owner == effective_worker_id,
                    LearningEvent.status == "processing",
                )
                .first()
            )
            if not event:
                continue

            try:
                # Run curation in transaction with tenant isolation check
                unified_curator.process_learning_event(
                    db, event, expected_tenant_id=event.tenant_id
                )

                now_success = utc_now()
                event.status = "processed"
                event.processed_at = now_success
                event.lease_owner = None
                event.lease_expires_at = None
                db.commit()
                processed_count += 1
                logger.debug(
                    "Curator worker successfully processed LearningEvent %s (tenant=%s)",
                    event_id,
                    event.tenant_id,
                )

            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Curator worker failed processing LearningEvent %s (tenant=%s): %s",
                    event_id,
                    getattr(event, "tenant_id", "unknown"),
                    exc,
                )

                try:
                    err_event = (
                        db.query(LearningEvent)
                        .filter(LearningEvent.id == event_id)
                        .first()
                    )
                    if err_event:
                        err_now = utc_now()
                        err_event.attempt_count += 1
                        err_event.last_error = str(exc)
                        err_event.lease_owner = None
                        err_event.lease_expires_at = None

                        if err_event.attempt_count >= max_retries:
                            err_event.status = "failed"
                            err_event.next_attempt_at = None
                            failed_count += 1
                            logger.error(
                                "LearningEvent %s marked failed after %d attempts: %s",
                                event_id,
                                err_event.attempt_count,
                                exc,
                            )
                        else:
                            err_event.status = "retry"
                            backoff_seconds = 10 * (2 ** err_event.attempt_count)
                            err_event.next_attempt_at = err_now + timedelta(seconds=backoff_seconds)
                            retried_count += 1
                            logger.info(
                                "LearningEvent %s scheduled for retry in %ds (attempt %d)",
                                event_id,
                                backoff_seconds,
                                err_event.attempt_count,
                            )
                        db.commit()
                except Exception as update_err:
                    db.rollback()
                    logger.error(
                        "Failed to update retry metadata for LearningEvent %s: %s",
                        event_id,
                        update_err,
                    )

        return {
            "claimed": len(claimed_event_ids),
            "processed": processed_count,
            "failed": failed_count,
            "retried": retried_count,
        }

    finally:
        if should_close:
            db.close()


class CuratorWorker:
    """Class wrapper for the Curator background worker."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        batch_size: int = 20,
        max_retries: int = 5,
    ):
        self.worker_id = worker_id or f"curator-worker-{uuid.uuid4()}"
        self.batch_size = batch_size
        self.max_retries = max_retries

    def process_batch(self, db: Optional[Session] = None) -> Dict[str, int]:
        """Process a single batch of pending/retry learning events."""
        return process_pending_learning_events_worker(
            db=db,
            batch_size=self.batch_size,
            max_retries=self.max_retries,
            worker_id=self.worker_id,
        )

    async def run_loop(
        self,
        interval_seconds: float = 5.0,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Run the worker continuously until stop_event is signaled."""
        await start_curator_worker_loop(
            interval_seconds=interval_seconds,
            stop_event=stop_event,
            worker=self,
        )


async def start_curator_worker_loop(
    interval_seconds: float = 5.0,
    stop_event: Optional[asyncio.Event] = None,
    worker: Optional[CuratorWorker] = None,
) -> None:
    """Continuous async runner for Curator worker polling loop with graceful shutdown."""
    if stop_event is None:
        stop_event = asyncio.Event()

    active_worker = worker or CuratorWorker()
    logger.info(
        "Curator worker loop started (worker_id=%s, interval=%.1fs)",
        active_worker.worker_id,
        interval_seconds,
    )

    while not stop_event.is_set():
        try:
            await asyncio.to_thread(active_worker.process_batch)
        except Exception as exc:
            logger.error("Error during Curator worker loop execution: %s", exc, exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

    logger.info("Curator worker loop stopped gracefully")


if __name__ == "__main__":
    import signal

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received for Curator worker")
        stop_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except (NotImplementedError, AttributeError):
                pass

    try:
        loop.run_until_complete(start_curator_worker_loop(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Curator worker interrupted, exiting...")
    finally:
        loop.close()

