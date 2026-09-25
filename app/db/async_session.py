"""Asynchronous database session and engine configuration.

Provides an async SQLAlchemy engine, async session factory, and
a ``get_async_db`` dependency generator supporting PostgreSQL via asyncpg
and SQLite fallback via aiosqlite for offline unit tests.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..core.config import settings


def create_async_db_engine(url: str | None = None) -> AsyncEngine:
    """Create a SQLAlchemy asynchronous engine.

    Handles SQLite concurrency configuration when running tests or offline modes,
    and connects to PostgreSQL via asyncpg in development and production.
    """
    db_url = url or settings.async_database_url
    connect_args: dict[str, Any] = {}

    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False

    return create_async_engine(
        db_url,
        connect_args=connect_args,
        echo=False,
        future=True,
    )


# Default module-level async engine bound to configured async database URL
async_engine: AsyncEngine = create_async_db_engine()

# Async session factory for creating scoped async sessions
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an asynchronous transactional session dependency.

    Can be used with FastAPI's ``Depends`` to inject an async database session
    into asynchronous request handlers and dialogue engine graph nodes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for standalone async sessions outside FastAPI request lifecycles."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
