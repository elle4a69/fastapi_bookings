#!/usr/bin/env python3
"""Operational CLI utility for SaaS Control Plane reconciliation and dead-letter replay (WP5).

Allows SREs and platform operators to:
1. Reconcile local SubscriptionProjections against remote Flexprice state across one or all tenants.
2. Inspect failed/ignored webhook events in the dead-letter inbox.
3. Batch replay failed inbox events through the subscription projection engine.

Usage:
    python scripts/reconcile_saas_control_plane.py --all-tenants
    python scripts/reconcile_saas_control_plane.py --tenant-id 1
    python scripts/reconcile_saas_control_plane.py --inspect-dead-letter --limit 20
    python scripts/reconcile_saas_control_plane.py --replay-failed --limit 50
"""

import argparse
from contextlib import nullcontext
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

# Ensure application path is available
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    ProviderEventInbox,
)
from app.services.platform_billing.reconciliation_service import reconciliation_service
from app.services.platform_billing.projection_service import projection_service
from app.services.platform_billing.flexprice_client import flexprice_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reconcile_saas_control_plane")


def _get_session_context(db: Optional[Session]):
    if db is not None:
        return nullcontext(db)
    return SessionLocal()


def reconcile_tenants(
    tenant_id: Optional[int] = None,
    all_tenants: bool = False,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Run subscription reconciliation between local projections and Flexprice."""
    results = []
    with _get_session_context(db) as session:
        if tenant_id is not None:
            tenants = session.query(Tenant).filter(Tenant.id == tenant_id).all()
        elif all_tenants:
            tenants = session.query(Tenant).order_by(Tenant.id).all()
        else:
            projections = session.query(SubscriptionProjection).all()
            tenant_ids = {p.tenant_id for p in projections}
            tenants = session.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all() if tenant_ids else []

        if not tenants:
            logger.info("No tenants found to reconcile.")
            return results

        logger.info("Reconciling %d tenant(s)...", len(tenants))
        for t in tenants:
            report = reconciliation_service.reconcile_tenant_subscription(
                db=session,
                tenant_id=t.id,
                client=flexprice_client,
            )
            res = {
                "tenant_id": report.tenant_id,
                "tenant_name": t.name,
                "external_subscription_id": report.external_subscription_id,
                "local_status": report.local_status,
                "remote_status": report.remote_status,
                "is_synchronized": report.is_synchronized,
                "discrepancies": report.discrepancy_details,
            }
            results.append(res)
            status_tag = "SYNCED" if report.is_synchronized else "DRIFT_DETECTED"
            logger.info(
                "Tenant %d (%s) -> [%s] local=%s, remote=%s",
                t.id,
                t.name,
                status_tag,
                report.local_status,
                report.remote_status,
            )
    return results


def inspect_dead_letter_inbox(
    limit: int = 50,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Query and display failed or ignored webhook events in the inbox."""
    with _get_session_context(db) as session:
        events = reconciliation_service.get_dead_letter_inbox_events(db=session, limit=limit)
        logger.info("Retrieved %d dead-letter event(s) from inbox.", len(events))
        output = []
        for ev in events:
            item = {
                "id": ev.id,
                "provider": ev.provider,
                "event_id": ev.external_event_id,
                "event_type": ev.event_type,
                "processing_status": ev.processing_status,
                "error_message": ev.error_message,
                "received_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            output.append(item)
            logger.warning(
                "Dead-Letter Event #%d: event_id=%s type=%s status=%s error=%s",
                ev.id,
                ev.external_event_id,
                ev.event_type,
                ev.processing_status,
                ev.error_message,
            )
        return output


def replay_failed_inbox_events(
    limit: int = 50,
    dry_run: bool = False,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Re-process failed or ignored events from the provider inbox."""
    stats = {"inspected": 0, "replayed": 0, "failed": 0, "ignored": 0}
    with _get_session_context(db) as session:
        events = reconciliation_service.get_dead_letter_inbox_events(db=session, limit=limit)
        stats["inspected"] = len(events)
        logger.info("Found %d dead-letter event(s) to replay (dry_run=%s)", len(events), dry_run)

        for ev in events:
            try:
                if dry_run:
                    logger.info("[Dry Run] Would replay event #%d (%s, %s)", ev.id, ev.event_type, ev.external_event_id)
                    stats["replayed"] += 1
                    continue

                # Reset status to allow re-processing and increment retry_count
                ev.retry_count += 1
                ev.processing_status = "pending"
                ev.error_message = None
                ev.processed_at = datetime.now(timezone.utc)
                session.commit()
                stats["replayed"] += 1
                logger.info("Successfully reset event #%d for reprocessing", ev.id)
            except Exception as exc:
                stats["failed"] += 1
                logger.error("Exception replaying event #%d: %s", ev.id, exc)
                ev.processing_status = "failed"
                ev.error_message = f"Replay exception: {str(exc)}"
                session.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SaaS Control Plane Operational Reconciliation & Dead-Letter Replay CLI",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Reconcile all tenants across the platform",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Reconcile a specific tenant by ID",
    )
    parser.add_argument(
        "--inspect-dead-letter",
        action="store_true",
        help="Inspect failed or ignored inbox events without reprocessing",
    )
    parser.add_argument(
        "--replay-failed",
        action="store_true",
        help="Batch replay dead-letter events from provider inbox",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of events to inspect or replay (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without writing database updates",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    args = parser.parse_args()

    if args.inspect_dead_letter:
        items = inspect_dead_letter_inbox(limit=args.limit)
        if args.json:
            print(json.dumps(items, indent=2))
        return

    if args.replay_failed:
        stats = replay_failed_inbox_events(limit=args.limit, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Replay complete: {stats}")
        return

    if args.all_tenants or args.tenant_id is not None:
        reports = reconcile_tenants(tenant_id=args.tenant_id, all_tenants=args.all_tenants)
        if args.json:
            print(json.dumps(reports, indent=2))
        return

    # Default action: reconcile tenants with projections
    reports = reconcile_tenants()
    if args.json:
        print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
