import time
import asyncio
import structlog
from functools import wraps
from collections.abc import Callable
from typing import TypeVar, ParamSpec, Awaitable, Iterable
from pymongo.errors import ServerSelectionTimeoutError

P = ParamSpec("P")
R = TypeVar("R")
logger = structlog.get_logger(__name__)


def retry(retry_count: int = 3, wait_seconds: int = 2):
    def decorator(func: Callable[P, R]):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal retry_count
            attempts = 0
            while attempts < retry_count:
                try:
                    return func(*args, **kwargs)
                except ServerSelectionTimeoutError as exc:
                    logger.warning(
                        "database_operation_retry",
                        attempt=attempts + 1,
                        error_type=type(exc).__name__,
                    )
                    time.sleep(wait_seconds)
                    attempts += 1
            return func(*args, **kwargs)

        return wrapper

    return decorator


async def async_retry(
    func: Callable[[], Awaitable[R]],
    retry_count: int = 3,
    wait_seconds: float = 0.2,
    exceptions: Iterable[type[Exception]] = (ServerSelectionTimeoutError,),
) -> R:
    attempts = 0
    while attempts < retry_count:
        try:
            return await func()
        except tuple(exceptions) as exc:
            if attempts == retry_count - 1:
                raise
            logger.warning(
                "database_operation_retry",
                attempt=attempts + 1,
                error_type=type(exc).__name__,
            )
            await asyncio.sleep(wait_seconds)
            attempts += 1
