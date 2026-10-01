"""System administration and cleanup API router."""

import time
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..deps import get_db, get_current_tenant, get_current_admin, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...services import retention_service
from ...schemas.general_systems import ServiceHealthCheck, SystemHealthResponse
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/system", tags=["system-admin"])


def _check_postgres(db: Session) -> ServiceHealthCheck:
    """Execute SELECT 1 via the live DB session and return a ServiceHealthCheck."""
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealthCheck(status="ok", latency_ms=latency_ms)
    except Exception as exc:  # pragma: no cover
        logger.warning("PostgreSQL health check failed: %s", exc)
        return ServiceHealthCheck(status="down", latency_ms=None, detail=str(exc))


def _check_redis() -> ServiceHealthCheck:
    """Send a real PING to Redis via the sync connection pool and measure round-trip."""
    try:
        from ...core.redis import get_redis_client
        client = get_redis_client()
        t0 = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealthCheck(status="ok", latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return ServiceHealthCheck(status="down", latency_ms=None, detail=str(exc))


def _check_neo4j() -> ServiceHealthCheck | None:
    """Run RETURN 1 via the Neo4j driver and measure round-trip; skip when not configured."""
    if not settings.GRAPH_KNOWLEDGE_ENABLED:
        return None
    try:
        from ...services.knowledge.graphiti_client import get_neo4j_driver
        driver = get_neo4j_driver()
        if driver is None:
            return ServiceHealthCheck(
                status="down",
                latency_ms=None,
                detail="Neo4j driver could not be initialised",
            )
        t0 = time.perf_counter()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("RETURN 1").consume()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealthCheck(status="ok", latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return ServiceHealthCheck(status="down", latency_ms=None, detail=str(exc))


@router.get("/health", response_model=SystemHealthResponse)
def get_system_health(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Return a real-time health snapshot measuring live connection latency for each service.

    Each service is checked independently; a single failure marks that service
    as 'down' and demotes api_status to 'degraded'.  The endpoint itself always
    returns HTTP 200 — callers must inspect the payload to determine health.
    """
    postgres = _check_postgres(db)
    redis = _check_redis()
    neo4j = _check_neo4j()

    # No Celery / ARQ queue system is wired into this application.
    # Report truthfully rather than inventing a count.
    background_workers = ServiceHealthCheck(
        status="ok",
        latency_ms=None,
        detail="source=none; no distributed task queue is configured",
    )

    any_down = postgres.status == "down" or redis.status == "down" or (
        neo4j is not None and neo4j.status == "down"
    )
    api_status = "degraded" if any_down else "operational"

    return SystemHealthResponse(
        api_status=api_status,
        postgres=postgres,
        redis=redis,
        neo4j=neo4j,
        background_workers=background_workers,
        checked_at=datetime.now(timezone.utc),
    ).model_dump()


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
    client_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """GDPR-compliant anonymization of a client record by ID."""
    success = retention_service.anonymize_client(db, client_id=client_id, tenant_id=tenant.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    
    return {"ok": True, "message": "Client anonymized successfully."}
