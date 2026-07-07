"""Audit log routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.audit import AuditLog as AuditModel
from ...schemas.audit import (
    AuditLog,
    AuditLogCreate,
    AuditLogListResponse,
    AuditLogResponse,
)


router = APIRouter()


@router.get("/audit-log", response_model=AuditLogListResponse, tags=["audit"])
def list_audit_logs(
    params: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of audit logs."""
    query = db.query(AuditModel).order_by(AuditModel.timestamp.desc())
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/audit-log", response_model=AuditLogResponse, tags=["audit"])
def create_audit_log(
    log_in: AuditLogCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new audit log entry."""
    log = AuditModel(**log_in.dict())
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"ok": True, "data": log}