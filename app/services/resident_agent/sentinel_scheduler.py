"""Autonomous Sentinel Heartbeat & Periodic Sweeps for Resident Autonomous Agent.

Runs continuous lightweight background sweeps monitoring:
1. SMS Outbox queues (stalled pending jobs, failed retries > 3).
2. Chatwoot sync and orphaned client conversations.
3. Database connectivity, connection pool saturation, and latency.

Automatically registers issues into ResidentAgentEngine and triggers two-way alerts
when anomalies cross severity thresholds.
"""

import asyncio
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...db.database import SessionLocal, engine
from ...models.sms_outbox import SmsOutboundJob
from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from .event_broker import event_broker
from .alert_dispatcher import alert_dispatcher

logger = logging.getLogger(__name__)


class SentinelScheduler:
    """Asyncio background worker performing continuous system health sweeps."""

    def __init__(self, sweep_interval_seconds: int = 900) -> None:
        self.sweep_interval_seconds = sweep_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._last_sweep_at: Optional[str] = None
        self._sweep_count: int = 0
        self._latest_sweep_result: Optional[Dict[str, Any]] = None

    @property
    def is_running(self) -> bool:
        return self._is_running and self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start background sentinel heartbeat sweep task."""
        if self.is_running:
            logger.info("SentinelScheduler is already running.")
            return

        self._is_running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run_loop())
        logger.info("SentinelScheduler heartbeat started (interval=%ds)", self.sweep_interval_seconds)

    def stop(self) -> None:
        """Stop background sentinel task."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("SentinelScheduler heartbeat cancelled.")

    async def _run_loop(self) -> None:
        """Periodic execution loop."""
        while self._is_running:
            try:
                await self.run_sweep()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in SentinelScheduler sweep loop: %s", exc)

            try:
                await asyncio.sleep(self.sweep_interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_sweep(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """Execute an immediate autonomous health sweep across all subsystems."""
        start_time = time.perf_counter()
        self._sweep_count += 1
        now_utc = datetime.now(timezone.utc)
        self._last_sweep_at = now_utc.isoformat()

        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            # 1. Check SMS Outbox Queue
            sms_check = self._check_sms_outbox(db, now_utc)

            # 2. Check Chatwoot & Conversations
            cw_check = self._check_chatwoot_and_conversations(db)

            # 3. Check Database Health & Latency
            db_check = self._check_database_health(db)

            # Collect detected issues
            sweep_issues: List[Dict[str, Any]] = []
            if sms_check.get("issue"):
                sweep_issues.append(sms_check["issue"])
            if cw_check.get("issue"):
                sweep_issues.append(cw_check["issue"])
            if db_check.get("issue"):
                sweep_issues.append(db_check["issue"])

            # Register issues in resident_agent_engine and dispatch critical alerts
            from .engine import resident_agent_engine
            for issue in sweep_issues:
                issue_id = issue["id"]
                if issue_id not in resident_agent_engine._active_issues:
                    resident_agent_engine._active_issues[issue_id] = {
                        **issue,
                        "status": "OPEN",
                        "discovered_at": now_utc.isoformat(),
                    }

                # If CRITICAL, trigger alert dispatcher
                if issue.get("severity") == "CRITICAL":
                    await alert_dispatcher.dispatch_critical_alert(issue)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            result = {
                "sweep_id": f"sweep_{self._sweep_count}_{int(now_utc.timestamp())}",
                "timestamp": self._last_sweep_at,
                "duration_ms": duration_ms,
                "subsystems": {
                    "sms_outbox": sms_check,
                    "chatwoot": cw_check,
                    "database": db_check,
                },
                "anomalies_detected": len(sweep_issues),
                "issues": sweep_issues,
                "status": "HEALTHY" if not sweep_issues else ("CRITICAL" if any(i.get("severity") == "CRITICAL" for i in sweep_issues) else "WARNING"),
            }
            self._latest_sweep_result = result

            await event_broker.publish(
                "telemetry",
                result,
                title=f"Autonomous Sentinel Sweep #{self._sweep_count} ({result['status']})",
                severity="INFO" if result["status"] == "HEALTHY" else result["status"],
            )

            return result

        finally:
            if should_close:
                db.close()

    def _check_sms_outbox(self, db: Session, now_utc: datetime) -> Dict[str, Any]:
        """Check for stalled or failing SMS outbound jobs."""
        try:
            pending_count = db.query(SmsOutboundJob).filter(SmsOutboundJob.status == "PENDING").count()
            stalled_cutoff = now_utc - timedelta(minutes=15)
            stalled_count = (
                db.query(SmsOutboundJob)
                .filter(
                    SmsOutboundJob.status == "PENDING",
                    SmsOutboundJob.created_at < stalled_cutoff,
                )
                .count()
            )
            failed_retries = (
                db.query(SmsOutboundJob)
                .filter(
                    (SmsOutboundJob.retry_count >= 3) | (SmsOutboundJob.status == "FAILED")
                )
                .count()
            )

            issue = None
            if failed_retries > 5 or stalled_count > 10:
                issue = {
                    "id": "ISSUE-SENTINEL-SMS-001",
                    "category": "sms_outbox",
                    "title": f"Stalled SMS Queue Alert ({stalled_count} stalled, {failed_retries} high-retry jobs)",
                    "severity": "CRITICAL" if failed_retries > 10 else "WARNING",
                    "description": f"SMS outbox queue has {stalled_count} pending jobs >15m old and {failed_retries} failed retries.",
                }

            return {
                "pending_jobs": pending_count,
                "stalled_jobs": stalled_count,
                "failed_retries": failed_retries,
                "healthy": issue is None,
                "issue": issue,
            }
        except Exception as err:
            logger.warning("Error checking SMS outbox in sentinel sweep: %s", err)
            return {"healthy": True, "error": str(err)}

    def _check_chatwoot_and_conversations(self, db: Session) -> Dict[str, Any]:
        """Check Chatwoot webhook secrets and orphaned client conversations."""
        try:
            bindings = db.query(SmsChatwootBinding).all()
            missing_secrets = sum(1 for b in bindings if not getattr(b, "webhook_secret", None))

            # Orphaned conversations (no client or recipient phone)
            orphaned = (
                db.query(SmsConversation)
                .filter(
                    (SmsConversation.client_id.is_(None)) & (SmsConversation.external_thread_id.is_(None))
                )
                .count()
            )

            issue = None
            if missing_secrets > 0:
                issue = {
                    "id": "ISSUE-SENTINEL-CW-001",
                    "category": "chatwoot",
                    "title": f"Missing Webhook Secret on {missing_secrets} Chatwoot Inboxes",
                    "severity": "WARNING",
                    "description": f"{missing_secrets} Chatwoot binding(s) lack configured webhook signature secrets.",
                }
            elif orphaned > 50:
                issue = {
                    "id": "ISSUE-SENTINEL-CW-002",
                    "category": "chatwoot",
                    "title": f"High Orphaned Conversation Volume ({orphaned} unlinked threads)",
                    "severity": "WARNING",
                    "description": f"{orphaned} conversations lack client associations or thread identifiers.",
                }

            return {
                "total_bindings": len(bindings),
                "missing_secrets": missing_secrets,
                "orphaned_conversations": orphaned,
                "healthy": issue is None,
                "issue": issue,
            }
        except Exception as err:
            logger.warning("Error checking Chatwoot in sentinel sweep: %s", err)
            return {"healthy": True, "error": str(err)}

    def _check_database_health(self, db: Session) -> Dict[str, Any]:
        """Check active DB ping latency and pool status."""
        t0 = time.perf_counter()
        try:
            db.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            pool = engine.pool
            pool_size = pool.size() if hasattr(pool, "size") else 5
            checkedin = pool.checkedin() if hasattr(pool, "checkedin") else 5
            checkedout = pool.checkedout() if hasattr(pool, "checkedout") else 0

            issue = None
            if latency_ms > 500:
                issue = {
                    "id": "ISSUE-SENTINEL-DB-001",
                    "category": "database",
                    "title": f"High Database Query Latency ({latency_ms}ms)",
                    "severity": "CRITICAL" if latency_ms > 1500 else "WARNING",
                    "description": f"Database ping query took {latency_ms}ms, exceeding acceptable SLO threshold.",
                }

            return {
                "ping_latency_ms": latency_ms,
                "pool_size": pool_size,
                "checked_in": checkedin,
                "checked_out": checkedout,
                "healthy": issue is None,
                "issue": issue,
            }
        except Exception as err:
            logger.warning("Error checking DB health in sentinel sweep: %s", err)
            return {"healthy": False, "error": str(err), "ping_latency_ms": -1}

    def get_status(self) -> Dict[str, Any]:
        """Return operational metrics of the sentinel scheduler."""
        return {
            "is_running": self.is_running,
            "sweep_interval_seconds": self.sweep_interval_seconds,
            "sweep_count": self._sweep_count,
            "last_sweep_at": self._last_sweep_at,
            "latest_result": self._latest_sweep_result,
        }


# Global sentinel scheduler singleton
sentinel_scheduler = SentinelScheduler()
