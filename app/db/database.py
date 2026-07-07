"""Database module for FastAPI Bookings.

This module defines the SQLAlchemy engine and session factory used by the
application. It also exposes a ``get_db`` dependency for injecting a
database session into request handlers.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..core.config import settings


def _create_engine(url: str):
    """Create a SQLAlchemy engine.

    SQLite requires special handling to allow multi‑threaded access from
    FastAPI's async request handlers. When the database URL begins with
    ``sqlite``, the ``check_same_thread`` flag must be disabled.
    """
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args)


# SQLAlchemy engine bound to the configured database URL
engine = _create_engine(settings.DATABASE_URL)

# Session factory for creating scoped sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """Provide a transactional scope around a series of operations.

    This dependency can be used with FastAPI's ``Depends`` to inject a
    database session into path operations. It ensures that the session
    is closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()