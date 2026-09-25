"""API router for Autonomous Knowledge Curator operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.tenant import Tenant
from app.models.user import User
from app.services.knowledge.curator import unified_curator, utc_now
from app.services.knowledge.gateway import knowledge_gateway

logger = logging.getLogger(__name__)

router = APIRouter()


class ProcessCuratorRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class ProcessCuratorResponse(BaseModel):
    ok: bool = True
    processed: int
    superseded: int
    curated: int
    quarantined: int


class MemoryItem(BaseModel):
    id: int
    tenant_id: int
    provider_id: Optional[int] = None
    category: str
    user_query: str
    ideal_response: str
    knowledge_kind: str
    authority: str
    status: str
    conflict_state: str
    supersedes_id: Optional[int] = None
    source_reference: Optional[str] = None
    confidence_score: float
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryListResponse(BaseModel):
    ok: bool = True
    items: List[MemoryItem]
    total: int


class SingleMemoryResponse(BaseModel):
    ok: bool = True
    data: MemoryItem


@router.post("/process", response_model=ProcessCuratorResponse)
async def process_curation(
    payload: Optional[ProcessCuratorRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Trigger autonomous curation on pending learning events for the tenant."""
    limit = payload.limit if payload else 50
    summary = unified_curator.process_pending_learning_events(
        db=db, tenant_id=tenant.id, limit=limit
    )
    return ProcessCuratorResponse(
        ok=True,
        processed=summary.get("processed", 0),
        superseded=summary.get("superseded", 0),
        curated=summary.get("curated", 0),
        quarantined=summary.get("quarantined", 0),
    )


@router.get("/status")
async def get_curation_status(
    provider_id: Optional[int] = Query(None),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve autonomous curation statistics and breakdown by scope."""
    stats = unified_curator.get_curation_status(
        db=db, tenant_id=tenant.id, provider_id=provider_id
    )
    return {"ok": True, "data": stats}


@router.get("/memories", response_model=MemoryListResponse)
async def list_curated_memories(
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    provider_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search text in queries or responses"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List CuratedMemory entries scoped to the authenticated tenant."""
    q = db.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant.id)
    if status:
        q = q.filter(CuratedMemory.status == status)
    if kind:
        q = q.filter(CuratedMemory.knowledge_kind == kind)
    if provider_id is not None:
        q = q.filter(CuratedMemory.provider_id == provider_id)
    if category:
        q = q.filter(CuratedMemory.category == category)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                CuratedMemory.user_query.ilike(term),
                CuratedMemory.ideal_response.ilike(term),
                CuratedMemory.category.ilike(term),
            )
        )

    total = q.count()
    items = q.order_by(CuratedMemory.updated_at.desc()).offset(offset).limit(limit).all()
    return MemoryListResponse(ok=True, items=items, total=total)


