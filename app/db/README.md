# Database Management & Connection Subsystem (`app/db/`)

## 1. Purpose & Scope

The `app/db/` module is the authoritative connection management, session lifecycle, and engine configuration layer for **FastAPI Bookings**.

### What it owns:
- **Synchronous Engine & Session Management (`database.py`)**: Configures the primary SQLAlchemy 2.0 synchronous engine, connection pool (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`), pre-ping liveness validation, and the `get_db` dependency for FastAPI synchronous endpoints.
- **Asynchronous Engine & Session Management (`async_session.py`)**: Configures the SQLAlchemy 2.0 asynchronous engine (`create_async_db_engine`), async sessionmaker (`AsyncSessionLocal`), `get_async_db` dependency for async endpoints, and the `async_session_scope()` context manager for background workers and dialogue engines.
- **Dialect Negotiation**: Automatically manages driver parameters across production PostgreSQL (`postgresql+psycopg2` / `postgresql+asyncpg`) and developer/test SQLite (`sqlite3` / `aiosqlite`).
- **Data Seeding Utilities (`seed.py`, `seed_map_data.py`)**: Initial seed script for development tenants, services, providers, and geospatial map entities.

### What it deliberately avoids:
- Does not define business logic, domain models, or table schemas (owned by `app/models/`).
- Does not execute schema migrations or DDL upgrades (owned by `alembic/`).
- Does not manage Redis, Neo4j, or external graph/cache connections (owned by `app/services/knowledge/` and `app/core/`).

---

## 2. Architecture & Key Files

```text
app/db/
├── __init__.py           # Re-exports Base, engine, SessionLocal, get_db, async_engine, AsyncSessionLocal, get_async_db, async_session_scope
├── database.py           # Sync engine creation, connection pooling parameters, declarative Base, get_db dependency
├── async_session.py      # Async engine creation, async_sessionmaker, get_async_db dependency, async_session_scope context manager
├── seed.py               # Development database seeding script
└── seed_map_data.py      # Geospatial and multi-location map seed data
```

### Key Symbols & Call Signatures:
- [`Base`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L45): Declarative base class for all SQLAlchemy ORM models.
- [`engine`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L39): Synchronous SQLAlchemy engine bound to `settings.DATABASE_URL`.
- [`SessionLocal`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L42): Factory for scoped synchronous database sessions.
- [`get_db()`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L48): Generator yielding a synchronous `Session`, closing it upon request termination.
- [`async_engine`](file:///f:/Projects/fastapi_bookings/app/db/async_session.py#L43): Asynchronous SQLAlchemy engine bound to `settings.async_database_url`.
- [`AsyncSessionLocal`](file:///f:/Projects/fastapi_bookings/app/db/async_session.py#L46): Factory for scoped asynchronous database sessions (`expire_on_commit=False`).
- [`get_async_db()`](file:///f:/Projects/fastapi_bookings/app/db/async_session.py#L55): Async generator yielding an `AsyncSession`, rolling back on unhandled exceptions and closing upon completion.
- [`async_session_scope()`](file:///f:/Projects/fastapi_bookings/app/db/async_session.py#L72): Asynchronous context manager for background tasks outside HTTP request lifecycles.

---

## 3. Setup, Configuration & Dependencies

### Dependencies
- `sqlalchemy>=2.0.0`: Core relational ORM and SQL toolkit.
- `psycopg2-binary>=2.9.9`: Synchronous PostgreSQL driver.
- `asyncpg>=0.29.0`: High-performance asynchronous PostgreSQL driver.
- `aiosqlite>=0.20.0`: Asynchronous SQLite driver for offline unit testing.
- `pgvector>=0.2.5`: PostgreSQL vector extension type bindings for SQLAlchemy.

### Configuration Parameters (`app/core/config.py`)
| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./fastapi_bookings.db` | Primary relational connection URL (sync driver) |
| `ASYNC_DATABASE_URL` | `None` (derived) | Derived via `settings.async_database_url` (translates `postgresql://` -> `postgresql+asyncpg://`, `sqlite:///` -> `sqlite+aiosqlite:///`) |
| `DB_POOL_SIZE` | `10` | Base PostgreSQL connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Maximum overflow connections allowed above `DB_POOL_SIZE` |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait before timing out on connection pool exhaustion |
| `DB_POOL_RECYCLE` | `1800` | Seconds before recycling connections to avoid backend timeout disconnects (30m) |

---

## 4. Core Workflows & Contracts

### 4.1 Synchronous Session Injection Pattern
Used across standard CRUD routers and admin endpoints:
```python
@router.get("/services")
def list_services(db: Session = Depends(get_db), current_tenant = Depends(get_current_tenant)):
    return db.query(Service).filter(Service.tenant_id == current_tenant.id).all()
```

### 4.2 Asynchronous Session Injection Pattern
Used in async-heavy routes, LangGraph dialogue engines, and async streaming:
```python
@router.post("/turns")
async def handle_turn(payload: TurnPayload, db: AsyncSession = Depends(get_async_db)):
    result = await process_dialogue_turn(payload, db=db)
    return result
```

### 4.3 Background Worker Scoped Session Pattern
Used by outbox workers, projection workers, and curator polling loops:
```python
async with async_session_scope() as session:
    stmt = select(LearningEvent).where(LearningEvent.status == "pending")
    events = (await session.execute(stmt)).scalars().all()
```

---

## 5. Data Safety & Isolation

- **Connection Pool Safety**: `pool_pre_ping=True` ensures stale connections dropped by network firewalls or database restarts are evicted before issuing queries.
- **Fail-Closed Cleanup**: Both `get_db` and `get_async_db` wrap session lifecycles in `try ... finally` blocks to prevent connection leaks into connection pools.
- **Savepoint Isolation in Testing**: Test suites in `tests/conftest.py` wrap every test in an isolated connection transaction with nested savepoints (`connection.begin_nested()`), rolling back changes immediately upon test completion.
- **Production Guardrail**: `app/core/config.py` enforces `if self.DATABASE_URL.startswith("sqlite"): raise ValueError("SQLite database is not allowed in production environment")`.

---

## 6. Known Issues, Edge Cases & Outstanding Work

1. **SQLite Pessimistic Locking Inefficacy**: SQLite does not support row-level pessimistic locking (`with_for_update()`). In SQLite dev/test environments, `FOR UPDATE` and `FOR UPDATE SKIP LOCKED` are ignored as no-ops. High-concurrency worker tests and slot allocation audits require PostgreSQL.
2. **Missing pgvector Native Support in SQLite**: SQLite lacks native vector distance operators (`<=>`, `<->`). When running under SQLite, semantic vector ranking must be computed in-memory via Python (`_cosine_similarity` / `compute_cosine_distance`), whereas PostgreSQL executes native C-level vector distance with HNSW indexing.
3. **Driver Prefix Translation**: `settings.async_database_url` replaces `postgresql://` and `postgresql+psycopg2://` with `postgresql+asyncpg://`. If specialized query-string arguments incompatible with `asyncpg` (e.g. `sslmode=require` vs `ssl=true`) are present in `DATABASE_URL`, connection initialization may fail.
4. **pgvector HNSW Cosine Indexing**: Migration `j1k2m3n4p5q6` enables the `vector` extension and adds the HNSW cosine index `ix_curated_memories_embedding_hnsw` (`USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`) to `curated_memories`, replacing sequential table scans with fast sub-millisecond approximate nearest neighbor retrieval in production PostgreSQL.

---

## 7. Verification & Testing Commands

```powershell
# Verify connection pool and database connectivity
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); from app.db.database import engine; print(engine.connect().execute(__import__('sqlalchemy').text('SELECT 1')).scalar())"

# Verify async database connectivity
.\.venv\Scripts\python.exe -c "import sys, asyncio; sys.path.insert(0, '.'); from app.db.async_session import async_engine; asyncio.run((lambda: async_engine.connect())())"

# Execute database parity verification between primary (5432) and dedicated test database (5433)
.\.venv\Scripts\python.exe scripts/verify_db_parity.py

# Run SQLite and PostgreSQL test suite
.\.venv\Scripts\python.exe -m pytest tests/test_concurrency.py tests/test_track1_vector_audit.py -q
```
