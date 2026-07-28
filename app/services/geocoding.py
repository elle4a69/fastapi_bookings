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

logger = logging.getLogger(__name__)


async def geocode_tenant_address(tenant_id: int, address: str) -> None:
    """Geocode a physical address via Mapbox and persist coordinates to the Tenant.

    Intended to be run as a FastAPI BackgroundTask so the admin HTTP response
    is not blocked by the external network call.

    Args:
        tenant_id: Primary key of the tenant to update.
        address:   Full physical address string to geocode.
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        logger.warning(
            "MAPBOX_ACCESS_TOKEN is not configured. Skipping geocoding for tenant %d.", tenant_id
        )
        return

    encoded_address = quote(address, safe="")
    url = (
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json"
        f"?access_token={settings.MAPBOX_ACCESS_TOKEN}&limit=1"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
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
            else:
                logger.error("Tenant %d not found when saving geocoded coordinates.", tenant_id)
        finally:
            db.close()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Mapbox Geocoding HTTP error for tenant %d: %s %s",
            tenant_id, exc.response.status_code, exc.response.text,
        )
    except Exception:
        logger.exception(
            "Unexpected error geocoding address for tenant %d: %s", tenant_id, address
        )
