"""Track 1 Foundation, Infrastructure & Database Models verification tests."""

import os
from datetime import datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.db import (
    Base,
    AsyncSessionLocal,
    async_engine,
    async_session_scope,
    create_async_db_engine,
    get_async_db,
)
from app.models import CuratedMemory, Provider, Service, Tenant
from app.core.config import Settings


def test_package_structure():
    """Verify that required directory packages exist with __init__.py files."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    required_packages = [
        "app/engine",
        "app/services/scheduling",
        "app/services/routing",
        "app/services/curation",
    ]
    for pkg in required_packages:
        pkg_path = os.path.join(base_dir, pkg)
        assert os.path.isdir(pkg_path), f"Package directory missing: {pkg}"
        assert os.path.isfile(os.path.join(pkg_path, "__init__.py")), f"Missing __init__.py in: {pkg}"


def test_models_export():
    """Verify CuratedMemory, Provider, and Service are exported in app.models."""
    assert "CuratedMemory" in app.models.__all__
    assert hasattr(app.models, "CuratedMemory")
    assert getattr(app.models, "CuratedMemory") is CuratedMemory
    assert "Provider" in app.models.__all__
    assert "Service" in app.models.__all__


def test_curated_memory_schema():
    """Verify CuratedMemory model columns, constraints, and attributes."""
    cols = {c.name: c for c in CuratedMemory.__table__.columns}

    expected_cols = [
        "id",
        "tenant_id",
        "provider_id",
        "category",
        "user_query",
        "ideal_response",
        "embedding",
        "confidence_score",
        "last_verified_at",
        "created_at",
        "updated_at",
    ]
    for col_name in expected_cols:
        assert col_name in cols, f"CuratedMemory missing column '{col_name}'"

    assert cols["tenant_id"].nullable is False
    assert cols["provider_id"].nullable is True
    assert cols["category"].nullable is False
    assert cols["user_query"].nullable is False
    assert cols["ideal_response"].nullable is False
    assert cols["confidence_score"].default.arg == 1.0


def test_provider_incall_outcall_schema():
    """Verify Provider in-call and out-call fields and defaults."""
    cols = {c.name: c for c in Provider.__table__.columns}

    assert "in_call_address" in cols
    assert cols["in_call_address"].nullable is True

    assert "out_call_radius_km" in cols
    assert cols["out_call_radius_km"].default.arg == 25.0

    assert "base_outcall_surcharge" in cols
    assert float(cols["base_outcall_surcharge"].default.arg) == 0.00

    assert "per_km_fee" in cols
    assert float(cols["per_km_fee"].default.arg) == 0.00

    assert "turnaround_buffer_mins" in cols
    assert cols["turnaround_buffer_mins"].default.arg == 15


def test_service_incall_outcall_schema():
    """Verify Service allow_in_call and allow_out_call flags."""
    cols = {c.name: c for c in Service.__table__.columns}

    assert "allow_in_call" in cols
    assert cols["allow_in_call"].default.arg is True

    assert "allow_out_call" in cols
    assert cols["allow_out_call"].default.arg is True


def test_async_database_url_property():
    """Verify conversion of database URLs to async drivers."""
    # SQLite
    s_sqlite = Settings(DATABASE_URL="sqlite:///./test.db")
    assert s_sqlite.async_database_url == "sqlite+aiosqlite:///./test.db"

    # PostgreSQL standard
    s_pg = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/dbname")
    assert s_pg.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/dbname"

    # PostgreSQL psycopg2
    s_psycopg = Settings(DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/dbname")
    assert s_psycopg.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/dbname"

    # Explicit override
    s_custom = Settings(
        DATABASE_URL="sqlite:///./test.db",
        ASYNC_DATABASE_URL="postgresql+asyncpg://remote:5432/db",
    )
    assert s_custom.async_database_url == "postgresql+asyncpg://remote:5432/db"


@pytest.mark.asyncio
async def test_async_database_lifecycle_and_crud():
    """Verify async engine, table creation, and CRUD for CuratedMemory, Provider, and Service."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Create tenant
        tenant = Tenant(name="Acme Health", subdomain="acme", email="admin@acme.test")
        session.add(tenant)
        await session.flush()

        # Create provider with in-call / out-call settings
        provider = Provider(
            tenant_id=tenant.id,
            name="Alice Walker",
            in_call_address="45 Market Street, Suite 2",
            out_call_radius_km=35.0,
            base_outcall_surcharge=25.00,
            per_km_fee=2.00,
            turnaround_buffer_mins=20,
        )
        session.add(provider)
        await session.flush()

        # Create service with in-call / out-call settings
        service = Service(
            tenant_id=tenant.id,
            name="Deep Tissue Massage",
            duration=90,
            price=150.00,
            allow_in_call=True,
            allow_out_call=True,
        )
        session.add(service)
        await session.flush()

        # Create CuratedMemory
        dummy_vector = [0.05] * 1536
        memory = CuratedMemory(
            tenant_id=tenant.id,
            provider_id=provider.id,
            category="pricing",
            user_query="How much does deep tissue massage cost?",
            ideal_response="Deep tissue massage is $150 for a 90 minute session.",
            embedding=dummy_vector,
            confidence_score=0.95,
        )
        session.add(memory)
        await session.commit()

        # Query back and verify CuratedMemory
        res = await session.execute(select(CuratedMemory).where(CuratedMemory.id == memory.id))
        cm = res.scalar_one()
        assert cm.category == "pricing"
        assert cm.confidence_score == 0.95
        assert cm.tenant_id == tenant.id
        assert cm.provider_id == provider.id
        assert "pricing" in repr(cm)

        # Query back and verify Provider
        res_p = await session.execute(select(Provider).where(Provider.id == provider.id))
        p = res_p.scalar_one()
        assert p.in_call_address == "45 Market Street, Suite 2"
        assert p.out_call_radius_km == 35.0
        assert Decimal(p.base_outcall_surcharge) == Decimal("25.00")
        assert Decimal(p.per_km_fee) == Decimal("2.00")
        assert p.turnaround_buffer_mins == 20

        # Query back and verify Service
        res_s = await session.execute(select(Service).where(Service.id == service.id))
        s = res_s.scalar_one()
        assert s.allow_in_call is True
        assert s.allow_out_call is True

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_async_db_dependency(monkeypatch):
    """Test the get_async_db generator yields a working AsyncSession and cleanly closes."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_sessionmaker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    import app.db.async_session as async_mod
    monkeypatch.setattr(async_mod, "AsyncSessionLocal", test_sessionmaker)

    gen = async_mod.get_async_db()
    session = await anext(gen)
    assert isinstance(session, AsyncSession)

    # Clean exit
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    await test_engine.dispose()
