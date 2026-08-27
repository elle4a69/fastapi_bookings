import asyncio

import pytest
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from app.db import url_crud
from app.core.config import settings


class StubCollection:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = 0

    async def find_one_and_update(self, _filter, update, upsert, return_document):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, dict):
            return outcome
        document = update["$setOnInsert"].copy()
        document["_id"] = f"stub{self.calls}"
        return document


class StubDB:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, _name):
        return self.collection


@pytest.mark.asyncio
async def test_create_url_retries_on_duplicate_short_url(monkeypatch):
    monkeypatch.setattr(settings, "db_retry_count", 1)
    monkeypatch.setattr(settings, "db_retry_delay_seconds", 0)
    monkeypatch.setattr(settings, "short_url_retry_count", 2)

    outcomes = [DuplicateKeyError("dup"), True]
    db = StubDB(StubCollection(outcomes))
    base_url = settings.short_base_url.rstrip("/")
    short_urls = iter([f"{base_url}/second"])

    def factory():
        return next(short_urls)

    result = await url_crud.create_url(
        db,
        "https://example.com/a",
        f"{base_url}/first",
        short_url_factory=factory,
        max_attempts=2,
    )
    assert result.short_url == f"{base_url}/second"


@pytest.mark.asyncio
async def test_create_url_retries_on_db_timeout(monkeypatch):
    monkeypatch.setattr(settings, "db_retry_count", 2)
    monkeypatch.setattr(settings, "db_retry_delay_seconds", 0)
    monkeypatch.setattr(settings, "short_url_retry_count", 1)

    outcomes = [ServerSelectionTimeoutError("timeout"), True]
    db = StubDB(StubCollection(outcomes))

    result = await url_crud.create_url(
        db,
        "https://example.com/b",
        f"{settings.short_base_url.rstrip('/')}/ok",
        max_attempts=1,
    )
    assert str(result.long_url) == "https://example.com/b"


@pytest.mark.asyncio
async def test_batch_creation_concurrency_is_bounded(monkeypatch):
    active = 0
    max_active = 0

    async def fake_upsert(_db, long_url, short_url, created_at, short_code=None):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "_id": short_code,
            "long_url": long_url,
            "short_url": short_url,
            "short_code": short_code,
            "created_at": created_at,
        }

    monkeypatch.setattr(url_crud, "_find_one_and_update_with_retry", fake_upsert)
    url_pairs = [
        {
            "long_url": f"https://example.com/{index}",
            "short_url": f"http://short.url/{index}",
        }
        for index in range(12)
    ]
    outcomes = await url_crud.create_urls_concurrently(
        object(),
        url_pairs,
        max_concurrency=3,
    )

    assert max_active == 3
    assert all(outcome.success for outcome in outcomes)
    assert [outcome.index for outcome in outcomes] == list(range(12))
