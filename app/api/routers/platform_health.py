"""Platform readiness and dependency health router (WP5).

Provides deep readiness checks for Kubernetes, AWS ALB, and operator diagnostics.
Adheres strictly to zero-leakage security rules: NEVER exposes credentials, database
connection strings with embedded passwords, API tokens, internal VPC IPs, or tenant
data in any response payloads.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Optional
from fastapi import APIRouter, Depends, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.redis import ping as redis_ping
from app.schemas.platform_health import DependencyHealth, PlatformReadinessResponse
from app.services.identity.logto_client import logto_client
from app.services.platform_billing.flexprice_client import flexprice_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["platform-health"])


def check_database_health(db: Session) -> DependencyHealth:
    """Execute a lightweight SELECT 1 query to verify transactional DB connectivity."""
    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return DependencyHealth(status="ok", latency_ms=latency_ms)
    except Exception as exc:
        logger.error("Platform health database check failed: %s", exc)
        return DependencyHealth(
            status="down",
            latency_ms=None,
            detail="Database connectivity check failed",
        )


def check_redis_health() -> DependencyHealth:
    """Execute Redis PING to verify key-value cache and idempotency lock layer."""
    t0 = time.perf_counter()
    try:
        healthy = redis_ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if healthy:
            return DependencyHealth(status="ok", latency_ms=latency_ms)
        return DependencyHealth(
            status="down",
            latency_ms=None,
            detail="Redis connectivity check failed",
        )
    except Exception as exc:
        logger.warning("Platform health Redis check failed: %s", exc)
        return DependencyHealth(
            status="down",
            latency_ms=None,
            detail="Redis connectivity check failed",
        )


def check_identity_provider_health() -> DependencyHealth:
    """Verify Logto Identity Provider connectivity without exposing credentials."""
    if not logto_client.is_configured:
        return DependencyHealth(
            status="not_configured",
            configured=False,
            provider="logto",
            detail="Identity provider not configured",
        )

    t0 = time.perf_counter()
    try:
        # Check OIDC discovery endpoint or root with short timeout
        discovery_url = f"{logto_client.endpoint}/oidc/.well-known/openid-configuration"
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(discovery_url)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status_code == 200:
                return DependencyHealth(
                    status="ok",
                    configured=True,
                    provider="logto",
                    latency_ms=latency_ms,
                )
            return DependencyHealth(
                status="degraded",
                configured=True,
                provider="logto",
                latency_ms=latency_ms,
                detail=f"Identity provider returned status {resp.status_code}",
            )
    except Exception as exc:
        logger.warning("Identity provider reachability check failed: %s", exc)
        return DependencyHealth(
            status="down",
            configured=True,
            provider="logto",
            latency_ms=None,
            detail="Identity provider endpoint unreachable",
        )


def check_billing_provider_health() -> DependencyHealth:
    """Verify Flexprice Billing Provider connectivity without exposing credentials."""
    if not flexprice_client.api_key:
        return DependencyHealth(
            status="not_configured",
            configured=False,
            provider="flexprice",
            detail="Billing provider not configured",
        )

    # If mock handler is set for test suite, verify using mock handler
    if flexprice_client._mock_handler is not None:
        try:
            t0 = time.perf_counter()
            flexprice_client._mock_handler("GET", "/health", None)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return DependencyHealth(
                status="ok",
                configured=True,
                provider="flexprice",
                latency_ms=latency_ms,
            )
        except Exception:
            return DependencyHealth(
                status="down",
                configured=True,
                provider="flexprice",
                latency_ms=None,
                detail="Billing provider endpoint unreachable",
            )

    t0 = time.perf_counter()
    try:
        health_url = f"{flexprice_client.base_url}/health"
        with httpx.Client(
            timeout=3.0,
            headers={"Authorization": f"Bearer {flexprice_client.api_key}"},
        ) as client:
            resp = client.get(health_url)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status_code in (200, 204):
                return DependencyHealth(
                    status="ok",
                    configured=True,
                    provider="flexprice",
                    latency_ms=latency_ms,
                )
            return DependencyHealth(
                status="degraded",
                configured=True,
                provider="flexprice",
                latency_ms=latency_ms,
                detail=f"Billing provider returned status {resp.status_code}",
            )
    except Exception as exc:
        logger.warning("Billing provider reachability check failed: %s", exc)
        return DependencyHealth(
            status="down",
            configured=True,
            provider="flexprice",
            latency_ms=None,
            detail="Billing provider endpoint unreachable",
        )


@router.get(
    "/api/platform/health/readiness",
    response_model=PlatformReadinessResponse,
    summary="Platform deep readiness probe",
)
@router.get(
    "/health/ready",
    response_model=PlatformReadinessResponse,
    summary="Standard cluster readiness probe alias",
)
def get_platform_readiness(db: Session = Depends(get_db)) -> Response:
    """Evaluate deep readiness across database, cache, identity, and billing dependencies.

    Fails closed with HTTP 503 Service Unavailable if any critical dependency (e.g. database)
    is unreachable or failing. Strictly redacts any sensitive URLs, credentials, or keys.
    """
    db_health = check_database_health(db)
    redis_health = check_redis_health()
    logto_health = check_identity_provider_health()
    flexprice_health = check_billing_provider_health()

    dependencies = {
        "database": db_health,
        "redis": redis_health,
        "identity_provider": logto_health,
        "billing_provider": flexprice_health,
    }

    # Determine overall status:
    # Critical dependency: database (must be 'ok')
    # If DB is down, overall status is 'down' (HTTP 503)
    # If any other dependency is degraded/down, overall status is 'degraded' (HTTP 200 with warnings)
    if db_health.status == "down":
        overall_status = "down"
    elif any(d.status in ("down", "degraded") for d in (redis_health, logto_health, flexprice_health)):
        overall_status = "degraded"
    else:
        overall_status = "ok"

    payload = PlatformReadinessResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        dependencies=dependencies,
        environment=settings.APP_ENV,
    )

    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if overall_status == "down"
        else status.HTTP_200_OK
    )

    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))
