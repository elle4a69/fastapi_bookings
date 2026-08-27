from collections.abc import AsyncIterator

from app.db.url_mongodb import get_db
from pymongo.asynchronous.database import AsyncDatabase


async def get_database_client() -> AsyncIterator[AsyncDatabase]:
    db = get_db()
    yield db
