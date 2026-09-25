"""Autonomous background worker for processing pending KnowledgeGraphProjection records.

Spec references: Sections 28–36, 67–69.
Implements worker claiming and leasing with skip-locked, Graphiti projection execution,
exponential retry backoff (Spec 68), max retry exhaustion to dead_letter (Spec 69),
and multi-tenant safe isolation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection, utc_now
from app.models.learning_event import LearningEvent
from app.services.knowledge.projection_service import projection_service

logger = logging.getLogger(__name__)


def process_pending_projections_worker(
    db: Optional[Session] = None,
    batch_size: int = 20,
    max_retries: int = 5,
    worker_id: Optional[str] = None,
) -> Dict[str, int]:
    """Fetch, lease, and process pending/retry KnowledgeGraphProjection records.

    Executes:
      Step 1 (Claiming):
        - Filters: status in ("pending", "retry") or stale "processing" where lease_expires_at < now.
        - Next attempt check: next_attempt_at is None or next_attempt_at <= now.
        - Attempt limit check: attempt_count < max_retries.
        - Uses with_for_update(skip_locked=True) on PostgreSQL.
        - Leases batch: status="processing", lease_owner=worker_uuid, lease_expires_at=now + 2m.
        - Commits lease immediately.
      Step 2 (Execution):
        - For each claimed projection:
          - Fetches associated CuratedMemory and LearningEvent.
          - Validates tenant boundary: projection.tenant_id == curated_memory.tenant_id.
          - Calls projection_service.project_to_graphiti(projection, memory, event).
          - On success:
              status="projected", projected_at=now, graph_episode_uuid=episode_id,
              clear lease, commit.
          - On failure/error:
              rollback transaction.
              increment attempt_count, record last_error.
              If attempt_count >= max_retries:
                  status="dead_letter" (Spec 69), next_attempt_at=None.
              Else:
                  status="retry", next_attempt_at=now + 10*(2^attempt_count) (Spec 68).
              Clear lease, commit error state.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    effective_worker_id = worker_id or f"projection-worker-{uuid.uuid4()}"

    try:
        now = utc_now()

        # Step 1: Claiming filter
        claim_filter = and_(
            or_(
                KnowledgeGraphProjection.status.in_(["pending", "retry"]),
                and_(
                    KnowledgeGraphProjection.status == "processing",
                    KnowledgeGraphProjection.lease_expires_at.is_not(None),
                    KnowledgeGraphProjection.lease_expires_at < now,
                ),
            ),
            or_(
                KnowledgeGraphProjection.next_attempt_at.is_(None),
                KnowledgeGraphProjection.next_attempt_at <= now,
            ),
            KnowledgeGraphProjection.attempt_count < max_retries,
        )

        query = (
            db.query(KnowledgeGraphProjection)
            .filter(claim_filter)
            .order_by(KnowledgeGraphProjection.created_at.asc())
            .limit(batch_size)
        )

        is_pg = (db.get_bind().dialect.name == "postgresql") if db.get_bind() else False
        if is_pg:
            query = query.with_for_update(skip_locked=True)

        candidates = query.all()
        if not candidates:
            return {"claimed": 0, "projected": 0, "retried": 0, "dead_letter": 0}

        # Step 2: Atomic Lease Acquisition
        claimed_projection_ids: List[str] = []
        lease_expires = now + timedelta(minutes=2)

        for candidate in candidates:
            try:
                rows = (
                    db.query(KnowledgeGraphProjection)
                    .filter(
                        KnowledgeGraphProjection.id == candidate.id,
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
                    claimed_projection_ids.append(candidate.id)
            except Exception as lease_err:
                logger.error(
                    "Failed to lease KnowledgeGraphProjection %s: %s",
                    candidate.id,
                    lease_err,
                )

        db.commit()

        # Step 3: Execution of Claimed Projections
        projected_count = 0
        retried_count = 0
        dead_letter_count = 0

        for proj_id in claimed_projection_ids:
            projection = (
                db.query(KnowledgeGraphProjection)
                .filter(
                    KnowledgeGraphProjection.id == proj_id,
                    KnowledgeGraphProjection.lease_owner == effective_worker_id,
                    KnowledgeGraphProjection.status == "processing",
                )
                .first()
            )
            if not projection:
                continue

            try:
                memory = None
                if projection.curated_memory_id:
                    memory = (
                        db.query(CuratedMemory)
                        .filter(CuratedMemory.id == projection.curated_memory_id)
                        .first()
                    )

                event = None
                if projection.learning_event_id:
                    event = (
                        db.query(LearningEvent)
                        .filter(LearningEvent.id == projection.learning_event_id)
                        .first()
                    )

                # Tenant boundary validation (Spec 34, multi-tenant isolation)
                if memory and projection.tenant_id != memory.tenant_id:
                    raise ValueError(
                        f"Tenant isolation mismatch: projection tenant {projection.tenant_id} "
                        f"!= memory tenant {memory.tenant_id}"
                    )
                if event and projection.tenant_id != event.tenant_id:
                    raise ValueError(
                        f"Tenant isolation mismatch: projection tenant {projection.tenant_id} "
                        f"!= event tenant {event.tenant_id}"
                    )

                episode_id = projection_service.project_to_graphiti(
                    projection=projection,
                    memory=memory,
                    event=event,
                )

                now_success = utc_now()
                projection.status = "projected"
                projection.projected_at = now_success
                projection.graph_episode_uuid = episode_id
                projection.lease_owner = None
                projection.lease_expires_at = None
                db.commit()
                projected_count += 1
                logger.debug(
                    "Successfully projected KnowledgeGraphProjection %s to episode %s (tenant=%s)",
                    proj_id,
                    episode_id,
                    projection.tenant_id,
                )

            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Projection worker failed processing projection %s (tenant=%s): %s",
                    proj_id,
                    getattr(projection, "tenant_id", "unknown"),
                    exc,
                )

                try:
                    err_proj = (
                        db.query(KnowledgeGraphProjection)
                        .filter(KnowledgeGraphProjection.id == proj_id)
                        .first()
                    )
                    if err_proj:
                        err_now = utc_now()
                        err_proj.attempt_count += 1
                        err_proj.last_error = str(exc)
                        err_proj.lease_owner = None
                        err_proj.lease_expires_at = None

                        if err_proj.attempt_count >= max_retries:
                            err_proj.status = "dead_letter"
                            err_proj.next_attempt_at = None
                            dead_letter_count += 1
                            logger.error(
                                "KnowledgeGraphProjection %s marked dead_letter after %d attempts: %s",
                                proj_id,
                                err_proj.attempt_count,
                                exc,
                            )
                        else:
                            err_proj.status = "retry"
                            backoff_seconds = 10 * (2 ** err_proj.attempt_count)
                            err_proj.next_attempt_at = err_now + timedelta(seconds=backoff_seconds)
                            retried_count += 1
                            logger.info(
                                "KnowledgeGraphProjection %s scheduled for retry in %ds (attempt %d)",
                                proj_id,
                                backoff_seconds,
                                err_proj.attempt_count,
                            )
                        db.commit()
                except Exception as update_err:
                    db.rollback()
                    logger.error(
                        "Failed to update error state for projection %s: %s",
                        proj_id,
                        update_err,
                    )

        return {
            "claimed": len(claimed_projection_ids),
            "projected": projected_count,
            "retried": retried_count,
            "dead_letter": dead_letter_count,
        }

    finally:
        if should_close:
            db.close()


class ProjectionWorker:
    """Class wrapper for the Graphiti projection background worker."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        batch_size: int = 20,
        max_retries: int = 5,
    ):
        self.worker_id = worker_id or f"projection-worker-{uuid.uuid4()}"
        self.batch_size = batch_size
        self.max_retries = max_retries

    def process_batch(self, db: Optional[Session] = None) -> Dict[str, int]:
        """Process a single batch of pending/retry projections."""
        return process_pending_projections_worker(
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
        await start_projection_worker_loop(
            interval_seconds=interval_seconds,
            stop_event=stop_event,
            worker=self,
        )


async def start_projection_worker_loop(
    interval_seconds: float = 5.0,
    stop_event: Optional[asyncio.Event] = None,
    worker: Optional[ProjectionWorker] = None,
) -> None:
    """Continuous async runner for Graphiti projection worker polling loop with graceful shutdown."""
    if stop_event is None:
        stop_event = asyncio.Event()

    active_worker = worker or ProjectionWorker()
    logger.info(
        "Projection worker loop started (worker_id=%s, interval=%.1fs)",
        active_worker.worker_id,
        interval_seconds,
    )

    while not stop_event.is_set():
        try:
            await asyncio.to_thread(active_worker.process_batch)
        except Exception as exc:
            logger.error("Error during Projection worker loop execution: %s", exc, exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

    logger.info("Projection worker loop stopped gracefully")


if __name__ == "__main__":
    import signal

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received for Projection worker")
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
        loop.run_until_complete(start_projection_worker_loop(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Projection worker interrupted, exiting...")
    finally:
        loop.close()

