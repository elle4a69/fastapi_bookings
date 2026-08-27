import structlog
from fastapi import APIRouter, HTTPException, Depends, Response, status
from fastapi.responses import RedirectResponse
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from app.schemas.url import (
    URLBatchItemResponse,
    URLBatchResponse,
    URLCreate,
    URLResponse,
)
from app.api.dependencies import get_database_client
from app.services.url_service import URLShortener
from app.core.config import settings
from app.core.metrics import BATCH_ITEMS_TOTAL
from app.db.url_crud import (
    create_url,
    get_url_by_short,
    update_access_count,
    delete_url,
    create_urls_concurrently as create_urls_in_batch,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

url_shortener = URLShortener(base_url=settings.short_base_url)


def _new_short_url() -> str:
    return url_shortener.build_short_url(url_shortener.generate_short_code())


def _validate_batch_size(urls: list[URLCreate]) -> None:
    if not urls:
        raise HTTPException(status_code=400, detail="URL list is empty.")
    if len(urls) > settings.max_batch_size:
        raise HTTPException(
            status_code=413,
            detail=f"Batch size exceeds the limit of {settings.max_batch_size}.",
        )


def _batch_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, DuplicateKeyError):
        return "short_code_collision", True
    if isinstance(exc, PyMongoError):
        return "storage_unavailable", True
    return "internal_error", False


async def _create_batch_response(
    urls: list[URLCreate],
    db: AsyncDatabase,
    max_concurrency: int,
) -> URLBatchResponse:
    _validate_batch_size(urls)
    url_pairs = [
        {
            "long_url": str(url_request.long_url),
            "short_url": _new_short_url(),
        }
        for url_request in urls
    ]
    outcomes = await create_urls_in_batch(
        db,
        url_pairs,
        short_url_factory=_new_short_url,
        max_attempts=settings.short_url_retry_count,
        max_concurrency=max_concurrency,
    )

    results: list[URLBatchItemResponse] = []
    success_count = 0
    for outcome in outcomes:
        if outcome.success and outcome.model is not None:
            success_count += 1
            BATCH_ITEMS_TOTAL.labels("success").inc()
            results.append(
                URLBatchItemResponse(
                    index=outcome.index,
                    long_url=outcome.model.long_url,
                    status="success",
                    short_url=outcome.model.short_url,
                    created_at=outcome.model.created_at,
                )
            )
            continue

        error = outcome.error or RuntimeError("Unknown batch creation error.")
        error_code, retryable = _batch_error(error)
        BATCH_ITEMS_TOTAL.labels("failed").inc()
        logger.warning(
            "batch_item_create_failed",
            item_index=outcome.index,
            error_code=error_code,
            error_type=type(error).__name__,
        )
        results.append(
            URLBatchItemResponse(
                index=outcome.index,
                long_url=outcome.long_url,
                status="failed",
                error_code=error_code,
                retryable=retryable,
            )
        )

    failure_count = len(results) - success_count
    return URLBatchResponse(
        results=results,
        success_count=success_count,
        failure_count=failure_count,
    )


@router.post("/shorten/", response_model=URLResponse)
async def create_short_url(
    url_request: URLCreate, db: AsyncDatabase = Depends(get_database_client)
):
    long_url = str(url_request.long_url)
    short_url = _new_short_url()

    try:
        url_model = await create_url(
            db,
            long_url,
            short_url,
            short_url_factory=_new_short_url,
            max_attempts=settings.short_url_retry_count,
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=500, detail="Failed to generate unique short URL."
        )
    return URLResponse(
        long_url=url_model.long_url,
        short_url=url_model.short_url,
        created_at=url_model.created_at,
    )


@router.post(
    "/shorten/batch/",
    response_model=URLBatchResponse,
    responses={207: {"description": "One or more items failed."}},
)
async def create_short_urls(
    urls: list[URLCreate],
    response: Response,
    db: AsyncDatabase = Depends(get_database_client),
):
    batch_response = await _create_batch_response(urls, db, max_concurrency=1)
    if batch_response.failure_count:
        response.status_code = status.HTTP_207_MULTI_STATUS
    return batch_response


@router.post(
    "/shorten/batch/concurrent/",
    response_model=URLBatchResponse,
    responses={207: {"description": "One or more items failed."}},
)
async def create_short_urls_concurrently(
    urls: list[URLCreate],
    response: Response,
    db: AsyncDatabase = Depends(get_database_client),
):
    batch_response = await _create_batch_response(
        urls,
        db,
        max_concurrency=settings.batch_max_concurrency,
    )
    if batch_response.failure_count:
        response.status_code = status.HTTP_207_MULTI_STATUS
    return batch_response


@router.get("/{short_url:path}")
async def redirect_to_long_url(
    short_url: str, db: AsyncDatabase = Depends(get_database_client)
):
    url_model = await get_url_by_short(db, short_url)
    if url_model is None:
        raise HTTPException(status_code=404, detail="URL not found")
    await update_access_count(db, url_model.short_url)
    response_model = URLResponse.from_raw(
        short_url=short_url, long_url=url_model.long_url
    )
    return RedirectResponse(url=response_model.long_url)


@router.delete("/urls/delete/{short_url:path}")
async def delete_short_url(
    short_url: str, db: AsyncDatabase = Depends(get_database_client)
):
    url_model = await get_url_by_short(db, short_url)
    if url_model is None:
        raise HTTPException(status_code=404, detail="URL not found or already deleted.")
    success = await delete_url(db, url_model.short_url)
    if success:
        return {"detail": "URL deleted successfully."}
    else:
        raise HTTPException(status_code=404, detail="URL not found or already deleted.")
