"""Knowledge Rebuild and Backfill Service.

Spec references: Sections 56, 57, 58, 59, 60, 61.
Provides administrative backfill and graph rebuilding capabilities for historical
CuratedMemory records and legacy SmsKnowledgeEntry items.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.services.curation.pii_scrubber import scrub_pii
from app.services.knowledge.gateway import knowledge_gateway
from app.services.knowledge.graphiti_client import format_group_id
from app.services.knowledge.policy import (
    is_dynamic_operational_data,
    is_system_safety_violation,
    validate_scope,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return aware current UTC timestamp."""
    return datetime.now(timezone.utc)


class KnowledgeRebuildService:
    """Orchestrates historical knowledge backfill, validation, and graph projection.

    Guarantees:
    - Multi-tenant and provider isolation on all scans and writes (Spec 34).
    - Policy enforcement: Dynamic operational data and safety violations are rejected (Specs 19, 58).
    - PII scrubbing on all legacy backfills (Spec 75).
    - Idempotency: Duplicate projections are avoided via (curated_memory_id, projection_type) checks (Spec 32).
    - Safe dry-run mode without database mutations.
    """

    def backfill_curated_memories(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Backfill existing CuratedMemory records into KnowledgeGraphProjection ledger.

        Spec references: Sections 58, 60.
        Scans CuratedMemory records matching tenant/provider filters.
        Enforces scope validity, dynamic operational data rejection, safety violations,
        and authority checks.
        Filters: active memories and historical superseded records (Spec 60).
        """
        query = db.query(CuratedMemory)
        if tenant_id is not None:
            query = query.filter(CuratedMemory.tenant_id == tenant_id)
        if provider_id is not None:
            query = query.filter(CuratedMemory.provider_id == provider_id)

        memories: List[CuratedMemory] = query.order_by(CuratedMemory.id.asc()).all()

        scanned = 0
        eligible = 0
        projected = 0
        skipped = 0
        rejected = 0
        rejection_reasons: Dict[str, int] = {}

        now = utc_now()

        for mem in memories:
            scanned += 1

            # 1. Filter: active and historical superseded records only (Spec 60)
            if mem.status not in ("active", "superseded"):
                rejected += 1
                reason = f"status_{mem.status}"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                continue

            # 2. Scope validation (Spec 34, 58)
            if not validate_scope(mem.tenant_id, mem.provider_id, mem.tenant_id):
                rejected += 1
                rejection_reasons["invalid_scope"] = rejection_reasons.get("invalid_scope", 0) + 1
                continue

            # 3. Dynamic operational data validation (Spec 19, 58)
            user_q = mem.user_query or ""
            ideal_resp = mem.ideal_response or ""
            if is_dynamic_operational_data(user_q) or is_dynamic_operational_data(ideal_resp):
                rejected += 1
                rejection_reasons["dynamic_operational_data"] = (
                    rejection_reasons.get("dynamic_operational_data", 0) + 1
                )
                continue

            # 4. System safety violation guard (Spec 58)
            if is_system_safety_violation(user_q) or is_system_safety_violation(ideal_resp):
                rejected += 1
                rejection_reasons["safety_violation"] = (
                    rejection_reasons.get("safety_violation", 0) + 1
                )
                continue

            # 5. Authority validation (Spec 58)
            auth = (mem.authority or "").strip().lower()
            if not auth or auth in ("conversation_candidate", "untrusted", "unverified"):
                rejected += 1
                rejection_reasons["insufficient_authority"] = (
                    rejection_reasons.get("insufficient_authority", 0) + 1
                )
                continue

            # Determine projection type
            if mem.status == "superseded" or mem.supersedes_id is not None:
                projection_type = "supersede_fact"
            elif mem.knowledge_kind in ("response_guidance", "style_example", "behaviour_rule"):
                projection_type = "behavioural_guidance"
            else:
                projection_type = "upsert_fact"

            # 6. Idempotency check: check existing projection by (curated_memory_id, projection_type)
            existing_proj = (
                db.query(KnowledgeGraphProjection)
                .filter(
                    KnowledgeGraphProjection.tenant_id == mem.tenant_id,
                    KnowledgeGraphProjection.curated_memory_id == mem.id,
                    KnowledgeGraphProjection.projection_type == projection_type,
                )
                .first()
            )

            eligible += 1

            if existing_proj:
                skipped += 1
                continue

            if not dry_run:
                graph_group_id = format_group_id(mem.tenant_id, mem.provider_id)
                proj = KnowledgeGraphProjection(
                    tenant_id=mem.tenant_id,
                    provider_id=mem.provider_id,
                    curated_memory_id=mem.id,
                    projection_type=projection_type,
                    graph_group_id=graph_group_id,
                    status="pending",
                    projection_version="2.0",
                    created_at=now,
                    updated_at=now,
                )
                db.add(proj)
                projected += 1
            else:
                projected += 1

        if not dry_run and projected > 0:
            db.commit()

        return {
            "scanned": scanned,
            "eligible": eligible,
            "projected": projected,
            "skipped": skipped,
            "rejected": rejected,
            "rejection_reasons": rejection_reasons,
            "dry_run": dry_run,
        }

    def backfill_legacy_sms_knowledge(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Backfill approved legacy SmsKnowledgeEntry records into CuratedMemory and projections.

        Spec reference: Section 59.
        Scans approved SmsKnowledgeEntry records.
        Validates scope, PII, and dynamic operational data risk.
        Maps category/entry to CuratedMemory with provenance=f"legacy_sms_knowledge:{entry.id}".
        Enqueues KnowledgeGraphProjection idempotently.
        """
        query = db.query(SmsKnowledgeEntry).filter(SmsKnowledgeEntry.status == "approved")
        if tenant_id is not None:
            query = query.filter(SmsKnowledgeEntry.tenant_id == tenant_id)
        if provider_id is not None:
            query = query.filter(SmsKnowledgeEntry.provider_id == provider_id)

        entries: List[SmsKnowledgeEntry] = query.order_by(SmsKnowledgeEntry.id.asc()).all()

        scanned = 0
        eligible = 0
        curated_created = 0
        projected = 0
        skipped = 0
        rejected = 0
        rejection_reasons: Dict[str, int] = {}

        now = utc_now()

        for entry in entries:
            scanned += 1

            # 1. Scope validation (Spec 34, 59)
            if not validate_scope(entry.tenant_id, entry.provider_id, entry.tenant_id):
                rejected += 1
                rejection_reasons["invalid_scope"] = rejection_reasons.get("invalid_scope", 0) + 1
                continue

            entry_text = entry.text or ""

            # 2. Dynamic operational data validation (Spec 19, 59)
            if is_dynamic_operational_data(entry_text):
                rejected += 1
                rejection_reasons["dynamic_operational_data"] = (
                    rejection_reasons.get("dynamic_operational_data", 0) + 1
                )
                continue

            # 3. System safety violation guard
            if is_system_safety_violation(entry_text):
                rejected += 1
                rejection_reasons["safety_violation"] = (
                    rejection_reasons.get("safety_violation", 0) + 1
                )
                continue

            clean_text = scrub_pii(entry_text)
            cat = (entry.category or "faq").strip().lower()

            if cat in ("tone", "style", "behavior", "behaviour"):
                knowledge_kind = "response_guidance"
                projection_type = "behavioural_guidance"
                user_query = f"{cat.capitalize()} guidance"
            else:
                knowledge_kind = "durable_fact"
                projection_type = "upsert_fact"
                user_query = f"Information regarding {cat}"

            provenance = f"legacy_sms_knowledge:{entry.id}"

            # Check if CuratedMemory already exists for this legacy entry
            existing_mem = (
                db.query(CuratedMemory)
                .filter(
                    CuratedMemory.tenant_id == entry.tenant_id,
                    CuratedMemory.source_reference == provenance,
                )
                .first()
            )

            eligible += 1

            if dry_run:
                if existing_mem:
                    # Check if projection already exists
                    existing_proj = (
                        db.query(KnowledgeGraphProjection)
                        .filter(
                            KnowledgeGraphProjection.tenant_id == entry.tenant_id,
                            KnowledgeGraphProjection.curated_memory_id == existing_mem.id,
                            KnowledgeGraphProjection.projection_type == projection_type,
                        )
                        .first()
                    )
                    if existing_proj:
                        skipped += 1
                    else:
                        projected += 1
                else:
                    curated_created += 1
                    projected += 1
                continue

            # Non-dry-run execution
            mem_target = existing_mem
            if not mem_target:
                content_hash = hashlib.sha256(
                    f"{entry.tenant_id}:{entry.provider_id}:{user_query}:{clean_text}".encode()
                ).hexdigest()

                effective_dt = entry.approved_at or entry.created_at or now

                mem_target = CuratedMemory(
                    tenant_id=entry.tenant_id,
                    provider_id=entry.provider_id,
                    category=cat[:64],
                    user_query=user_query,
                    ideal_response=clean_text,
                    knowledge_kind=knowledge_kind,
                    authority="provider_approval",
                    status="active",
                    conflict_state="clear",
                    content_hash=content_hash,
                    source_reference=provenance,
                    effective_from=effective_dt,
                    last_verified_at=entry.approved_at or now,
                    created_at=entry.created_at or now,
                    updated_at=now,
                )
                db.add(mem_target)
                db.flush()
                curated_created += 1

            # Check if projection already exists for this memory
            existing_proj = (
                db.query(KnowledgeGraphProjection)
                .filter(
                    KnowledgeGraphProjection.tenant_id == entry.tenant_id,
                    KnowledgeGraphProjection.curated_memory_id == mem_target.id,
                    KnowledgeGraphProjection.projection_type == projection_type,
                )
                .first()
            )

            if existing_proj:
                skipped += 1
            else:
                graph_group_id = format_group_id(entry.tenant_id, entry.provider_id)
                proj = KnowledgeGraphProjection(
                    tenant_id=entry.tenant_id,
                    provider_id=entry.provider_id,
                    curated_memory_id=mem_target.id,
                    projection_type=projection_type,
                    graph_group_id=graph_group_id,
                    status="pending",
                    projection_version="2.0",
                    created_at=now,
                    updated_at=now,
                )
                db.add(proj)
                projected += 1

        if not dry_run and (curated_created > 0 or projected > 0):
            db.commit()

        return {
            "scanned": scanned,
            "eligible": eligible,
            "curated_created": curated_created,
            "projected": projected,
            "skipped": skipped,
            "rejected": rejected,
            "rejection_reasons": rejection_reasons,
            "dry_run": dry_run,
        }

    def verify_parity(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Perform parity verification between PostgreSQL records and graph projections (Spec 57).

        Checks that all eligible active and superseded CuratedMemory records have an
        associated KnowledgeGraphProjection in the ledger.
        """
        mem_q = db.query(CuratedMemory).filter(CuratedMemory.status.in_(["active", "superseded"]))
        if tenant_id is not None:
            mem_q = mem_q.filter(CuratedMemory.tenant_id == tenant_id)
        if provider_id is not None:
            mem_q = mem_q.filter(CuratedMemory.provider_id == provider_id)

        all_memories = mem_q.all()
        total_memories = len(all_memories)

        proj_q = db.query(KnowledgeGraphProjection).filter(
            KnowledgeGraphProjection.curated_memory_id.isnot(None)
        )
        if tenant_id is not None:
            proj_q = proj_q.filter(KnowledgeGraphProjection.tenant_id == tenant_id)
        if provider_id is not None:
            proj_q = proj_q.filter(KnowledgeGraphProjection.provider_id == provider_id)

        projections = proj_q.all()
        total_projections = len(projections)

        projected_mem_ids: Set[int] = {
            p.curated_memory_id for p in projections if p.curated_memory_id is not None
        }

        # Check which valid memories lack projections
        missing_ids: List[int] = []
        for m in all_memories:
            # Only consider memories that pass dynamic & authority safety checks as expected to have projections
            user_q = m.user_query or ""
            ideal_resp = m.ideal_response or ""
            if is_dynamic_operational_data(user_q) or is_dynamic_operational_data(ideal_resp):
                continue
            if is_system_safety_violation(user_q) or is_system_safety_violation(ideal_resp):
                continue
            auth = (m.authority or "").strip().lower()
            if not auth or auth in ("conversation_candidate", "untrusted", "unverified"):
                continue

            if m.id not in projected_mem_ids:
                missing_ids.append(m.id)

        parity_ok = len(missing_ids) == 0

        return {
            "parity_ok": parity_ok,
            "total_memories": total_memories,
            "total_projections": total_projections,
            "missing_projections_count": len(missing_ids),
            "missing_memory_ids": missing_ids[:50],
        }

    def rebuild_graph(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        dry_run: bool = False,
        verify: bool = False,
    ) -> Dict[str, Any]:
        """Orchestrate full knowledge backfill and graph rebuilding (Specs 56, 57).

        1. Backfills CuratedMemory records.
        2. Backfills legacy approved SmsKnowledgeEntry records.
        3. Invalidates knowledge cache for target scope.
        4. Runs optional parity verification check.
        """
        logger.info(
            "Starting knowledge graph rebuild: tenant_id=%s, provider_id=%s, dry_run=%s, verify=%s",
            tenant_id,
            provider_id,
            dry_run,
            verify,
        )

        curated_summary = self.backfill_curated_memories(
            db=db, tenant_id=tenant_id, provider_id=provider_id, dry_run=dry_run
        )
        sms_summary = self.backfill_legacy_sms_knowledge(
            db=db, tenant_id=tenant_id, provider_id=provider_id, dry_run=dry_run
        )

        total_scanned = curated_summary["scanned"] + sms_summary["scanned"]
        total_eligible = curated_summary["eligible"] + sms_summary["eligible"]
        total_projected = curated_summary["projected"] + sms_summary["projected"]
        total_skipped = curated_summary["skipped"] + sms_summary["skipped"]
        total_rejected = curated_summary["rejected"] + sms_summary["rejected"]

        # Cache invalidation for target scope if live execution
        if not dry_run and tenant_id is not None:
            knowledge_gateway.invalidate(tenant_id, provider_id)

        parity_result = None
        if verify:
            parity_result = self.verify_parity(db=db, tenant_id=tenant_id, provider_id=provider_id)

        return {
            "status": "completed" if not dry_run else "dry_run_completed",
            "dry_run": dry_run,
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "total_scanned": total_scanned,
            "total_eligible": total_eligible,
            "total_projected": total_projected,
            "total_skipped": total_skipped,
            "total_rejected": total_rejected,
            "curated_memories": curated_summary,
            "legacy_sms_knowledge": sms_summary,
            "parity": parity_result,
        }


# Singleton instance
knowledge_rebuild_service = KnowledgeRebuildService()
