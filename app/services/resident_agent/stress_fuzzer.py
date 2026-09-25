"""Synthetic Concurrency & Race-Condition Fuzzer for Resident Autonomous Agent.

Simulates high-density concurrent booking requests attempting to claim the exact same
calendar slot and provider simultaneously. Validates transactional integrity, verifies
single-winner lock guarantees (zero double-bookings), and calculates contention metrics.
"""

import time
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db.database import SessionLocal
from ...core.state_machine import BookingStatus
from ...models.tenant import Tenant
from ...models.provider import Provider
from ...models.client import Client
from ...models.service import Service
from ...models.booking import Booking
from ...models.booking_slot_allocation import BookingSlotAllocation
from ..slot_allocation_service import is_slot_allocation_conflict
from .event_broker import event_broker

logger = logging.getLogger(__name__)


class ConcurrencyStressFuzzer:
    """Fuzzer evaluating database transaction isolation and slot reservation locks."""

    def __init__(self) -> None:
        self.latest_fuzz_result: Optional[Dict[str, Any]] = None

    async def run_race_condition_test(
        self,
        db: Session,
        concurrency: int = 15,
        target_slot: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Execute concurrent simulated booking requests on the exact same slot.
        
        Guarantees:
        1. Exactly 1 booking attempt commits successfully.
        2. All other N-1 attempts receive clean conflict rejections.
        3. Zero double-bookings occur.
        """
        clamped_concurrency = max(2, min(concurrency, 50))
        test_id = uuid.uuid4().hex[:6]

        await event_broker.publish(
            "thought",
            f"Initiating synthetic concurrency fuzzing: {clamped_concurrency} concurrent threads claiming identical slot...",
            title="Concurrency Fuzzer Started",
        )

        # 1. Resolve or establish test fixture context
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name=f"Fuzz Tenant {test_id}", subdomain=f"fuzz-{test_id}")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        provider = db.query(Provider).filter(Provider.tenant_id == tenant.id).first()
        if not provider:
            provider = Provider(
                tenant_id=tenant.id,
                name=f"Fuzz Provider {test_id}",
                email=f"fuzz_{test_id}@example.com",
            )
            db.add(provider)
            db.commit()
            db.refresh(provider)

        client = db.query(Client).filter(Client.tenant_id == tenant.id).first()
        if not client:
            client = Client(
                tenant_id=tenant.id,
                name=f"Fuzz Client {test_id}",
                email=f"fuzz_client_{test_id}@example.com",
            )
            db.add(client)
            db.commit()
            db.refresh(client)

        service = db.query(Service).filter(Service.tenant_id == tenant.id).first()
        if not service:
            service = Service(
                tenant_id=tenant.id,
                name=f"Fuzz Service {test_id}",
                duration=30,
            )
            db.add(service)
            db.commit()
            db.refresh(service)

        # Generate a distinct slot in the future to avoid colliding with real bookings
        future_day = 100 + (hash(test_id) % 200)
        slot_start = target_slot or (datetime.now(timezone.utc) + timedelta(days=future_day)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        slot_end = slot_start + timedelta(minutes=30)

        await event_broker.publish(
            "step",
            {
                "concurrency": clamped_concurrency,
                "provider_id": provider.id,
                "slot_start": slot_start.isoformat(),
            },
            title=f"Dispatched {clamped_concurrency} Concurrent Workers",
        )

        overall_start = time.perf_counter()

        def _worker_attempt(worker_idx: int) -> Dict[str, Any]:
            w_start = time.perf_counter()
            worker_session = SessionLocal()
            try:
                # Attempt to allocate the exact same discrete slot
                b = Booking(
                    tenant_id=tenant.id,
                    client_id=client.id,
                    provider_id=provider.id,
                    service_id=service.id,
                    start_time=slot_start,
                    end_time=slot_end,
                    status=BookingStatus.CONFIRMED,
                )
                worker_session.add(b)
                worker_session.flush()

                allocation = BookingSlotAllocation(
                    tenant_id=tenant.id,
                    booking_id=b.id,
                    provider_id=provider.id,
                    slot_start=slot_start,
                )
                worker_session.add(allocation)
                worker_session.commit()

                w_latency = round((time.perf_counter() - w_start) * 1000, 2)
                return {
                    "worker_index": worker_idx,
                    "booking_id": b.id,
                    "status": "SUCCESS",
                    "latency_ms": w_latency,
                    "error": None,
                }
            except IntegrityError as ie:
                worker_session.rollback()
                w_latency = round((time.perf_counter() - w_start) * 1000, 2)
                is_conflict = is_slot_allocation_conflict(ie)
                return {
                    "worker_index": worker_idx,
                    "booking_id": None,
                    "status": "CONFLICT",
                    "is_slot_conflict": is_conflict,
                    "latency_ms": w_latency,
                    "error": "Slot already claimed by concurrent transaction",
                }
            except Exception as e:
                worker_session.rollback()
                w_latency = round((time.perf_counter() - w_start) * 1000, 2)
                return {
                    "worker_index": worker_idx,
                    "booking_id": None,
                    "status": "ERROR",
                    "latency_ms": w_latency,
                    "error": str(e),
                }
            finally:
                worker_session.close()

        # Fire all requests concurrently using threadpool
        with ThreadPoolExecutor(max_workers=clamped_concurrency) as executor:
            futures = [
                executor.submit(_worker_attempt, i)
                for i in range(clamped_concurrency)
            ]
            results = [f.result() for f in futures]

        total_duration_ms = round((time.perf_counter() - overall_start) * 1000, 2)

        # Analyze metrics
        successes = [r for r in results if r["status"] == "SUCCESS"]
        conflicts = [r for r in results if r["status"] == "CONFLICT"]
        errors = [r for r in results if r["status"] == "ERROR"]

        success_count = len(successes)
        conflict_count = len(conflicts)
        double_bookings = max(0, success_count - 1)
        latencies = [r["latency_ms"] for r in results]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        # Lock contention time: time spent waiting in rejected threads
        contention_latencies = [r["latency_ms"] for r in conflicts]
        avg_contention_ms = round(sum(contention_latencies) / len(contention_latencies), 2) if contention_latencies else 0.0

        double_bookings_prevented_pct = 100.0 if double_bookings == 0 and success_count == 1 else 0.0
        conflict_rate_pct = round((conflict_count / clamped_concurrency) * 100, 2)

        fuzz_report = {
            "test_id": f"fuzz_race_{test_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_provider_id": provider.id,
            "target_slot": slot_start.isoformat(),
            "concurrency_tested": clamped_concurrency,
            "successful_bookings": success_count,
            "conflicts_prevented": conflict_count,
            "unexpected_errors": len(errors),
            "double_bookings_occurred": double_bookings,
            "double_bookings_prevented_pct": double_bookings_prevented_pct,
            "conflict_rate_pct": conflict_rate_pct,
            "total_duration_ms": total_duration_ms,
            "avg_latency_ms": avg_latency,
            "avg_lock_contention_ms": avg_contention_ms,
            "max_latency_ms": max_latency,
            "transactional_integrity_verified": (success_count == 1 and double_bookings == 0),
            "sample_worker_results": results[:5],
        }

        self.latest_fuzz_result = fuzz_report

        # Publish event
        await event_broker.publish(
            "step",
            fuzz_report,
            title=f"Race-Condition Fuzzer Completed: {double_bookings_prevented_pct}% Prevention ({conflict_count}/{clamped_concurrency} conflicts handled)",
            severity="INFO" if fuzz_report["transactional_integrity_verified"] else "CRITICAL",
        )

        # Cleanup transient fuzz slot allocations and bookings to leave DB pristine
        try:
            db.query(BookingSlotAllocation).filter(
                BookingSlotAllocation.provider_id == provider.id,
                BookingSlotAllocation.slot_start == slot_start,
            ).delete(synchronize_session=False)
            db.query(Booking).filter(
                Booking.provider_id == provider.id,
                Booking.start_time == slot_start,
            ).delete(synchronize_session=False)
            db.commit()
        except Exception as cleanup_err:
            logger.warning("Error cleaning up fuzz allocations: %s", cleanup_err)
            db.rollback()

        return fuzz_report


# Global fuzzer singleton
stress_fuzzer = ConcurrencyStressFuzzer()