@router.post("/memories/{id}/supersede", response_model=SingleMemoryResponse)
async def supersede_memory(
    id: int = Path(..., description="ID of the memory to supersede"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Manually supersede a CuratedMemory item."""
    memory = (
        db.query(CuratedMemory)
        .filter(CuratedMemory.id == id, CuratedMemory.tenant_id == tenant.id)
        .first()
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated memory not found.",
        )

    now = utc_now()
    memory.status = "superseded"
    memory.updated_at = now

    # Invalidate cache & enqueue projection
    knowledge_gateway.invalidate(tenant.id, memory.provider_id)
    graph_group_id = (
        f"tenant:{tenant.id}:provider:{memory.provider_id}"
        if memory.provider_id is not None
        else f"tenant:{tenant.id}:shared"
    )
    proj = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=memory.provider_id,
        curated_memory_id=memory.id,
        projection_type="supersede_fact",
        graph_group_id=graph_group_id,
        status="pending",
        projection_version="2.0",
        created_at=now,
        updated_at=now,
    )
    db.add(proj)

    db.commit()
    db.refresh(memory)
    return SingleMemoryResponse(ok=True, data=memory)


@router.post("/memories/{id}/restore", response_model=SingleMemoryResponse)
async def restore_memory(
    id: int = Path(..., description="ID of the memory to restore"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Restore a superseded CuratedMemory item back to active status."""
    memory = (
        db.query(CuratedMemory)
        .filter(CuratedMemory.id == id, CuratedMemory.tenant_id == tenant.id)
        .first()
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated memory not found.",
        )

    now = utc_now()
    memory.status = "active"
    memory.updated_at = now

    # Invalidate cache & enqueue projection
    knowledge_gateway.invalidate(tenant.id, memory.provider_id)
    graph_group_id = (
        f"tenant:{tenant.id}:provider:{memory.provider_id}"
        if memory.provider_id is not None
        else f"tenant:{tenant.id}:shared"
    )
    proj = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=memory.provider_id,
        curated_memory_id=memory.id,
        projection_type="upsert_fact",
        graph_group_id=graph_group_id,
        status="pending",
        projection_version="2.0",
        created_at=now,
        updated_at=now,
    )
    db.add(proj)

    db.commit()
    db.refresh(memory)
    return SingleMemoryResponse(ok=True, data=memory)


@router.get("/memories/{id}", response_model=SingleMemoryResponse)
async def get_curated_memory(
    id: int = Path(..., description="ID of the memory to fetch"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Fetch single CuratedMemory item."""
    memory = (
        db.query(CuratedMemory)
        .filter(CuratedMemory.id == id, CuratedMemory.tenant_id == tenant.id)
        .first()
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated memory not found.",
        )
    return SingleMemoryResponse(ok=True, data=memory)


@router.get("/memories/{id}/provenance")
async def get_memory_provenance(
    id: int = Path(..., description="ID of the memory to inspect"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Inspect full provenance, supersession, and projection status for a memory (Spec 80)."""
    memory = (
        db.query(CuratedMemory)
        .filter(CuratedMemory.id == id, CuratedMemory.tenant_id == tenant.id)
        .first()
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated memory not found.",
        )

    projections = (
        db.query(KnowledgeGraphProjection)
        .filter(
            KnowledgeGraphProjection.tenant_id == tenant.id,
            KnowledgeGraphProjection.curated_memory_id == memory.id,
        )
        .all()
    )

    superseded_by = (
        db.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant.id,
            CuratedMemory.supersedes_id == memory.id,
        )
        .all()
    )

    return {
        "ok": True,
        "memory_id": memory.id,
        "tenant_id": memory.tenant_id,
        "provider_id": memory.provider_id,
        "category": memory.category,
        "knowledge_kind": memory.knowledge_kind,
        "authority": memory.authority,
        "status": memory.status,
        "source_reference": memory.source_reference,
        "supersedes_id": memory.supersedes_id,
        "superseded_by_ids": [m.id for m in superseded_by],
        "content_hash": memory.content_hash,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "last_verified_at": memory.last_verified_at,
        "projections": [
            {
                "id": p.id,
                "projection_type": p.projection_type,
                "status": p.status,
                "graph_group_id": p.graph_group_id,
                "attempt_count": p.attempt_count,
                "last_error": p.last_error,
                "created_at": p.created_at,
                "projected_at": p.projected_at,
            }
            for p in projections
        ],
    }


@router.get("/quarantined")
@router.get("/proposals/quarantined")
async def list_quarantined_proposals(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve proposals quarantined due to safety or dynamic policy violations (Spec 80)."""
    proposals = (
        db.query(KnowledgeProposal)
        .filter(
            KnowledgeProposal.tenant_id == tenant.id,
            or_(
                KnowledgeProposal.proposal_type == "quarantine",
                KnowledgeProposal.reason_code == "safety_violation",
                KnowledgeProposal.resolution_code == "quarantined_safety_violation",
                KnowledgeProposal.status == "rejected",
            ),
        )
        .order_by(KnowledgeProposal.created_at.desc())
        .all()
    )
    return {
        "ok": True,
        "count": len(proposals),
        "items": [
            {
                "id": p.id,
                "proposal_type": p.proposal_type,
                "category": p.category,
                "user_query": p.user_query,
                "proposed_response": p.proposed_response,
                "reason_code": p.reason_code,
                "resolution_code": p.resolution_code,
                "status": p.status,
                "evidence_count": p.evidence_count,
                "created_at": p.created_at,
            }
            for p in proposals
        ],
    }


@router.get("/projections/status")
@router.get("/projections")
async def get_projections_status(
    limit: int = Query(50, ge=1, le=200),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve status counts and recent entries in the graph projection ledger (Spec 80)."""
    base_q = db.query(KnowledgeGraphProjection).filter(
        KnowledgeGraphProjection.tenant_id == tenant.id
    )
    all_projs = base_q.all()

    counts = {
        "total": len(all_projs),
        "pending": sum(1 for p in all_projs if p.status == "pending"),
        "processing": sum(1 for p in all_projs if p.status == "processing"),
        "completed": sum(1 for p in all_projs if p.status == "completed"),
        "failed": sum(1 for p in all_projs if p.status == "failed"),
        "dead_letter": sum(1 for p in all_projs if p.status == "dead_letter"),
    }

    recent = (
        base_q.order_by(KnowledgeGraphProjection.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "ok": True,
        "counts": counts,
        "items": [
            {
                "id": p.id,
                "curated_memory_id": p.curated_memory_id,
                "projection_type": p.projection_type,
                "status": p.status,
                "attempt_count": p.attempt_count,
                "graph_group_id": p.graph_group_id,
                "last_error": p.last_error,
                "created_at": p.created_at,
                "projected_at": p.projected_at,
            }
            for p in recent
        ],
    }


@router.post("/projections/retry-failed")
async def retry_failed_projections(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Reset failed/dead_letter projections back to pending for worker retry (Spec 80)."""
    now = utc_now()
    failed_projs = (
        db.query(KnowledgeGraphProjection)
        .filter(
            KnowledgeGraphProjection.tenant_id == tenant.id,
            KnowledgeGraphProjection.status.in_(["failed", "dead_letter"]),
        )
        .all()
    )

    count = len(failed_projs)
    for p in failed_projs:
        p.status = "pending"
        p.attempt_count = 0
        p.next_attempt_at = now
        p.lease_owner = None
        p.lease_expires_at = None
        p.last_error = None
        p.updated_at = now

    db.commit()
    return {"ok": True, "retried_count": count}
