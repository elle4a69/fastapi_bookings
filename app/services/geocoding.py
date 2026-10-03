"""Geocoding service using Mapbox Geocoding API.

This module provides a background task that geocodes a tenant physical
address into latitude/longitude coordinates using the Mapbox Geocoding API
and persists the result back to the Tenant record.
"""

import logging
from urllib.parse import quote

import httpx

from ..core.config import settings
from ..db.database import SessionLocal
from ..models.tenant import Tenant
from .routing.geocoding import (
    AsyncRateLimiter,
    GeocodingTTLCache,
    _GEOCODING_CACHE,
    _RATE_LIMITER,
    clear_geocoding_cache,
    get_geocoding_cache,
)

logger = logging.getLogger(__name__)


def _persist_tenant_coordinates(
    tenant_id: int, address: str, latitude: float, longitude: float
) -> bool:
    """Save geocoded coordinates to the Tenant record in the database."""
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            tenant.latitude = latitude
            tenant.longitude = longitude
            db.commit()
            logger.info(
                "Geocoded tenant %d (%s) to lat=%.6f lon=%.6f",
                tenant_id, address, latitude, longitude,
            )
            return True
        else:
            logger.error("Tenant %d not found when saving geocoded coordinates.", tenant_id)
            return False
    finally:
        db.close()


async def geocode_tenant_address(tenant_id: int, address: str) -> None:
    """Geocode a physical address via Mapbox and persist coordinates to the Tenant.

    Intended to be run as a FastAPI BackgroundTask so the admin HTTP response
    is not blocked by the external network call. Utilizes in-memory TTL caching
    and rate limiting to prevent redundant requests and 429 errors.

    Args:
        tenant_id: Primary key of the tenant to update.
        address:   Full physical address string to geocode.
    """
    if not address or not address.strip():
        logger.warning("Empty address provided for tenant %d. Skipping geocoding.", tenant_id)
        return

    if not settings.MAPBOX_ACCESS_TOKEN:
        logger.warning(
            "MAPBOX_ACCESS_TOKEN is not configured. Skipping geocoding for tenant %d.", tenant_id
        )
        return

    norm_key = f"coord:{address.strip().lower()}"

    # 1. Check TTL cache to avoid duplicate outbound network calls
    cached = _GEOCODING_CACHE.get(norm_key)
    if cached is not None:
        latitude, longitude = cached
        logger.info(
            "Using cached coordinates for tenant %d (%s): lat=%.6f lon=%.6f",
            tenant_id, address, latitude, longitude,
        )
        _persist_tenant_coordinates(tenant_id, address, latitude, longitude)
        return

    # 2. Rate limiter protection before outbound call
    await _RATE_LIMITER.acquire()

    encoded_address = quote(address, safe="")
    url = (
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json"
        f"?access_token={settings.MAPBOX_ACCESS_TOKEN}&limit=1"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 429:
                logger.warning(
                    "Mapbox rate limit (429) hit during geocoding for tenant %d (%s).",
                    tenant_id, address,
                )
                return
            response.raise_for_status()
            data = response.json()

        features = data.get("features", [])
        if not features:
            logger.warning(
                "Mapbox returned no results for address: %s (tenant %d)", address, tenant_id
            )
            return

        center = features[0].get("center", [])
        if len(center) != 2:
            logger.warning(
                "Unexpected center format from Mapbox for tenant %d: %s", tenant_id, center
            )
            return

        longitude, latitude = float(center[0]), float(center[1])

        # Cache valid coordinates (keyed by normalized query string)
        _GEOCODING_CACHE.set(norm_key, (latitude, longitude))

        _persist_tenant_coordinates(tenant_id, address, latitude, longitude)

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning(
                "Mapbox rate limit (429) hit for tenant %d (%s).", tenant_id, address
            )
        else:
            logger.error(
                "Mapbox Geocoding HTTP error for tenant %d: %s %s",
                tenant_id, exc.response.status_code, exc.response.text,
            )
    except Exception:
        logger.exception(
            "Unexpected error geocoding address for tenant %d: %s", tenant_id, address
        )
