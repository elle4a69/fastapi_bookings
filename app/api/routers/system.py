"""System administration and cleanup API router."""

import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..deps import get_db, get_current_tenant, get_current_admin
from ...models.tenant import Tenant
from ...models.user import User
from ...services import retention_service

router = APIRouter(prefix="/api/admin/system", tags=["system-admin"])


@router.get("/health")
def get_system_health(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Return a real-time health snapshot of the API and database."""
    start = time.perf_counter()
    db.execute(text("SELECT 1"))
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "ok": True,
        "data": {
            "api_status": "operational",
            "sqlite_latency_ms": latency_ms,
            "background_queues_active": 0,
        },
    }


@router.post("/cleanup")
def run_historic_cleanup(
    days: int = 365,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Execute cleanup of historic notifications, logs, and cancelled bookings older than specified days."""
    if days < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Days threshold must be positive.")
    
    results = retention_service.cleanup_historic_records(db, tenant_id=tenant.id, days_threshold=days)
    return {"ok": True, "data": results, "message": "Cleanup executed successfully."}


@router.post("/clients/{client_id}/anonymize")
def anonymize_client_record(
    client_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """GDPR-compliant anonymization of a client record by ID."""
    success = retention_service.anonymize_client(db, client_id=client_id, tenant_id=tenant.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    
    return {"ok": True, "message": "Client anonymized successfully."}
