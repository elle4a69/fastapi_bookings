"""Telemetry and Service Sentinel for Resident Autonomous Agent.

Queries local telemetry pipeline status, inspects SMS outbox queues and retry
backlogs, validates Chatwoot webhook sync configurations, and computes a composite
Health Score (0-100%).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ...core.telemetry import get_telemetry_status_data
from ...models.sms_outbox import SmsOutboundJob, SmsAiJob
from ...models.outbox import OutboxEvent
from ...models.webhook import WebhookDelivery
from ...models.sms_chatwoot import SmsChatwootBinding

logger = logging.getLogger(__name__)


class TelemetrySentinel:
    """Monitors telemetry pipelines, queues, and messaging backlogs."""

    def inspect_telemetry_pipeline(self) -> Dict[str, Any]:
        """Query observability baseline without leaking secrets."""
        try:
            status = get_telemetry_status_data()
            return {
                "telemetry_enabled": status.get("telemetry_enabled", False),
                "trace_exporter_active": status.get("trace_exporter_active", False),
                "metric_exporter_active": status.get("metric_exporter_active", False),
                "log_exporter_active": status.get("log_exporter_active", False),
                "service_name": status.get("service_name", "fastapi-bookings"),
                "environment": status.get("environment", "development"),
                "last_export_status": status.get("last_export_status", "unknown"),
            }
        except Exception as exc:
            logger.warning("Failed to query telemetry status: %s", exc)
            return {
                "telemetry_enabled": False,
                "error": str(exc),
            }

    def inspect_sms_outbox_queue(self, db: Session) -> Dict[str, Any]:
        """Check SMS outbound jobs, failures, and retry backlogs."""
        try:
            total_jobs = db.query(SmsOutboundJob).count()
            pending_jobs = db.query(SmsOutboundJob).filter(SmsOutboundJob.status == "PENDING").count()
            processing_jobs = db.query(SmsOutboundJob).filter(SmsOutboundJob.status == "PROCESSING").count()
            failed_jobs = db.query(SmsOutboundJob).filter(SmsOutboundJob.status == "FAILED").count()
            success_jobs = db.query(SmsOutboundJob).filter(SmsOutboundJob.status == "SUCCESS").count()
            retry_backlog = db.query(SmsOutboundJob).filter(SmsOutboundJob.retry_count > 0).count()

            # Inspect AI reply jobs
            pending_ai_jobs = db.query(SmsAiJob).filter(SmsAiJob.status == "PENDING").count()

            # Inspect generic outbox events
            unprocessed_events = db.query(OutboxEvent).filter(OutboxEvent.processed == False).count()

            # Inspect webhook deliveries
            dead_letter_deliveries = db.query(WebhookDelivery).filter(WebhookDelivery.status == "DEAD_LETTER").count()
            retry_deliveries = db.query(WebhookDelivery).filter(WebhookDelivery.status == "RETRY").count()

            return {
                "total_sms_jobs": total_jobs,
                "pending_sms_jobs": pending_jobs,
                "processing_sms_jobs": processing_jobs,
                "failed_sms_jobs": failed_jobs,
                "successful_sms_jobs": success_jobs,
                "retry_backlog": retry_backlog,
                "pending_ai_jobs": pending_ai_jobs,
                "unprocessed_outbox_events": unprocessed_events,
                "dead_letter_deliveries": dead_letter_deliveries,
                "retry_deliveries": retry_deliveries,
                "healthy": (failed_jobs == 0 and dead_letter_deliveries == 0 and pending_jobs < 50),
            }
        except Exception as exc:
            logger.warning("Failed to inspect SMS outbox queue: %s", exc)
            return {
                "error": str(exc),
                "healthy": False,
                "total_sms_jobs": 0,
                "failed_sms_jobs": 0,
                "pending_sms_jobs": 0,
                "retry_backlog": 0,
                "unprocessed_outbox_events": 0,
                "dead_letter_deliveries": 0,
            }

    def inspect_chatwoot_sync(self, db: Session) -> Dict[str, Any]:
        """Verify Chatwoot bindings and webhook security configurations."""
        try:
            bindings = db.query(SmsChatwootBinding).all()
            total_bindings = len(bindings)
            active_bindings = sum(1 for b in bindings if b.is_enabled)
            missing_secret_count = sum(1 for b in bindings if not b._webhook_secret)

            return {
                "total_bindings": total_bindings,
                "active_bindings": active_bindings,
                "missing_webhook_secrets": missing_secret_count,
                "healthy": (missing_secret_count == 0),
            }
        except Exception as exc:
            logger.warning("Failed to inspect Chatwoot sync: %s", exc)
            return {
                "error": str(exc),
                "total_bindings": 0,
                "active_bindings": 0,
                "missing_webhook_secrets": 0,
                "healthy": False,
            }

    def compute_health(self, db: Session) -> Dict[str, Any]:
        """Run sentinel inspection, identify issues, and compute composite Health Score (0-100%)."""
        telemetry = self.inspect_telemetry_pipeline()
        outbox = self.inspect_sms_outbox_queue(db)
        chatwoot = self.inspect_chatwoot_sync(db)

        score = 100
        detected_issues: List[Dict[str, Any]] = []

        # 1. Telemetry Sentinel scoring (Max 25 pts)
        if not telemetry.get("telemetry_enabled", False):
            # Development default may disable OTel SDK
            score -= 10
            detected_issues.append({
                "id": "ISSUE-TEL-001",
                "category": "telemetry",
                "title": "OpenTelemetry Exporter Inactive",
                "severity": "INFO",
                "description": "OTel SDK exporter is disabled or operating in local suppression mode.",
            })

        # 2. SMS Outbox queue scoring (Max 35 pts)
        failed_sms = outbox.get("failed_sms_jobs", 0)
        dead_letters = outbox.get("dead_letter_deliveries", 0)
        retry_backlog = outbox.get("retry_backlog", 0)

        if failed_sms > 0:
            deduction = min(25, failed_sms * 5)
            score -= deduction
            detected_issues.append({
                "id": "ISSUE-SMS-001",
                "category": "sms_outbox",
                "title": f"Failed SMS Outbound Jobs ({failed_sms} failed)",
                "severity": "CRITICAL" if failed_sms > 5 else "WARNING",
                "description": f"Found {failed_sms} jobs in FAILED status in the SMS outbound queue.",
            })

        if dead_letters > 0:
            score -= 15
            detected_issues.append({
                "id": "ISSUE-WH-001",
                "category": "webhooks",
                "title": f"Webhook Deliveries in Dead Letter Queue ({dead_letters})",
                "severity": "WARNING",
                "description": f"{dead_letters} webhook deliveries reached max attempts and entered DEAD_LETTER.",
            })

        if retry_backlog > 10:
            score -= 10
            detected_issues.append({
                "id": "ISSUE-SMS-002",
                "category": "sms_outbox",
                "title": f"High SMS Retry Backlog ({retry_backlog} jobs retrying)",
                "severity": "WARNING",
                "description": f"SMS worker is experiencing delivery delays across {retry_backlog} jobs.",
            })

        # 3. Chatwoot sync scoring (Max 20 pts)
        missing_sec = chatwoot.get("missing_webhook_secrets", 0)
        if missing_sec > 0:
            score -= 15
            detected_issues.append({
                "id": "ISSUE-CW-001",
                "category": "chatwoot",
                "title": f"Chatwoot Bindings Missing Webhook Secret ({missing_sec})",
                "severity": "WARNING",
                "description": f"{missing_sec} Chatwoot binding(s) lack a configured webhook secret cipher.",
            })

        composite_score = max(0, min(100, score))

        return {
            "health_score": composite_score,
            "status": "HEALTHY" if composite_score >= 80 else ("DEGRADED" if composite_score >= 50 else "CRITICAL"),
            "telemetry": telemetry,
            "outbox": outbox,
            "chatwoot": chatwoot,
            "detected_issues": detected_issues,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global sentinel singleton
telemetry_sentinel = TelemetrySentinel()
