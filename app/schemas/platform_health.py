"""Pydantic schemas for platform health and deep readiness probes (WP5).

Strictly privacy-safe: never includes database URLs, passwords, API keys,
tokens, internal IP addresses, or tenant/customer data.
"""

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class DependencyHealth(BaseModel):
    """Health status representation for a single platform backing service."""

    status: str = Field(
        ...,
        description="Health status: 'ok', 'degraded', 'down', or 'not_configured'",
    )
    latency_ms: Optional[float] = Field(
        None,
        description="Observed round-trip ping/query latency in milliseconds",
    )
    detail: Optional[str] = Field(
        None,
        description="Sanitized non-sensitive diagnostic message if degraded or down",
    )
    provider: Optional[str] = Field(
        None,
        description="Standard identifier for external provider (e.g. 'logto', 'flexprice')",
    )
    configured: Optional[bool] = Field(
        None,
        description="Indicates whether the dependency has credentials configured",
    )


class PlatformReadinessResponse(BaseModel):
    """Deep readiness check response for Kubernetes/ALB health probes."""

    status: str = Field(
        ...,
        description="Overall readiness state: 'ok', 'degraded', or 'down'",
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp of the readiness evaluation",
    )
    dependencies: Dict[str, DependencyHealth] = Field(
        ...,
        description="Health breakdown of all backing platform dependencies",
    )
    environment: str = Field(
        ...,
        description="Deployment environment name (e.g. 'production', 'staging', 'development')",
    )
