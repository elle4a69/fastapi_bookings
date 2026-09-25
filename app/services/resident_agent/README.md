# Resident Autonomous Agent & Code Sentinel

## Purpose & Scope
The `app/services/resident_agent/` module provides persistent, autonomous codebase supervision, deep subsystem audits, telemetry health sentinels, and transaction integrity fuzzers for **FastAPI Bookings**.

Key responsibilities:
- Continuous scanning of repository integrity, route registrations, and schema boundaries.
- Live Server-Sent Events (SSE) telemetry broadcast to the admin control panel.
- Transactional race-condition stress fuzzing to verify zero-double-booking locking under concurrent load.
- Self-healing remediation strategies for detected anomalies.

---

## Architecture & Key Files

```
app/services/resident_agent/
├── sentinel.py          # Real-time health sentinel, metrics gathering & status aggregator
├── fuzzer.py            # High-concurrency race condition simulator (atomic slot allocation tester)
├── auditor.py           # Deep static and runtime audit runner across all subsystems
└── events.py            # Event dispatch and SSE connection manager
```

---

## Setup, Configuration & Dependencies
- **Routes Exposed**: `/api/admin/resident-agent/status`, `/api/admin/resident-agent/events`, `/api/admin/resident-agent/audit`, `/api/admin/resident-agent/fuzz-concurrency`.
- **Database Tables**: Uses `bookings`, `booking_slot_allocations`, and `providers` for transactional lock fuzzing.
- **Dependencies**: Uses `asyncio`, `SQLAlchemy`, and standard FastAPI background tasks.

---

## Core Workflows & Contracts

### 1. Deep Subsystem Audit Flow
1. Admin triggers audit via UI or `POST /api/admin/resident-agent/audit`.
2. `auditor.py` executes verification passes across:
   - Route registration and precedence.
   - PII redaction compliance in telemetry.
   - Database foreign key cascades and multi-tenant isolation.
   - Outbox queue drain health.
3. Results are stored in memory and streamed via SSE to the admin frontend.

### 2. Concurrency & Race-Condition Fuzzing
1. Client requests fuzzer execution with `concurrency_level` (10x–30x).
2. `fuzzer.py` generates concurrent coroutines targeting the exact same provider slot simultaneously.
3. Verifies that exactly one transaction succeeds while the rest are caught by atomic constraints (100% double-booking prevention).

---

## Data Safety, Multi-Tenancy & PII Isolation
- Fuzzing transactions run with isolated synthetic tenant labels (`fuzz_tenant_test`).
- All synthetic test bookings are rolled back or cleaned up immediately post-test.
- Zero customer PII or sensitive keys are logged in audit reports or emitted over SSE.

---

## Known Issues, Edge Cases & Outstanding Work
- Fuzzer requires database row-level locking (`SELECT ... FOR UPDATE`) or discrete slot allocations; SQLite file locks behave differently from PostgreSQL row-level locks under extreme concurrency.
- Future work: automated rollback of detected regression diffs via git worktrees.

---

## Verification & Testing Commands
```bash
# Run resident agent unit and integration tests
.venv\Scripts\python.exe -m pytest tests/test_resident_agent.py -v

# Run race-condition baseline verification
.venv\Scripts\python.exe -m pytest tests/test_gate1_gate3_baseline.py -v
```
