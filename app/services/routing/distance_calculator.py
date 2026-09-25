"""Distance and routing calculation service using OSRM with Haversine fallback.

Calculates road distance and driving duration between coordinates, with
automatic fallback to great-circle Haversine calculations when external
routing services are unreachable. Also provides out-call travel surcharge
and radius validation.
"""

import logging
import math
from typing import Any, Optional

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM: float = 6371.0


class DistanceCalculator:
    """Async service for calculating driving distance, duration, and outcall fees."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 5.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Initialize DistanceCalculator.

        Args:
            base_url: OSRM base URL. Defaults to settings.OSRM_BASE_URL or public demo.
            timeout: HTTP timeout in seconds. Defaults to 5.0.
            client: Optional externally provided httpx.AsyncClient instance.
        """
        raw_base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "OSRM_BASE_URL", "https://router.project-osrm.org")
        )
        self.base_url: str = raw_base_url.rstrip("/")
        self.timeout: float = timeout
        self._external_client: Optional[httpx.AsyncClient] = client
        self._owned_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create active httpx.AsyncClient."""
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self.timeout)
        return self._owned_client

    async def close(self) -> None:
        """Close internal client if owned by this instance."""
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()
            self._owned_client = None

    async def __aenter__(self) -> "DistanceCalculator":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    @staticmethod
    def haversine_distance(
        origin_lat: float | tuple[float, float] | list[float],
        origin_lng: float | tuple[float, float] | list[float] | None = None,
        dest_lat: float | None = None,
        dest_lng: float | None = None,
        road_winding_factor: float = 1.25,
        assumed_speed_kmh: float = 50.0,
    ) -> dict[str, float]:
        """Compute estimated distance and duration via the Haversine formula.

        Args:
            origin_lat: Origin latitude in degrees, or (lat, lng) tuple.
            origin_lng: Origin longitude in degrees, or (lat, lng) destination tuple.
            dest_lat: Destination latitude in degrees (if origin_lat is float).
            dest_lng: Destination longitude in degrees (if origin_lat is float).
            road_winding_factor: Multiplier to estimate road travel vs straight line.
            assumed_speed_kmh: Average driving speed in km/h for duration estimation.

        Returns:
            Dict containing distance_km and duration_minutes.
        """
        if isinstance(origin_lat, (tuple, list)):
            coord1 = origin_lat
            coord2 = origin_lng
            o_lat, o_lng = float(coord1[0]), float(coord1[1])
            d_lat_val, d_lng_val = float(coord2[0]), float(coord2[1])
        else:
            o_lat = float(origin_lat)
            o_lng = float(origin_lng)
            d_lat_val = float(dest_lat)
            d_lng_val = float(dest_lng)

        d_lat = math.radians(d_lat_val - o_lat)
        d_lng = math.radians(d_lng_val - o_lng)
        lat1 = math.radians(o_lat)
        lat2 = math.radians(d_lat_val)

        a = (
            math.sin(d_lat / 2.0) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        straight_km = EARTH_RADIUS_KM * c

        # Apply winding road factor for realistic driving estimate
        driving_distance_km = round(straight_km * road_winding_factor, 2)

        # Estimate duration in minutes based on assumed speed
        duration_hours = driving_distance_km / assumed_speed_kmh if assumed_speed_kmh > 0 else 0.0
        duration_minutes = round(duration_hours * 60.0, 1)

        return {
            "distance_km": float(driving_distance_km),
            "duration_minutes": float(duration_minutes),
        }

    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict[str, float]:
        """Calculate driving distance and duration between two coordinates.

        Attempts to call the configured OSRM service. If OSRM is unreachable,
        fails, or times out, falls back seamlessly to the Haversine formula.

        Args:
            origin_lat: Starting latitude.
            origin_lng: Starting longitude.
            dest_lat: Destination latitude.
            dest_lng: Destination longitude.

        Returns:
            Dict with 'distance_km' (float) and 'duration_minutes' (float).
        """
        # OSRM expects coordinates in {longitude},{latitude} order
        endpoint = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=false"
        )

        client = await self._get_client()
        try:
            logger.info(
                "Querying OSRM route from (%s, %s) to (%s, %s)",
                origin_lat,
                origin_lng,
                dest_lat,
                dest_lng,
            )
            response = await client.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok" and data.get("routes"):
                best_route = data["routes"][0]
                distance_meters = float(best_route["distance"])
                duration_seconds = float(best_route["duration"])

                distance_km = round(distance_meters / 1000.0, 2)
                duration_minutes = round(duration_seconds / 60.0, 1)

                logger.info(
                    "OSRM route resolved: %s km, %s mins",
                    distance_km,
                    duration_minutes,
                )
                return {
                    "distance_km": float(distance_km),
                    "duration_minutes": float(duration_minutes),
                }

            logger.warning(
                "OSRM returned non-Ok code '%s', falling back to Haversine",
                data.get("code"),
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "OSRM routing timed out after %ss (%s), falling back to Haversine",
                self.timeout,
                exc,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "OSRM routing HTTP error (%s), falling back to Haversine",
                exc,
            )
        except Exception as exc:
            logger.warning(
                "Unexpected error querying OSRM (%s), falling back to Haversine",
                exc,
                exc_info=True,
            )

        # Graceful fallback to Haversine formula
        fallback_result = self.haversine_distance(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
        )
        logger.info(
            "Haversine fallback calculated: %s km, %s mins",
            fallback_result["distance_km"],
            fallback_result["duration_minutes"],
        )
        return fallback_result

    @staticmethod
    def calculate_outcall_fee(
        distance_km: float,
        base_surcharge: float,
        per_km_fee: float,
        max_radius_km: float,
    ) -> dict[str, Any]:
        """Calculate out-call travel surcharge and check serviceability.

        Args:
            distance_km: Distance to client in kilometers.
            base_surcharge: Flat surcharge for out-call travel.
            per_km_fee: Variable fee charged per kilometer.
            max_radius_km: Maximum serviceable travel radius.

        Returns:
            Dict indicating whether out-call is allowed and fee amount.
            If distance exceeds max_radius_km:
                {"allowed": False, "reason": "Location exceeds maximum out-call radius", "fee": 0.0}
            Else:
                {"allowed": True, "fee": round(base_surcharge + (distance_km * per_km_fee), 2)}
        """
        if distance_km > max_radius_km:
            return {
                "allowed": False,
                "reason": "Location exceeds maximum out-call radius",
                "fee": 0.0,
            }

        calculated_fee = round(base_surcharge + (distance_km * per_km_fee), 2)
        return {
            "allowed": True,
            "fee": float(calculated_fee),
        }
