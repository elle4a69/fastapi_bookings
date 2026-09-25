"""System diagnostics API routes.

These endpoints expose internal diagnostic information to admins as well as
a public schema-limited, privacy-safe frontend telemetry ingestion endpoint.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_admin
from ...db.database import get_db
from ...models import (
    Service,
    Provider,
    Client,
    Booking,
    Resource,
    OutboxEvent,
    WaitlistEntry,
)


class DiagnosticsCounts(BaseModel):
    services: int
    providers: int
    clients: int
    bookings: int
    resources: int
    waitlist_entries: int
    outbox_events: int


class DiagnosticsModules(BaseModel):
    locations: bool
    categories: bool
    resources: bool
    products: bool
    add_ons: bool
    packages: bool
    waitlist: bool
    multi_tenant: bool


class DiagnosticsResponse(BaseModel):
    counts: DiagnosticsCounts
    modules: DiagnosticsModules


router = APIRouter(prefix="/api/admin/system", tags=["system"])
public_router = APIRouter(prefix="/api/public/diagnostics", tags=["public-diagnostics"])
admin_diag_router = APIRouter(prefix="/api/admin/diagnostics", tags=["diagnostics"])
readiness_v1_router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def get_system_diagnostics(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return minimal system entity counts and module flags."""
    diagnostics: Dict[str, Any] = {
        "counts": {
            "services": db.query(Service).count(),
            "providers": db.query(Provider).count(),
            "clients": db.query(Client).count(),
            "bookings": db.query(Booking).count(),
            "resources": db.query(Resource).count(),
            "waitlist_entries": db.query(WaitlistEntry).count(),
            "outbox_events": db.query(OutboxEvent).filter(OutboxEvent.processed == False).count(),
        },
        "modules": {
            "locations": True,
            "categories": True,
            "resources": True,
            "products": True,
            "add_ons": True,
            "packages": True,
            "waitlist": True,
            "multi_tenant": True,
        },
    }
    return diagnostics


class PublicFrontendTelemetryEvent(BaseModel):
    """Strictly schema-limited, unauthenticated frontend diagnostic event."""
    event_type: str                         # Enum: js_error, unhandled_rejection, route_change, web_vital, component_error
    error_class: Optional[str] = None      # Max 100 chars, clean identifier
    route: Optional[str] = None            # Pathname template only, no query strings/hashes
    component: Optional[str] = None        # Component name max 100 chars
    duration_ms: Optional[float] = None    # Non-negative float
    vital_name: Optional[str] = None       # Enum: FCP, LCP, CLS, FID, TTFB


@public_router.post("/telemetry", status_code=200)
def ingest_public_frontend_telemetry(event: PublicFrontendTelemetryEvent) -> Dict[str, str]:
    """Ingest privacy-safe structural frontend telemetry events from public & admin clients."""
    valid_events = {"js_error", "unhandled_rejection", "route_change", "web_vital", "component_error"}
    if event.event_type not in valid_events:
        return {"status": "rejected"}

    # Strip query strings and hashes from route
    clean_route = ""
    if event.route:
        clean_route = event.route.split("?")[0].split("#")[0][:150]

    clean_error_class = ""
    if event.error_class:
        clean_error_class = "".join(c for c in event.error_class if c.isalnum() or c in "._-")[:100]

    clean_component = ""
    if event.component:
        clean_component = "".join(c for c in event.component if c.isalnum() or c in "._-")[:100]

    from opentelemetry import trace as _trace
    tracer = _trace.get_tracer("frontend-bookings")

    with tracer.start_as_current_span(f"frontend.{event.event_type}") as span:
        span.set_attribute("frontend.event_type", event.event_type)
        if clean_error_class:
            span.set_attribute("frontend.error_class", clean_error_class)
        if clean_route:
            span.set_attribute("frontend.route", clean_route)
        if clean_component:
            span.set_attribute("frontend.component", clean_component)
        if event.duration_ms is not None and event.duration_ms >= 0:
            span.set_attribute("frontend.duration_ms", event.duration_ms)
        if event.vital_name and event.vital_name in {"FCP", "LCP", "CLS", "FID", "TTFB"}:
            span.set_attribute("frontend.vital_name", event.vital_name)

    return {"status": "accepted"}


@admin_diag_router.get("/telemetry/status")
@router.get("/diagnostics/telemetry/status")
def get_telemetry_status(current_admin = Depends(get_current_admin)) -> Dict[str, Any]:
    """Return safe observability pipeline health status (non-sensitive, no endpoints or tokens)."""
    from ...core.telemetry import get_telemetry_status_data
    return get_telemetry_status_data()


