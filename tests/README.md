# Test Architecture & Verification Gates (`tests/`)

The `tests/` directory contains the automated test suites, fixtures, mock isolation wrappers, and release verification gates for **FastAPI Bookings**.

---

## 1. Purpose & Scope

The automated test framework owns:
- Verification of the core booking lifecycle, discrete 15-minute slot allocations, and double-booking collision prevention.
- Cal.com headless scheduling federation and event type synchronization.
- Website builder, draft saving, and live publishing regression tests.
- Autonomous SMS/MMS dialogue engine, debouncing, prompt hierarchy, and outbox delivery.
- Chatwoot webhook intake, contact mapping, and human takeover handshakes.
- Multi-tier role hierarchy (`owner`, `manager`, `provider`) and RBAC permissions.
- Client self-service portal, OTP authentication, and dispute lodging.
- Umbrella directory, geocoding fast-paths, and geo-radius Haversine calculation.
- OpenTelemetry telemetry pipelines, structural trace attributes, and PII redaction.
- Living documentation compliance verifiers and release gates (AGENTS.md Rule 10).

This module deliberately avoids making live external HTTP or SMS carrier calls during test execution, mutating live production databases, or persisting un-redacted customer PII in test fixtures.

---

## 2. Architecture & Key Files

```
tests/
├── conftest.py                          # Pytest fixtures, in-memory SQLite setup, socket blocking guards
├── test_booking.py                      # Booking domain logic, slot allocations, and state machines
├── test_concurrency.py                  # High-concurrency First-Submit-Wins collision tests
├── test_sms_foundation.py               # SMS account isolation, idempotency, timeline assembly
├── test_sms_chatwoot.py                 # Chatwoot sync bridge and webhook HMAC verification
├── test_sms_arrivals.py                 # Lobby arrival tokens, chime alerts, and deduplication
├── test_assistant_tools_and_prompts.py  # 10-tier prompt hierarchy and live tool server enforcement
├── test_knowledge_curator_safety.py     # Epistemic curator proposals, PII scrubbing, graph projection
├── test_client_portal.py                # Passwordless OTP, reschedule/cancellation, disputes
├── test_living_documentation.py         # Rule 10 compliance linter and documentation indexer tests
├── test_fuzzer.py                       # Schemathesis API schema contract fuzzer
└── README.md                            # Living documentation
```

### Key Test Files:
- [conftest.py](file:///f:/Projects/fastapi_bookings/tests/conftest.py): Global test configuration providing rollback database sessions, client fixtures (`TestClient`, `AsyncClient`), and socket-level network blocks.
- [test_concurrency.py](file:///f:/Projects/fastapi_bookings/tests/test_concurrency.py): Multi-threaded race condition tests verifying discrete slot reservation atomicity.
- [test_sms_foundation.py](file:///f:/Projects/fastapi_bookings/tests/test_sms_foundation.py): Comprehensive unit and integration tests for SMS dialogue debouncing, state machines, and account isolation.
- [test_living_documentation.py](file:///f:/Projects/fastapi_bookings/tests/test_living_documentation.py): Validates documentation parser, stub detector, manifest generator, and SQLite FTS5 search index.
- [test_telemetry_redaction.py](file:///f:/Projects/fastapi_bookings/tests/test_telemetry_redaction.py): Regression suite ensuring 100% PII redaction across telemetry spans and metrics.

---

## 3. Setup, Configuration & Dependencies

### Prerequisites & Test Runner
- **Test Framework**: `pytest` (v8.3+) with plugins `pytest-asyncio`, `pytest-cov`, `pytest-subtests`.
- **Database Backend**: Isolated in-memory SQLite databases (`sqlite:///:memory:`) configured with transactional rollback after each test case.
- **Environment Flags**:
  - `OTEL_SDK_DISABLED=true`: Prevents unwanted background telemetry export during local test runs.
  - `APP_ENV=test`: Sets testing security profiles and predictable seed constants.

---

## 4. Core Workflows & Contracts

### 4.1 Pytest Fixture Lifecycle & Session Isolation
1. **Engine Setup**: `conftest.py` initializes an in-memory SQLite schema using SQLAlchemy `Base.metadata.create_all()`.
2. **Session Fixture**: Yields a scoped database session. After test completion, the session is cleanly closed and rolled back.
3. **HTTP Client Fixture**: Provides FastAPI `TestClient` pre-configured with default tenant headers (`X-Tenant: simplydemo`).

### 4.2 Network Isolation Guard (Socket Blocker)
- During test execution, standard socket connections to external hosts (OpenAI, ClickSend, Chatwoot, Cal.com) are intercepted and blocked by `conftest.py`.
- Any unexpected live network call immediately triggers a test failure, guaranteeing 100% offline determinism and eliminating flaky test runs.

---

## 5. Data Safety & Isolation

- **Synthetic Phone & Email Constants**: All test cases use reserved synthetic numbers (`0411000001`–`0411000005`) and test email domains (`@example.com`).
- **In-Memory Volatility**: Tests never persist data to disk or write to production database files (`fastapi_bookings.db`).
- **PII Scrubbing Audits**: Telemetry and curator tests explicitly assert that credit card patterns, phone numbers, and street addresses are replaced with `<REDACTED_*>` tokens before assertions complete.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Async Fixture Event Loop Deprecation**: Future versions of `pytest-asyncio` default loop scope to function scope; explicit `asyncio_default_fixture_loop_scope = "function"` is recommended in `pytest.ini`.
- **Schemathesis Fuzzer Execution Time**: `test_fuzzer.py` generates hundreds of randomized API permutations and is excluded from fast gate checks via `--ignore=tests/test_fuzzer.py`.
- **SQLite Concurrency Simulation**: In-memory SQLite uses database-level locks rather than row-level locking; concurrency tests simulate multi-worker behavior using transactional rollback checks.

---

## 7. Verification & Testing Commands

To run the automated test suites:

```powershell
# 1. Run all unit and integration tests (excluding heavy fuzzer)
python -m pytest tests/ --ignore=tests/test_fuzzer.py -v

# 2. Run concurrency slot allocation tests
python -m pytest tests/test_concurrency.py -v

# 3. Run living documentation compliance test suite
python -m pytest tests/test_living_documentation.py -v

# 4. Run test suite with code coverage analysis
python -m pytest --cov=app tests/
```
