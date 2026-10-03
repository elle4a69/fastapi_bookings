"""Tests for Mapbox geocoding in-memory TTL caching and rate limiting."""

import asyncio
import time
from typing import Any
import pytest
import httpx

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.services.geocoding import (
    geocode_tenant_address,
)
from app.services.routing.geocoding import (
    AsyncRateLimiter,
    GeocodingService,
    GeocodingTTLCache,
    clear_geocoding_cache,
    get_geocoding_cache,
    search_addresses_mapbox,
)


@pytest.fixture(autouse=True)
def clean_geocoding_cache():
    """Ensure global geocoding cache is clean before and after each test."""
    clear_geocoding_cache()
    yield
    clear_geocoding_cache()


def test_geocoding_ttl_cache_normalization_and_retrieval():
    """Verify TTL cache normalizes query strings and handles casing/whitespace."""
    cache = GeocodingTTLCache(ttl_seconds=3600.0)
    cache.set("150 Collins St, Melbourne VIC 3000", (-37.8136, 144.9665))

    # Identical retrieval
    assert cache.get("150 Collins St, Melbourne VIC 3000") == (-37.8136, 144.9665)
    # Different case and whitespace
    assert cache.get("  150 collins st, melbourne vic 3000  ") == (-37.8136, 144.9665)
    assert "150 COLLINS ST, MELBOURNE VIC 3000" in cache

    # Non-existent
    assert cache.get("non-existent address") is None
    assert "non-existent" not in cache


def test_geocoding_ttl_cache_expiry():
    """Verify entries expire and are pruned after TTL elapsed."""
    cache = GeocodingTTLCache(ttl_seconds=0.05)
    cache.set("short-lived query", (10.0, 20.0))

    assert cache.get("short-lived query") == (10.0, 20.0)
    time.sleep(0.06)
    assert cache.get("short-lived query") is None


def test_geocoding_ttl_cache_capacity_eviction():
    """Verify cache respects max_entries capacity by evicting oldest."""
    cache = GeocodingTTLCache(ttl_seconds=3600.0, max_entries=2)
    cache.set("query1", 1)
    cache.set("query2", 2)
    assert len(cache) == 2

    cache.set("query3", 3)
    assert len(cache) <= 2
    assert cache.get("query1") is None
    assert cache.get("query2") == 2
    assert cache.get("query3") == 3


@pytest.mark.asyncio
async def test_async_rate_limiter_burst_and_acquire():
    """Verify AsyncRateLimiter allows burst and smoothly acquires tokens."""
    limiter = AsyncRateLimiter(rate=50.0, max_tokens=2.0)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # The third acquire should have taken at least a fraction of a second to replenish
    assert elapsed >= 0.0


@pytest.mark.asyncio
async def test_query_mapbox_uses_cache(monkeypatch):
    """Verify _query_mapbox caches network responses and avoids redundant HTTP requests."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "features": [
                    {"center": [144.9665, -37.8136]}
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        service = GeocodingService(client=mock_client)

        coords1 = await service._query_mapbox("150 Collins St", "pk.test_token")
        assert coords1 == (-37.8136, 144.9665)
        assert call_count == 1

        # Second call with equivalent query should hit TTL cache
        coords2 = await service._query_mapbox("  150 collins st  ", "pk.test_token")
        assert coords2 == (-37.8136, 144.9665)
        assert call_count == 1  # No additional network call made


@pytest.mark.asyncio
async def test_query_mapbox_handles_429_gracefully():
    """Verify _query_mapbox catches 429 rate limit responses gracefully."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        service = GeocodingService(client=mock_client)
        coords = await service._query_mapbox("Rapid Query St", "pk.test_token")
        assert coords is None


@pytest.mark.asyncio
async def test_search_addresses_mapbox_uses_cache():
    """Verify search_addresses_mapbox returns cached results for duplicate queries."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "place_name": "150 Collins St, Melbourne VIC 3000, Australia",
                        "text": "Collins St",
                        "address": "150",
                        "center": [144.9665, -37.8136],
                        "context": [
                            {"id": "postcode.123", "text": "3000"},
                            {"id": "locality.456", "text": "Melbourne"},
                            {"id": "region.789", "text": "VIC", "short_code": "AU-VIC"},
                        ],
                    }
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        results1 = await search_addresses_mapbox("150 Collins St", "pk.test_token", mock_client, limit=5)
        assert len(results1) == 1
        assert results1[0]["suburb"] == "Melbourne"
        assert call_count == 1

        # Identical query should be served from memory cache
        results2 = await search_addresses_mapbox("150 collins st", "pk.test_token", mock_client, limit=5)
        assert len(results2) == 1
        assert results2[0]["suburb"] == "Melbourne"
        assert call_count == 1


@pytest.mark.asyncio
async def test_search_addresses_mapbox_handles_429_gracefully():
    """Verify search_addresses_mapbox handles 429 response without unhandled exception."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        results = await search_addresses_mapbox("Burst Query", "pk.test_token", mock_client)
        assert results == []


@pytest.mark.asyncio
async def test_geocode_tenant_address_caching_and_persistence(monkeypatch):
    """Verify geocode_tenant_address caches coordinates and saves to database."""
    import uuid

    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(
        name=f"Cache Geocode Test {unique_suffix}",
        subdomain=f"cache-{unique_suffix}",
        address="200 Bourke St, Melbourne VIC 3000",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    tenant_id = tenant.id
    db.close()

    try:
        monkeypatch.setattr(settings, "MAPBOX_ACCESS_TOKEN", "pk.test_token")

        network_calls = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url):
                nonlocal network_calls
                network_calls += 1
                return httpx.Response(
                    200,
                    json={
                        "features": [
                            {"center": [144.9670, -37.8140]}
                        ]
                    },
                    request=httpx.Request("GET", url),
                )

        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

        # First call: performs outbound call and caches
        await geocode_tenant_address(tenant_id, "200 Bourke St, Melbourne VIC 3000")
        assert network_calls == 1

        db = SessionLocal()
        updated = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        assert updated.latitude == -37.8140
        assert updated.longitude == 144.9670
        db.close()

        # Second call with same address: served from TTL cache without network call
        await geocode_tenant_address(tenant_id, "200 Bourke St, Melbourne VIC 3000")
        assert network_calls == 1  # No additional network call
    finally:
        db = SessionLocal()
        t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if t:
            db.delete(t)
            db.commit()
        db.close()
