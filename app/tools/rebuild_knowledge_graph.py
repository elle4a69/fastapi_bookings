"""Administrative CLI tool for rebuilding and backfilling the knowledge graph.

Spec references: Sections 56, 57, 58, 59, 60, 61.

Usage:
    python -m app.tools.rebuild_knowledge_graph [--tenant-id ID] [--provider-id ID] [--dry-run] [--verify]

Guarantees:
- Strict multi-tenant and provider isolation.
- Zero credential, secret, or PII output.
- Idempotent and non-destructive dry-run capabilities.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.db.database import SessionLocal
from app.services.knowledge.rebuild import knowledge_rebuild_service


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments for the rebuild CLI tool."""
    parser = argparse.ArgumentParser(
        description="Rebuild and backfill the knowledge graph ledger from PostgreSQL records (Spec 56).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Optional tenant ID to restrict the backfill scope",
    )
    parser.add_argument(
        "--provider-id",
        type=int,
        default=None,
        help="Optional provider ID to restrict the backfill scope",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview candidate and eligibility counts without persisting changes",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify parity between active PostgreSQL records and graph projections",
    )
    return parser.parse_args(args)


def format_summary(result: dict) -> str:
    """Format a clean, privacy-preserving terminal summary (Spec 56)."""
    lines = [
        "",
        "============================================================",
        "             KNOWLEDGE GRAPH REBUILD SUMMARY",
        "============================================================",
        f"Status:            {result.get('status', 'unknown')}",
        f"Dry Run:           {result.get('dry_run', False)}",
        f"Tenant Scope:      {result.get('tenant_id') if result.get('tenant_id') is not None else 'ALL'}",
        f"Provider Scope:    {result.get('provider_id') if result.get('provider_id') is not None else 'ALL'}",
        "------------------------------------------------------------",
        f"Total Scanned:     {result.get('total_scanned', 0)}",
        f"Total Eligible:    {result.get('total_eligible', 0)}",
        f"Total Projected:   {result.get('total_projected', 0)}",
        f"Total Skipped:     {result.get('total_skipped', 0)}",
        f"Total Rejected:    {result.get('total_rejected', 0)}",
        "------------------------------------------------------------",
    ]

    curated = result.get("curated_memories", {})
    lines.extend([
        "Curated Memories:",
        f"  - Scanned:       {curated.get('scanned', 0)}",
        f"  - Eligible:      {curated.get('eligible', 0)}",
        f"  - Projected:     {curated.get('projected', 0)}",
        f"  - Skipped:       {curated.get('skipped', 0)}",
        f"  - Rejected:      {curated.get('rejected', 0)}",
    ])

    sms = result.get("legacy_sms_knowledge", {})
    lines.extend([
        "Legacy SMS Knowledge:",
        f"  - Scanned:       {sms.get('scanned', 0)}",
        f"  - Eligible:      {sms.get('eligible', 0)}",
        f"  - Created:       {sms.get('curated_created', 0)}",
        f"  - Projected:     {sms.get('projected', 0)}",
        f"  - Skipped:       {sms.get('skipped', 0)}",
        f"  - Rejected:      {sms.get('rejected', 0)}",
        "------------------------------------------------------------",
    ])

    parity = result.get("parity")
    if parity:
        status_str = "PASSED (100% PARITY)" if parity.get("parity_ok") else "MISMATCH DETECTED"
        lines.extend([
            "Parity Verification (PostgreSQL vs Graph Projections):",
            f"  - Status:                {status_str}",
            f"  - Total Valid Memories:  {parity.get('total_memories', 0)}",
            f"  - Total Ledger Items:    {parity.get('total_projections', 0)}",
            f"  - Missing Projections:   {parity.get('missing_projections_count', 0)}",
            "============================================================",
        ])
    else:
        lines.append("============================================================")

    return "\n".join(lines)


def main(args: Optional[list[str]] = None) -> int:
    """CLI execution entrypoint."""
    parsed = parse_args(args)
    db = SessionLocal()
    try:
        result = knowledge_rebuild_service.rebuild_graph(
            db=db,
            tenant_id=parsed.tenant_id,
            provider_id=parsed.provider_id,
            dry_run=parsed.dry_run,
            verify=parsed.verify,
        )
        print(format_summary(result))
        return 0
    except Exception as exc:
        print(f"Error executing knowledge graph rebuild: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
