from typing import Any, Optional

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings


class MongoDB:
    client: Optional[AsyncMongoClient[dict[str, Any]]] = None


def initialize_mongodb() -> AsyncMongoClient[dict[str, Any]]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.database_url,
        serverSelectionTimeoutMS=settings.database_server_selection_timeout_ms,
    )
    MongoDB.client = client
    return client


def get_db() -> AsyncDatabase[dict[str, Any]]:
    if MongoDB.client is None:
        raise RuntimeError("MongoDB client has not been initialized.")
    return MongoDB.client[settings.database_name]


async def ping_mongodb() -> None:
    if MongoDB.client is None:
        raise RuntimeError("MongoDB client has not been initialized.")
    await MongoDB.client.admin.command({"ping": 1})


async def close_mongodb() -> None:
    if MongoDB.client is None:
        return
    client = MongoDB.client
    MongoDB.client = None
    await client.close()
