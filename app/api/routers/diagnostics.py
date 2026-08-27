"""System diagnostics API routes.

These endpoints expose internal diagnostic information to admins.
Diagnostics include database status, migration version, enabled
modules, and counts of key entities.  They can be used to monitor
the health of the system and aid in troubleshooting.
"""

from typing import Any, Dict
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
    holds: bool
    waitlist: bool
    multi_tenant: bool


class DiagnosticsResponse(BaseModel):
    counts: DiagnosticsCounts
    modules: DiagnosticsModules


router = APIRouter(prefix="/api/admin/system", tags=["system"])


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def get_system_diagnostics(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return system diagnostics.

    For security reasons the diagnostics returned here are minimal
    and intended primarily for demonstration.  A real system might
    include migration version, orphaned record detection, failed
    events and more.
    """
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
            "holds": True,
            "waitlist": True,
            "multi_tenant": True,  # toggle once multi‑tenant support is added
        },
    }
    return diagnostics


class FrontendTelemetryEvent(BaseModel):
    """A privacy-safe frontend error or timing event."""
    event_type: str               # e.g. "js_error", "unhandled_rejection", "route_change", "web_vital"
    error_class: str = ""         # e.g. "TypeError", "ReferenceError"
    route: str = ""               # URL pathname only – no query strings
    component: str = ""           # React component name
    duration_ms: float = 0.0      # Web Vital duration in milliseconds
    vital_name: str = ""          # e.g. "FCP", "LCP", "CLS"
    session_id: str = ""          # anonymous session identifier


@router.post("/diagnostics/telemetry", status_code=200)
def ingest_frontend_telemetry(
    event: FrontendTelemetryEvent,
    current_admin = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Accept privacy-safe frontend telemetry events and forward them as OTel spans.

    Only structural/timing data is accepted (error class, route template, component
    name). No personal data, SMS content, or identifying info is ever included.
    """
    import logging as _logging
    from opentelemetry import trace as _trace

    fe_logger = _logging.getLogger("frontend.telemetry")
    tracer = _trace.get_tracer("frontend-bookings")

    with tracer.start_as_current_span(f"frontend.{event.event_type}") as span:
        span.set_attribute("frontend.event_type", event.event_type)
        if event.error_class:
            span.set_attribute("frontend.error_class", event.error_class)
        if event.route:
            span.set_attribute("frontend.route", event.route)
        if event.component:
            span.set_attribute("frontend.component", event.component)
        if event.duration_ms:
            span.set_attribute("frontend.duration_ms", event.duration_ms)
        if event.vital_name:
            span.set_attribute("frontend.vital_name", event.vital_name)
        if event.session_id:
            span.set_attribute("frontend.session_id", event.session_id)

        fe_logger.info(
            "Frontend telemetry event ingested",
            extra={
                "event_type": event.event_type,
                "error_class": event.error_class or None,
                "route": event.route or None,
                "component": event.component or None,
            },
        )

    return {"status": "accepted"}


@router.get("/diagnostics/telemetry/status")
def get_telemetry_status(
    current_admin = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return observability pipeline health status (non-sensitive)."""
    import os
    from opentelemetry import trace as _trace

    provider = _trace.get_tracer_provider()
    provider_class = type(provider).__name__

    return {
        "otel_sdk_disabled": os.environ.get("OTEL_SDK_DISABLED", "false"),
        "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "not_configured"),
        "tracer_provider": provider_class,
        "telemetry_active": "NoOpTracerProvider" not in provider_class,
    }