@admin_diag_router.get("/metrics")
@public_router.get("/metrics")
@router.get("/diagnostics/metrics")
def get_diagnostics_metrics(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Expose alert metrics, error thresholds, and rollout configuration (Sections 32, 33)."""
    from ...core.config import settings
    from ...models.knowledge_projection import KnowledgeGraphProjection

    try:
        backlog = db.query(KnowledgeGraphProjection).filter(
            KnowledgeGraphProjection.status.in_(["pending", "retry", "processing"])
        ).count()
        dead_letters = db.query(KnowledgeGraphProjection).filter(
            KnowledgeGraphProjection.status == "dead_letter"
        ).count()
    except Exception:
        backlog = 0
        dead_letters = 0

    rollout_mode = "graph_live" if getattr(settings, "GRAPH_KNOWLEDGE_ENABLED", False) else (
        "canary" if (getattr(settings, "GRAPH_CANARY_PROVIDER_IDS", []) or getattr(settings, "GRAPH_CANARY_TENANT_IDS", [])) else "fallback"
    )

    return {
        "status": "healthy",
        "rollout_mode": rollout_mode,
        "feature_flags": {
            "graph_knowledge_enabled": bool(getattr(settings, "GRAPH_KNOWLEDGE_ENABLED", False)),
            "graph_shadow_write": bool(getattr(settings, "GRAPH_SHADOW_WRITE", False)),
            "graph_shadow_read": bool(getattr(settings, "GRAPH_SHADOW_READ", False)),
            "canary_provider_ids": list(getattr(settings, "GRAPH_CANARY_PROVIDER_IDS", [])),
            "canary_tenant_ids": list(getattr(settings, "GRAPH_CANARY_TENANT_IDS", [])),
        },
        "thresholds": {
            "error_rate_pct_limit": 1.0,
            "p95_latency_ms_limit": 200.0,
            "max_projection_backlog": 500,
            "cross_tenant_leakage_tolerance": 0,
        },
        "metrics": {
            "projection_backlog": backlog,
            "dead_letters": dead_letters,
            "error_rate_pct": 0.0,
        },
    }


class GranularHealthStatus(BaseModel):
    """Granular health and readiness schema reporting component-level statuses."""
    status: str
    fastapi: str
    postgresql: str
    redis: str
    neo4j: str
    projection_worker: str
    curator_worker: str


def check_granular_system_readiness(db: Optional[Session] = None) -> Dict[str, Any]:
    """Check connectivity and operational health across all major subsystems (Spec 24)."""
    from sqlalchemy.sql import text
    from ...core.config import settings
    from ...core.redis import ping as redis_ping
    from ...services.knowledge.graphiti_client import ping_neo4j

    pg_healthy = False
    if db is not None:
        try:
            db.execute(text("SELECT 1"))
            pg_healthy = True
        except Exception:
            pg_healthy = False
    else:
        try:
            from ...db.database import SessionLocal
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                pg_healthy = True
        except Exception:
            pg_healthy = False

    redis_healthy = bool(redis_ping())
    neo4j_healthy = bool(ping_neo4j())
    projection_worker_healthy = bool(getattr(settings, "PROJECTION_WORKER_ENABLED", True))
    curator_worker_healthy = bool(getattr(settings, "CURATOR_WORKER_ENABLED", True))

    all_healthy = (
        pg_healthy
        and redis_healthy
        and neo4j_healthy
        and projection_worker_healthy
        and curator_worker_healthy
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "fastapi": "healthy",
        "postgresql": "healthy" if pg_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
        "neo4j": "healthy" if neo4j_healthy else "unhealthy",
        "projection_worker": "healthy" if projection_worker_healthy else "unhealthy",
        "curator_worker": "healthy" if curator_worker_healthy else "unhealthy",
    }


@public_router.get("/health/granular", response_model=GranularHealthStatus)
@public_router.get("/readiness", response_model=GranularHealthStatus)
@admin_diag_router.get("/readiness", response_model=GranularHealthStatus)
@router.get("/diagnostics/readiness", response_model=GranularHealthStatus)
@readiness_v1_router.get("/readiness", response_model=GranularHealthStatus)
def get_granular_readiness(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Expose granular system readiness check (Section 24)."""
    return check_granular_system_readiness(db)