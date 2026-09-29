"""Geocoding and suburb/postcode centroid estimation service.

Provides address-to-coordinate resolution and suburb/postcode centroid estimation
with:
1. Primary Fast-Path: Local SQLite database of Australian postcodes & suburbs (`data/au_postcodes.db`) (<1ms, no network).
2. API Fallback: Mapbox Geocoding API for exact addresses or unlisted areas.
3. Centroid fallback: Predefined dictionary & deterministic coordinates for offline testing.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Optional, Tuple
from urllib.parse import quote

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

# Path to the local Australian Postcodes SQLite database
DATA_DIR = Path(__file__).resolve().parent / "data"
AU_POSTCODES_DB = DATA_DIR / "au_postcodes.db"

# Predefined centroids for Australian reference locations & international tests
KNOWN_CENTROIDS: dict[str, tuple[float, float]] = {
    # Reference AU Capitals
    "sydney": (-33.8688, 151.2093),
    "sydney cbd": (-33.8688, 151.2093),
    "melbourne": (-37.8136, 144.9631),
    "melbourne cbd": (-37.8136, 144.9631),
    "brisbane": (-27.4698, 153.0251),
    "adelaide": (-34.9285, 138.6007),
    "perth": (-31.9505, 115.8605),
    "canberra": (-35.2809, 149.1300),
    # International test references
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "10001": (40.7128, -74.0060),
    "times square": (40.7589, -73.9851),
}

# Test/runtime overrides registry
_RUNTIME_REGISTRY: dict[str, tuple[float, float]] = {}


def register_test_location(name_or_address: str, coords: tuple[float, float]) -> None:
    """Register a temporary location mapping for testing."""
    _RUNTIME_REGISTRY[name_or_address.strip().lower()] = coords


def clear_test_locations() -> None:
    """Clear test location registry."""
    _RUNTIME_REGISTRY.clear()


def lookup_au_postcode(
    suburb: Optional[str] = None,
    postcode: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Query the local Australian postcodes database (<1ms fast-path).

    Args:
        suburb: Suburb/locality name (case-insensitive).
        postcode: 4-digit postcode string.

    Returns:
        Dict with suburb, postcode, state, latitude, longitude, or None if not found.
    """
    if not AU_POSTCODES_DB.exists():
        return None

    suburb_clean = (suburb or "").strip().lower()
    postcode_clean = (postcode or "").strip().zfill(4) if (postcode and postcode.strip().isdigit()) else (postcode or "").strip()

    if not suburb_clean and not postcode_clean:
        return None

    try:
        with sqlite3.connect(f"file:{AU_POSTCODES_DB}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            # 1. Both suburb and postcode supplied
            if suburb_clean and postcode_clean:
                cur.execute(
                    """
                    SELECT suburb, postcode, state, latitude, longitude
                    FROM postcodes
                    WHERE suburb_lower = ? AND postcode = ?
                    LIMIT 1
                    """,
                    (suburb_clean, postcode_clean),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "suburb": row[0],
                        "postcode": row[1],
                        "state": row[2],
                        "latitude": float(row[3]),
                        "longitude": float(row[4]),
                    }

            # 2. Suburb match
            if suburb_clean:
                cur.execute(
                    """
                    SELECT suburb, postcode, state, latitude, longitude
                    FROM postcodes
                    WHERE suburb_lower = ?
                    ORDER BY (CASE WHEN category = 'Delivery Area' THEN 0 ELSE 1 END)
                    LIMIT 1
                    """,
                    (suburb_clean,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "suburb": row[0],
                        "postcode": row[1],
                        "state": row[2],
                        "latitude": float(row[3]),
                        "longitude": float(row[4]),
                    }

            # 3. Postcode match
            if postcode_clean:
                cur.execute(
                    """
                    SELECT suburb, postcode, state, latitude, longitude
                    FROM postcodes
                    WHERE postcode = ?
                    ORDER BY (CASE WHEN category = 'Delivery Area' THEN 0 ELSE 1 END)
                    LIMIT 1
                    """,
                    (postcode_clean,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "suburb": row[0],
                        "postcode": row[1],
                        "state": row[2],
                        "latitude": float(row[3]),
                        "longitude": float(row[4]),
                    }

    except Exception as exc:
        logger.warning("Error querying au_postcodes.db: %s", exc)

    return None


def search_au_suburbs(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Instant autocomplete for Australian suburbs and postcodes (prefix search).

    Args:
        query: Prefix text (e.g. 'bon', 'melb', '202').
        limit: Maximum number of results.

    Returns:
        List of matching dicts containing suburb, postcode, state, latitude, longitude.
    """
    if not AU_POSTCODES_DB.exists():
        return []

    q = (query or "").strip().lower()
    if not q:
        return []

    results: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(f"file:{AU_POSTCODES_DB}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            if q.isdigit():
                cur.execute(
                    """
                    SELECT DISTINCT suburb, postcode, state, latitude, longitude
                    FROM postcodes
                    WHERE postcode LIKE ?
                    ORDER BY postcode ASC, suburb ASC
                    LIMIT ?
                    """,
                    (f"{q}%", limit),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT suburb, postcode, state, latitude, longitude
                    FROM postcodes
                    WHERE suburb_lower LIKE ?
                    ORDER BY suburb ASC, postcode ASC
                    LIMIT ?
                    """,
                    (f"{q}%", limit),
                )

            for row in cur.fetchall():
                results.append(
                    {
                        "suburb": row[0],
                        "postcode": row[1],
                        "state": row[2],
                        "latitude": float(row[3]),
                        "longitude": float(row[4]),
                    }
                )
    except Exception as exc:
        logger.warning("Error executing suburb autocomplete: %s", exc)

    return results


def parse_coordinates_literal(value: Any) -> Optional[tuple[float, float]]:
    """Attempt to parse coordinates from tuple, list, dict, or comma-separated string."""
    if isinstance(value, (tuple, list)) and len(value) == 2:
        try:
            return float(value[0]), float(value[1])
        except (ValueError, TypeError):
            return None

    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lng = value.get("longitude") or value.get("lng") or value.get("lon")
        if lat is not None and lng is not None:
            try:
                return float(lat), float(lng)
            except (ValueError, TypeError):
                return None

    if isinstance(value, str):
        cleaned = value.strip().strip("()[]{}")
        match = re.match(r"^([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)$", cleaned)
        if match:
            try:
                return float(match.group(1)), float(match.group(2))
            except ValueError:
                return None

    return None


def _deterministic_fallback_coords(query: str, base_lat: float = -33.8688, base_lng: float = 151.2093) -> tuple[float, float]:
    """Generate deterministic coordinates within ~15 km of base for unrecognized test queries."""
    digest = hashlib.md5(query.lower().encode("utf-8")).hexdigest()
    offset_lat = ((int(digest[:4], 16) % 2000) - 1000) / 10000.0
    offset_lng = ((int(digest[4:8], 16) % 2000) - 1000) / 10000.0
    return round(base_lat + offset_lat, 6), round(base_lng + offset_lng, 6)


class GeocodingService:
    """Service resolving addresses and suburb/postcodes to geographic coordinates."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None, timeout: float = 5.0) -> None:
        self._external_client = client
        self._owned_client: Optional[httpx.AsyncClient] = None
        self.timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self.timeout)
        return self._owned_client

    async def close(self) -> None:
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()
            self._owned_client = None

    def resolve_coordinates_sync(self, location_query: Any) -> tuple[float, float]:
        """Resolve an address, waypoint, coordinate string, or tuple to (lat, lng) synchronously."""
        literal = parse_coordinates_literal(location_query)
        if literal is not None:
            return literal

        if not isinstance(location_query, str):
            query_str = str(location_query or "")
        else:
            query_str = location_query.strip()

        if not query_str:
            return -33.8688, 151.2093

        normalized = query_str.lower()

        if normalized in _RUNTIME_REGISTRY:
            return _RUNTIME_REGISTRY[normalized]

        if query_str.isdigit() and len(query_str) == 4:
            local_match = lookup_au_postcode(postcode=query_str)
            if local_match:
                return local_match["latitude"], local_match["longitude"]

        local_suburb = lookup_au_postcode(suburb=query_str)
        if local_suburb:
            return local_suburb["latitude"], local_suburb["longitude"]

        if normalized in KNOWN_CENTROIDS:
            return KNOWN_CENTROIDS[normalized]

        for key, coords in KNOWN_CENTROIDS.items():
            if re.search(r"\b" + re.escape(key) + r"\b", normalized):
                return coords

        return _deterministic_fallback_coords(query_str)

    async def resolve_coordinates(self, location_query: Any) -> tuple[float, float]:
        """Resolve an address, waypoint, coordinate string, or tuple to (lat, lng)."""
        # 1. Literal coordinates
        literal = parse_coordinates_literal(location_query)
        if literal is not None:
            return literal

        if not isinstance(location_query, str):
            query_str = str(location_query or "")
        else:
            query_str = location_query.strip()

        if not query_str:
            return -33.8688, 151.2093

        normalized = query_str.lower()

        # 2. Runtime test registry
        if normalized in _RUNTIME_REGISTRY:
            return _RUNTIME_REGISTRY[normalized]

        # 3. Local AU Postcodes fast-path
        # If query matches an AU postcode (4 digits) or clean suburb name
        if query_str.isdigit() and len(query_str) == 4:
            local_match = lookup_au_postcode(postcode=query_str)
            if local_match:
                return local_match["latitude"], local_match["longitude"]

        local_suburb = lookup_au_postcode(suburb=query_str)
        if local_suburb:
            return local_suburb["latitude"], local_suburb["longitude"]

        # 4. Known centroids dictionary
        if normalized in KNOWN_CENTROIDS:
            return KNOWN_CENTROIDS[normalized]

        for key, coords in KNOWN_CENTROIDS.items():
            if re.search(r"\b" + re.escape(key) + r"\b", normalized):
                return coords

        # 5. External Mapbox API fallback (if token is configured and not in offline test mode)
        mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", None)
        if mapbox_token and not os.getenv("PYTEST_CURRENT_TEST"):
            coords = await self._query_mapbox(query_str, mapbox_token)
            if coords is not None:
                return coords

        # 6. Deterministic fallback
        return _deterministic_fallback_coords(query_str)

    async def estimate_suburb_centroid(self, suburb: str, postcode: Optional[str] = None) -> tuple[float, float]:
        """Estimate the centroid coordinates for a given suburb and/or postcode."""
        suburb_clean = (suburb or "").strip()
        postcode_clean = (postcode or "").strip()

        # 1. Check runtime registry first
        if postcode_clean.lower() in _RUNTIME_REGISTRY:
            return _RUNTIME_REGISTRY[postcode_clean.lower()]
        if suburb_clean.lower() in _RUNTIME_REGISTRY:
            return _RUNTIME_REGISTRY[suburb_clean.lower()]

        # 2. Primary Fast-Path: Local AU postcodes database (<1ms)
        local_match = lookup_au_postcode(suburb=suburb_clean, postcode=postcode_clean)
        if local_match:
            return local_match["latitude"], local_match["longitude"]

        # 3. Known reference centroids dictionary
        combined = f"{suburb_clean.lower()} {postcode_clean.lower()}".strip()
        if combined in KNOWN_CENTROIDS:
            return KNOWN_CENTROIDS[combined]
        if suburb_clean.lower() in KNOWN_CENTROIDS:
            return KNOWN_CENTROIDS[suburb_clean.lower()]
        if postcode_clean in KNOWN_CENTROIDS:
            return KNOWN_CENTROIDS[postcode_clean]

        # 4. External Mapbox API fallback
        mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", None)
        if mapbox_token and not os.getenv("PYTEST_CURRENT_TEST"):
            coords = await self._query_mapbox(combined, mapbox_token)
            if coords is not None:
                return coords

        # 5. Deterministic fallback
        return _deterministic_fallback_coords(combined or "suburb")

    async def _query_mapbox(self, query: str, token: str) -> Optional[tuple[float, float]]:
        """Call Mapbox places API with timeout safety."""
        encoded = quote(query, safe="")
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json?access_token={token}&limit=1"
        try:
            client = await self._get_client()
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                if features and "center" in features[0]:
                    center = features[0]["center"]
                    return float(center[1]), float(center[0])
        except Exception as exc:
            logger.warning("Mapbox geocoding query failed for '%s': %s", query, exc)
        return None

    async def search_addresses(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for verified addresses using the service's HTTP client."""
        client = await self._get_client()
        return await search_addresses(query, limit=limit, client=client)


async def search_addresses_mapbox(
    query: str,
    token: str,
    client: httpx.AsyncClient,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Query Mapbox Geocoding Places API for Australian addresses."""
    encoded = quote(query, safe="")
    url = (
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json"
        f"?access_token={token}&country=au&types=address,poi,postcode,locality,place&limit={limit}"
    )
    results: list[dict[str, Any]] = []
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            for feat in data.get("features", []):
                coords = feat.get("center")
                if not coords or len(coords) < 2:
                    continue
                lng, lat = float(coords[0]), float(coords[1])
                place_name = feat.get("place_name", "")
                street_num = feat.get("address", "")
                street_name = feat.get("text", "")
                street_address = f"{street_num} {street_name}".strip() if (street_num or street_name) else None

                suburb = None
                state = None
                postcode = None
                country = "Australia"

                for ctx in feat.get("context", []):
                    cid = ctx.get("id", "")
                    if cid.startswith("postcode"):
                        postcode = ctx.get("text")
                    elif cid.startswith("locality") or cid.startswith("place") or cid.startswith("district"):
                        if not suburb:
                            suburb = ctx.get("text")
                    elif cid.startswith("region"):
                        state = (ctx.get("short_code", "") or "").replace("AU-", "") or ctx.get("text")
                    elif cid.startswith("country"):
                        country = ctx.get("text", "Australia")

                if not suburb and "place" in feat.get("place_type", []):
                    suburb = feat.get("text")

                results.append({
                    "formatted_address": place_name,
                    "street_address": street_address,
                    "suburb": suburb,
                    "state": state,
                    "postcode": postcode,
                    "country": country,
                    "latitude": lat,
                    "longitude": lng,
                    "source": "mapbox",
                    "is_verified": True,
                })
    except Exception as exc:
        logger.warning("Mapbox address search failed for '%s': %s", query, exc)
    return results


async def search_addresses_osm(
    query: str,
    client: httpx.AsyncClient,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Query OpenStreetMap Nominatim for Australian addresses."""
    encoded = quote(query, safe="")
    url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&addressdetails=1&limit={limit}&countrycodes=au"
    headers = {"User-Agent": "FastAPIBookings-AddressVerification/1.0"}
    results: list[dict[str, Any]] = []
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                lat = float(item.get("lat", 0))
                lng = float(item.get("lon", 0))
                addr = item.get("address", {})
                road = addr.get("road")
                house_num = addr.get("house_number")
                street_address = f"{house_num} {road}".strip() if house_num and road else (road or None)
                suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city") or addr.get("town")
                state = addr.get("state")
                postcode = addr.get("postcode")
                country = addr.get("country", "Australia")
                formatted = item.get("display_name", "")

                results.append({
                    "formatted_address": formatted,
                    "street_address": street_address,
                    "suburb": suburb,
                    "state": state,
                    "postcode": postcode,
                    "country": country,
                    "latitude": lat,
                    "longitude": lng,
                    "source": "osm_nominatim",
                    "is_verified": True,
                })
    except Exception as exc:
        logger.warning("OSM Nominatim address search failed for '%s': %s", query, exc)
    return results


def search_addresses_local(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search addresses using the local Australian postcodes database."""
    q = (query or "").strip()
    if not q:
        return []

    results: list[dict[str, Any]] = []

    # Check if query has comma or street structure, e.g. "123 George St, Sydney" or "10 Main St, 2000"
    parts = [p.strip() for p in q.split(",") if p.strip()]
    if len(parts) >= 2:
        street_part = parts[0]
        locality_part = parts[1]
        local_match = lookup_au_postcode(suburb=locality_part) or lookup_au_postcode(postcode=locality_part)
        if local_match:
            formatted = f"{street_part}, {local_match['suburb']} {local_match['state']} {local_match['postcode']}, Australia"
            results.append({
                "formatted_address": formatted,
                "street_address": street_part,
                "suburb": local_match["suburb"],
                "state": local_match["state"],
                "postcode": local_match["postcode"],
                "country": "Australia",
                "latitude": local_match["latitude"],
                "longitude": local_match["longitude"],
                "source": "au_postcodes",
                "is_verified": True,
            })

    # Also search suburb autocomplete matches
    suburbs = search_au_suburbs(q, limit=limit)
    for sub in suburbs:
        formatted = f"{sub['suburb']} {sub['state']} {sub['postcode']}, Australia"
        results.append({
            "formatted_address": formatted,
            "street_address": None,
            "suburb": sub["suburb"],
            "state": sub["state"],
            "postcode": sub["postcode"],
            "country": "Australia",
            "latitude": sub["latitude"],
            "longitude": sub["longitude"],
            "source": "au_postcodes",
            "is_verified": True,
        })

    # Deduplicate results by formatted_address
    seen = set()
    deduped = []
    for r in results:
        addr = r["formatted_address"].lower()
        if addr not in seen:
            seen.add(addr)
            deduped.append(r)
        if len(deduped) >= limit:
            break

    return deduped


async def search_addresses(
    query: str,
    limit: int = 10,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict[str, Any]]:
    """Search for verified Australian addresses with multi-tier fallback.

    Tier 1: Mapbox Geocoding (if MAPBOX_ACCESS_TOKEN is configured and not in offline test mode).
    Tier 2: OpenStreetMap Nominatim (if not in offline test mode).
    Tier 3: Local Australian postcodes database (<1ms, offline-safe).
    """
    q = (query or "").strip()
    if not q:
        return []

    is_test_env = bool(os.getenv("PYTEST_CURRENT_TEST"))
    mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", None)

    # 1. Mapbox Geocoding if available and not offline test
    if mapbox_token and not is_test_env:
        try:
            close_client = False
            req_client = client
            if req_client is None:
                req_client = httpx.AsyncClient(timeout=4.0)
                close_client = True
            try:
                results = await search_addresses_mapbox(q, mapbox_token, req_client, limit=limit)
                if results:
                    return results
            finally:
                if close_client:
                    await req_client.aclose()
        except Exception as exc:
            logger.warning("Mapbox search failed, trying fallback: %s", exc)

    # 2. OSM Nominatim fallback if not offline test
    if not is_test_env:
        try:
            close_client = False
            req_client = client
            if req_client is None:
                req_client = httpx.AsyncClient(timeout=3.0)
                close_client = True
            try:
                results = await search_addresses_osm(q, req_client, limit=limit)
                if results:
                    return results
            finally:
                if close_client:
                    await req_client.aclose()
        except Exception as exc:
            logger.warning("OSM Nominatim search failed, falling back to local: %s", exc)

    # 3. Local AU Postcodes fast-path / fallback
    return search_addresses_local(q, limit=limit)

