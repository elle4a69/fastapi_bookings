# FastAPI Bookings — Application Module Index

This document provides a master catalog of all modules, directories, domain boundaries, and their active operational status across the **FastAPI Bookings** codebase.

---

## 1. Purpose & Scope

The Module Index acts as an authoritative directory for engineers and autonomous agents to locate functional subsystems, identify file ownership, trace integration points, and inspect technical debt or operational readiness without searching ad-hoc transcripts.

---

## 2. Master Module Inventory Table

| Path | Domain / Responsibility | Primary Files / Entrypoint | Operational Status | Documentation Link |
| :--- | :--- | :--- | :--- | :--- |
| `app/api/routers/` | HTTP REST API Endpoints | [__init__.py](file:///F:/Projects/fastapi_bookings/app/api/routers/__init__.py), [bookings.py](file:///F:/Projects/fastapi_bookings/app/api/routers/bookings.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/api/routers/README.md) |
| `app/api/` | Dependency Injection & Auth Boundaries | [deps.py](file:///F:/Projects/fastapi_bookings/app/api/deps.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/api/routers/README.md) |
| `app/core/` | Configuration, Security, Telemetry | [config.py](file:///F:/Projects/fastapi_bookings/app/core/config.py), [telemetry.py](file:///F:/Projects/fastapi_bookings/app/core/telemetry.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/core/README.md) |
| `app/db/` | Database Sessions & Engine | [database.py](file:///F:/Projects/fastapi_bookings/app/db/database.py) | **Active / Production** | [docs/ARCHITECTURE.md](file:///F:/Projects/fastapi_bookings/docs/ARCHITECTURE.md) |
| `app/models/` | SQLAlchemy ORM Models | [__init__.py](file:///F:/Projects/fastapi_bookings/app/models/__init__.py), [booking.py](file:///F:/Projects/fastapi_bookings/app/models/booking.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/models/README.md) |
| `app/schemas/` | Pydantic Request & Response Models | [booking.py](file:///F:/Projects/fastapi_bookings/app/schemas/booking.py) | **Active / Production** | [app/api/routers/README.md](file:///F:/Projects/fastapi_bookings/app/api/routers/README.md) |
| `app/services/sms/` | Autonomous SMS Dialogue Engine | [ai_orchestrator.py](file:///F:/Projects/fastapi_bookings/app/services/sms/ai_orchestrator.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/sms/README.md) |
| `app/services/sms/transports/` | Mobile Carrier Adapters (ClickSend) | [mobilemessage.py](file:///F:/Projects/fastapi_bookings/app/services/sms/transports/mobilemessage.py), [fake.py](file:///F:/Projects/fastapi_bookings/app/services/sms/transports/fake.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/sms/README.md) |
| `app/services/scheduling/` | Cal.com Headless Integration Adapter | [calcom_adapter.py](file:///F:/Projects/fastapi_bookings/app/services/scheduling/calcom_adapter.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/scheduling/README.md) |
| `app/services/` (Root) | Core Scheduling & Slot Allocation | [slot_allocation_service.py](file:///F:/Projects/fastapi_bookings/app/services/slot_allocation_service.py), [outbox_worker.py](file:///F:/Projects/fastapi_bookings/app/services/outbox_worker.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/scheduling/README.md) |
| `app/services/resident_agent/` | Codex Autonomous Resident Sentinel | [engine.py](file:///F:/Projects/fastapi_bookings/app/services/resident_agent/engine.py), [sentinel_scheduler.py](file:///F:/Projects/fastapi_bookings/app/services/resident_agent/sentinel_scheduler.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/resident_agent/README.md) |
| `app/services/curation/` | Semantic Memory Curator & PII Scrubber | [memory_curator.py](file:///F:/Projects/fastapi_bookings/app/services/curation/memory_curator.py), [pii_scrubber.py](file:///F:/Projects/fastapi_bookings/app/services/curation/pii_scrubber.py) | **Active / Production** | [README.md](file:///F:/Projects/fastapi_bookings/app/services/curation/README.md) |
| `scripts/` | Data Seeding, Chatwoot Sync, Release Gates | [seed_clean_numbered_data.py](file:///F:/Projects/fastapi_bookings/scripts/seed_clean_numbered_data.py), [verify_all_release_gates.py](file:///F:/Projects/fastapi_bookings/scripts/verify_all_release_gates.py) | **Active / Operational** | [README.md](file:///F:/Projects/fastapi_bookings/scripts/README.md) |
| `tests/` | Pytest Test Suites & Conftest | [conftest.py](file:///F:/Projects/fastapi_bookings/tests/conftest.py), [test_concurrency.py](file:///F:/Projects/fastapi_bookings/tests/test_concurrency.py) | **Active / Automated CI** | [README.md](file:///F:/Projects/fastapi_bookings/tests/README.md) |
| `frontend/` | React/Vite SPA & Booking Widget | [App.tsx](file:///F:/Projects/fastapi_bookings/frontend/src/App.tsx), [main.tsx](file:///F:/Projects/fastapi_bookings/frontend/src/main.tsx) | **Active / Production** | [frontend/README.md](file:///F:/Projects/fastapi_bookings/frontend/README.md) |
| `alembic/` | Schema Migrations | [env.py](file:///F:/Projects/fastapi_bookings/alembic/env.py), [versions/](file:///F:/Projects/fastapi_bookings/alembic/versions/) | **Active / Production** | [docs/ARCHITECTURE.md](file:///F:/Projects/fastapi_bookings/docs/ARCHITECTURE.md) |
| `contracts/` | OpenAPI Spec & Type Generators | [openapi.json](file:///F:/Projects/fastapi_bookings/openapi.json) | **Active / Supporting** | [docs/ARCHITECTURE.md](file:///F:/Projects/fastapi_bookings/docs/ARCHITECTURE.md) |

---

## 3. Subsystem Domain Breakdowns

### 3.1 HTTP & API Gateway (`app/api/routers/`)
Handles intake of external HTTP traffic, JWT token authentication, input validation via Pydantic schemas, and role gatekeeping:
- Public widget booking endpoints (`/api/public/*`)
- Client portal management (`/api/client-portal/*`)
- Staff & administrative control (`/api/admin/*`)
- Webhook ingress (ClickSend SMS, Stripe, Chatwoot AgentBot)

### 3.2 Autonomous Conversation Engine (`app/services/sms/`)
Orchestrates AI-driven appointment dialogues over SMS:
- Inbound webhook processing with signature validation and deduplication receipts
- Turn consolidation and 5-second burst debouncing
- OpenAI GPT-4o function calling for live bookings with deterministic local rule fallbacks
- Transactional outbox pattern for SMS delivery
- Bi-directional Chatwoot customer sync and human takeover toggle

### 3.3 Scheduling & Slot Allocation Engine (`app/services/scheduling/`)
Guarantees double-booking prevention and scheduling integrity:
- Provider schedule matrices and blackout rules
- 15-minute discrete slot allocation (`BookingSlotAllocation`)
- Database-level unique constraint collision detection (`uq_provider_slot_allocation`)
- Cal.com headless integration adapter for external calendar sync

### 3.4 Resident Autonomous Sentinel (`app/services/resident_agent/`)
Self-healing, continuous monitoring agent running in the FastAPI lifespan:
- Static codebase and git worktree audits
- Telemetry sentinel computing real-time system health score
- Stress fuzzer evaluating race conditions and slot allocation integrity
- Automated remediation planning and safe fix execution

### 3.5 Semantic Memory Curation (`app/services/curation/`)
Long-term tenant knowledge base:
- Post-conversation transcript analysis (Mem0 pattern: `ADD`, `UPDATE`, `DELETE`, `NOOP`)
- Strict PII scrubbing (phone, email, credit card, Australian street addresses)
- Multi-tenant pgvector semantic indexing

---

## 4. Setup, Configuration & Dependencies

The modules across the application are configured globally via [app/core/config.py](file:///F:/Projects/fastapi_bookings/app/core/config.py) (`Settings`). Subsystems declare explicit dependencies:
- **Database**: PostgreSQL 15+ or SQLite 3.38+ via SQLAlchemy.
- **SMS Gateway**: ClickSend / MobileMessage API credentials.
- **AI Engine**: OpenAI API key (`OPENAI_API_KEY`) for GPT-4o dialogue.
- **Support Inbox**: Chatwoot API base URL and access token.
- **Observability**: OpenTelemetry OTLP endpoint (SigNoz).

---

## 5. Data Safety & Isolation Matrix

| Subsystem | Tenant Scoping | PII Scrubbing | Concurrency Safety |
| :--- | :--- | :--- | :--- |
| `app/api/routers/` | Subdomain + Header `tenant_id` | Excluded from logs | Path bounds check (`DatabaseId`) |
| `app/services/sms/` | Isolated by `tenant_id` and `sms_account_id` | Filtered in traces | Inbound deduplication receipts |
| `app/services/scheduling/` | Scoped by `tenant_id` & `provider_id` | N/A | Unique composite slot constraints |
| `app/services/curation/` | Strict `tenant_id` memory partition | Regex scrubbers before embedding | Vector isolation per tenant |
| `app/core/telemetry.py` | Low-cardinality metadata only | Allowlist span filtering | Non-blocking async processors |

---

## 6. Known Technical Debt & Module Limitations

1. **SQLite Concurrency Limitation**: SQLite locks during concurrent transactions; full production concurrency testing must use PostgreSQL.
2. **Chatwoot Outbox Decoupling**: Chatwoot API network failures should queue transparently in `outbox_events` rather than synchronous retries in worker loops.
3. **Cal.com Dual-Write Conflict**: If Cal.com and FastAPI Bookings both accept concurrent appointments for an un-synced provider, local slot allocations win, but reconciliation webhooks must be audited.

---

## 7. Verification & Health Commands

Validate health across all modules:
```powershell
# Run full release gate verification suite
python scripts/verify_all_release_gates.py

# Verify module compilation
python -m compileall app/

# Run targeted domain tests
pytest tests/test_multi_tenancy.py tests/test_concurrency.py tests/test_sms_openai.py -v
```
