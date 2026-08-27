import pytest

from app.db.url_crud import ensure_indexes
from app.services.url_service import URLShortener
from app.utils.data_cleanup import (
    _apply_cleanup,
    _build_report,
    _reassign_duplicate_short_codes,
    _rebuild_short_code_index,
    _synchronize_short_codes,
)
from tests.fakes import FakeDatabase


@pytest.mark.asyncio
async def test_synchronize_short_code_from_short_url():
    database = FakeDatabase()
    database.collection.documents = [
        {
            "_id": "one",
            "long_url": "https://example.com/one",
            "short_url": "http://short.url/expected",
            "short_code": "stale",
        }
    ]

    synchronized = await _synchronize_short_codes(database.collection)

    assert synchronized == 1
    assert database.collection.documents[0]["short_code"] == "expected"


@pytest.mark.asyncio
async def test_duplicate_short_code_reassigns_url_and_code_together(monkeypatch):
    database = FakeDatabase()
    database.collection.documents = [
        {
            "_id": "one",
            "long_url": "https://example.com/one",
            "short_url": "http://short.url/same",
            "short_code": "same",
            "created_at": 1,
            "access_count": 10,
        },
        {
            "_id": "two",
            "long_url": "https://example.com/two",
            "short_url": "http://legacy.url/same",
            "short_code": "same",
            "created_at": 2,
            "access_count": 1,
        },
    ]
    shortener = URLShortener(base_url="http://short.url")
    monkeypatch.setattr(shortener, "generate_short_code", lambda: "replacement")

    reassigned = await _reassign_duplicate_short_codes(
        database.collection,
        shortener,
        max_attempts=2,
    )

    assert reassigned == 1
    assert {doc["short_code"] for doc in database.collection.documents} == {
        "same",
        "replacement",
    }
    replacement = next(
        doc
        for doc in database.collection.documents
        if doc["short_code"] == "replacement"
    )
    assert replacement["short_url"] == "http://short.url/replacement"


@pytest.mark.asyncio
async def test_rebuild_legacy_short_code_index_as_unique():
    database = FakeDatabase()
    database.collection.indexes["short_code_1"] = {
        "key": [("short_code", 1)],
        "unique": False,
    }

    rebuilt = await _rebuild_short_code_index(database.collection)

    assert rebuilt is True
    assert database.collection.indexes["short_code_1"]["unique"] is True


@pytest.mark.asyncio
async def test_ensure_indexes_requires_unique_short_code():
    database = FakeDatabase()

    await ensure_indexes(database)

    assert database.collection.indexes["long_url_1"]["unique"] is True
    assert database.collection.indexes["short_url_1"]["unique"] is True
    assert database.collection.indexes["short_code_1"]["unique"] is True


@pytest.mark.asyncio
async def test_cleanup_pipeline_validates_before_rebuilding_index(monkeypatch):
    database = FakeDatabase()
    database.collection.documents = [
        {
            "_id": "one",
            "long_url": "https://example.com/shared",
            "short_url": "http://short.url/same",
            "short_code": "stale-one",
            "created_at": 1,
            "access_count": 3,
        },
        {
            "_id": "two",
            "long_url": "https://example.com/shared",
            "short_url": "http://short.url/removed",
            "short_code": "stale-two",
            "created_at": 2,
            "access_count": 2,
        },
        {
            "_id": "three",
            "long_url": "https://example.com/other",
            "short_url": "http://legacy.url/same",
            "short_code": "stale-three",
            "created_at": 3,
            "access_count": 1,
        },
    ]
    database.collection.indexes["short_code_1"] = {
        "key": [("short_code", 1)],
        "unique": False,
    }
    shortener = URLShortener(base_url="http://short.url")
    monkeypatch.setattr(shortener, "generate_short_code", lambda: "replacement")
    report = await _build_report(database.collection)

    await _apply_cleanup(
        database.collection,
        report,
        shortener,
        max_attempts=2,
        rebuild_indexes=True,
    )

    assert report["actions"]["long_url_deleted"] == 1
    assert report["actions"]["short_code_synchronized"] == 2
    assert report["actions"]["short_code_reassigned"] == 1
    assert report["actions"]["short_code_index_rebuilt"] is True
    assert not any(report["validation"].values())
