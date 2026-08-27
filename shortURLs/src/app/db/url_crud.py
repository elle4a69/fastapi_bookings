import time
import asyncio
from dataclasses import dataclass
from typing import Optional, Callable
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from app.core.config import settings
from app.models.domain import URLModel
from app.schemas.url import URLInDB
from app.utils.url_utils import async_retry

COLLECTION_NAME = settings.database_collection_name


@dataclass(slots=True)
class BatchCreateOutcome:
    index: int
    long_url: str
    model: Optional[URLModel] = None
    error: Optional[Exception] = None

    @property
    def success(self) -> bool:
        return self.model is not None and self.error is None


async def ensure_indexes(db: AsyncDatabase) -> None:
    await db[COLLECTION_NAME].create_index("long_url", unique=True)
    await db[COLLECTION_NAME].create_index("short_url", unique=True)
    await db[COLLECTION_NAME].create_index("short_code", unique=True)


def _extract_short_code(short_url: str) -> str:
    short_url = str(short_url).rstrip("/")
    return short_url.split("/")[-1] if short_url else ""


async def _find_one_and_update_with_retry(
    db: AsyncDatabase,
    long_url: str,
    short_url: str,
    created_at: int,
    short_code: str | None = None,
):
    async def operation():
        insert_doc = {
            "long_url": long_url,
            "short_url": short_url,
            "created_at": created_at,
        }
        if short_code:
            insert_doc["short_code"] = short_code
        return await db[COLLECTION_NAME].find_one_and_update(
            {"long_url": long_url},
            {"$setOnInsert": insert_doc},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    return await async_retry(
        operation,
        retry_count=settings.db_retry_count,
        wait_seconds=settings.db_retry_delay_seconds,
        exceptions=(ServerSelectionTimeoutError,),
    )


async def _find_one_with_retry(db: AsyncDatabase, query: dict) -> Optional[dict]:
    async def operation():
        return await db[COLLECTION_NAME].find_one(query)

    return await async_retry(
        operation,
        retry_count=settings.db_retry_count,
        wait_seconds=settings.db_retry_delay_seconds,
        exceptions=(ServerSelectionTimeoutError,),
    )


async def _find_many_with_retry(
    db: AsyncDatabase, query: dict, limit: int
) -> list[dict]:
    async def operation():
        cursor = db[COLLECTION_NAME].find(query).limit(limit)
        return await cursor.to_list(length=limit)

    return await async_retry(
        operation,
        retry_count=settings.db_retry_count,
        wait_seconds=settings.db_retry_delay_seconds,
        exceptions=(ServerSelectionTimeoutError,),
    )


async def _update_one_with_retry(db: AsyncDatabase, query: dict, update: dict):
    async def operation():
        return await db[COLLECTION_NAME].update_one(query, update)

    return await async_retry(
        operation,
        retry_count=settings.db_retry_count,
        wait_seconds=settings.db_retry_delay_seconds,
        exceptions=(ServerSelectionTimeoutError,),
    )


async def _delete_one_with_retry(db: AsyncDatabase, query: dict):
    async def operation():
        return await db[COLLECTION_NAME].delete_one(query)

    return await async_retry(
        operation,
        retry_count=settings.db_retry_count,
        wait_seconds=settings.db_retry_delay_seconds,
        exceptions=(ServerSelectionTimeoutError,),
    )


async def create_url(
    db: AsyncDatabase,
    long_url: str,
    short_url: str,
    short_url_factory: Optional[Callable[[], str]] = None,
    max_attempts: int | None = None,
) -> URLModel:
    document = {
        "long_url": str(long_url),
        "short_url": str(short_url),
        "created_at": time.time_ns(),
    }
    short_code = _extract_short_code(document["short_url"])
    if short_code:
        document["short_code"] = short_code
    attempts = max_attempts or settings.short_url_retry_count
    for attempt in range(attempts):
        try:
            updated = await _find_one_and_update_with_retry(
                db,
                document["long_url"],
                document["short_url"],
                document["created_at"],
                short_code=document.get("short_code"),
            )
            if not updated:
                raise RuntimeError("Failed to create or fetch URL document.")
            updated["id"] = str(updated.pop("_id"))
            return URLModel(**updated)
        except DuplicateKeyError:
            if not short_url_factory or attempt == attempts - 1:
                raise
            document["short_url"] = str(short_url_factory())
            short_code = _extract_short_code(document["short_url"])
            if short_code:
                document["short_code"] = short_code
    raise RuntimeError("Failed to create or fetch URL document.")


def _build_url_document(pair: dict) -> dict:
    document = {
        "long_url": str(pair["long_url"]),
        "short_url": str(pair["short_url"]),
        "created_at": pair.get("created_at", time.time_ns()),
    }
    short_code = _extract_short_code(document["short_url"])
    if short_code:
        document["short_code"] = short_code
    return document


async def _upsert_url_document(
    db: AsyncDatabase,
    document: dict,
    semaphore: asyncio.Semaphore,
    short_url_factory: Optional[Callable[[], str]],
    max_attempts: int,
) -> Optional[dict]:
    async with semaphore:
        for attempt in range(max_attempts):
            try:
                return await _find_one_and_update_with_retry(
                    db,
                    document["long_url"],
                    document["short_url"],
                    document["created_at"],
                    short_code=document.get("short_code"),
                )
            except DuplicateKeyError:
                if not short_url_factory or attempt == max_attempts - 1:
                    raise
                document["short_url"] = str(short_url_factory())
                document["short_code"] = _extract_short_code(document["short_url"])
    return None


def _batch_outcomes(documents: list[dict], results: list) -> list[BatchCreateOutcome]:
    outcomes: list[BatchCreateOutcome] = []
    for index, (document, result) in enumerate(zip(documents, results)):
        if isinstance(result, Exception):
            outcomes.append(
                BatchCreateOutcome(
                    index=index,
                    long_url=document["long_url"],
                    error=result,
                )
            )
            continue
        if not result:
            outcomes.append(
                BatchCreateOutcome(
                    index=index,
                    long_url=document["long_url"],
                    error=RuntimeError("URL creation returned no document."),
                )
            )
            continue
        result_copy = dict(result)
        result_copy["id"] = str(result_copy.pop("_id"))
        outcomes.append(
            BatchCreateOutcome(
                index=index,
                long_url=document["long_url"],
                model=URLModel(**result_copy),
            )
        )
    return outcomes


async def create_urls_concurrently(
    db: AsyncDatabase,
    url_pairs: list[dict],
    short_url_factory: Optional[Callable[[], str]] = None,
    max_attempts: int | None = None,
    max_concurrency: int | None = None,
) -> list[BatchCreateOutcome]:
    semaphore = asyncio.Semaphore(max_concurrency or settings.batch_max_concurrency)
    attempts = max_attempts or settings.short_url_retry_count
    documents = [_build_url_document(pair) for pair in url_pairs]
    tasks = [
        _upsert_url_document(
            db,
            document,
            semaphore,
            short_url_factory,
            attempts,
        )
        for document in documents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return _batch_outcomes(documents, results)


async def get_url_by_short(db: AsyncDatabase, short_url: str) -> Optional[URLModel]:
    short_url = str(short_url).rstrip("/")
    short_code = _extract_short_code(short_url)
    if not short_url and not short_code:
        return None
    candidates = []
    if short_url:
        candidates.append(short_url)
    if short_code:
        candidates.append(f"{settings.short_base_url.rstrip('/')}/{short_code}")
    candidates = list(dict.fromkeys(candidates))

    query = {"short_url": {"$in": candidates}}
    document = await _find_one_with_retry(db, query)
    if not document and short_code:
        matches = await _find_many_with_retry(db, {"short_code": short_code}, limit=2)
        if len(matches) == 1:
            document = matches[0]
        else:
            return None

    return (
        URLModel(**{**document, "id": str(document.pop("_id"))}) if document else None
    )


async def update_access_count_bak(db: AsyncDatabase, short_url: str) -> bool:
    result = await _update_one_with_retry(
        db, {"short_url": short_url}, {"$inc": {"access_count": 1}}
    )
    return result.modified_count > 0


async def update_access_count(db: AsyncDatabase, short_url: str) -> Optional[URLInDB]:
    result = await _update_one_with_retry(
        db, {"short_url": short_url}, {"$inc": {"access_count": 1}}
    )

    if result.modified_count > 0:
        updated_record = await _find_one_with_retry(db, {"short_url": short_url})
        if updated_record:
            updated_record["id"] = str(updated_record.pop("_id"))
            return URLInDB(**updated_record)

    return None


async def delete_url(db: AsyncDatabase, short_url: str) -> bool:
    result = await _delete_one_with_retry(db, {"short_url": short_url})
    return result.deleted_count > 0
