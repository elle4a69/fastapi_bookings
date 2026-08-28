# Booking Holds Retirement & Architecture Remediation Plan

**Date:** 2026-08-29  
**Repository:** `F:\\Projects\\fastapi_bookings`  
**Branch:** `telemetry/observability-baseline`  
**Target Architecture:** First-Confirmed-Submission-Wins (Atomic Database Concurrency)

---

## 1. Executive Summary

This document establishes the comprehensive audit, inventory, and migration plan to completely remove temporary booking holds from **FastAPI Bookings**. In their place, we transition the application to an atomic, database-enforced **"first confirmed booking submission wins"** concurrency model.

### Key Architectural Tenets:
1. **Zero Temporary Holds:** Viewing, selecting, or initiating a booking step does not lock or reserve time.
2. **Live Calendar Availability:** Slot availability is derived strictly from real-time database queries, not cached or speculative reservations.
3. **Atomic Booking Creation:** The final booking creation transaction performs a row-locked/atomic conflict check with mandatory 15-minute buffers and 30-minute lead time.
4. **Immediate 409 Conflict Handling:** If a competing customer books the slot milliseconds prior, the losing request receives `HTTP 409 Conflict` and must pick another live available slot.
5. **Passive Waitlist Safety:** Waitlist entries serve strictly as passive customer interest logs; automatic background hold creation and waitlist auto-promotion to holds are retired.

---

## 2. Complete Inventory of Hold-Related Dependencies

### A. Database Models & Schema
* `app/models/hold.py`: Defines `HoldStatus` (`PENDING`, `EXPIRED`, `CONFIRMED`) and `Hold` model with unique partial index `uq_pending_holds`.
* `app/models/__init__.py`: Exports `Hold` and `HoldStatus`.
* `app/models/waitlist.py`: Contains `WaitlistEntry` with status transitions that previously triggered hold generation.

### B. Schemas
* `app/schemas/hold.py`: Defines `HoldBase`, `HoldCreate`, `HoldOut`, `HoldConfirm`, `HoldListResponse`.
* `app/schemas/__init__.py`: Exports hold schemas.

### C. API Routers
* `app/api/routers/holds.py`:
  - `POST /api/public/holds`: Creates temporary slot hold.
  - `POST /api/public/holds/{hold_id}/confirm`: Converts hold to booking.
  - `DELETE /api/public/holds/{hold_id}`: Releases hold.
  - `GET /api/admin/holds`: Lists tenant holds.
  - `DELETE /api/admin/holds/{hold_id}`: Admin hold cancellation.
* `app/api/routers/__init__.py`: Router registration.
* `app/main.py`: Includes `holds.router`.
* `app/api/routers/diagnostics.py`: Health diagnostics checking `holds: bool`.
* `app/api/routers/bookings.py`: Line 237 calls `promote_waitlist` on booking cancellation.

### D. Services & Background Jobs
* `app/services/hold_service.py`:
  - `create_hold`: Inserts temporary hold record.
  - `expire_holds`: Expired hold transitioner.
  - `promote_waitlist`: Autonomously searches slots and spawns holds for waitlist entries.
* `app/services/scheduling_service.py`:
  - Imports and re-exports `create_hold`, `expire_holds`, `promote_waitlist`.
  - Queries `active_holds` in `compute_availability` to block slot display.
* `app/services/scheduling_utils.py`:
  - `check_slot_overlaps` checks `active_holds`.
* `app/services/outbox_worker.py`:
  - Handled `hold.*` event types.

### E. Frontend Surfaces
* Public booking page (`frontend/src/pages/public/booking-page.tsx`): Directly creates bookings via `POST /api/public/bookings` (no frontend hold tokens or countdown timers were in active use).

### F. Test Suites
* `tests/test_concurrency.py`: Contains `test_concurrent_holds_same_slot` (`xfail`/`xpass`) and `test_concurrent_hold_confirmation`.
* `tests/test_audit_fixes.py`: Contains `test_hold_timezone_and_serialization` and `test_auto_promotion_on_cancellation`.
* `tests/test_scheduling_edge_cases.py`: Contains `test_cascading_waitlist_promotions` asserting hold creation.
* `tests/test_numeric_id_bounds.py`: Tested bounds on `DELETE /api/public/holds/{id}`.
* `tests/test_fuzzer.py`: Schemathesis fuzzer test index including `/api/public/holds` routes.

---

## 3. Proposed Removal and Transition Order

1. **Step 1: Implement Atomic First-Submit-Wins in `public_bookings.py` and `bookings.py`:**
   - In single database transaction with row-level locking (`with_for_update()`) on candidate Provider.
   - Run slot overlap check against confirmed active bookings (including 15-min buffers + 30-min lead time).
   - Enforce resource allocation and idempotency key uniqueness.
   - Return structured `409 CONFLICT` when slot is taken.
2. **Step 2: Clean Up Availability Calculation:**
   - Update `scheduling_service.py` and `scheduling_utils.py` to remove `active_holds` dependency from `compute_availability` and `check_slot_overlaps`.
3. **Step 3: Retire Hold Service & Routes:**
   - Remove `app/api/routers/holds.py`, `app/schemas/hold.py`, `app/services/hold_service.py`, and `app/models/hold.py`.
   - Remove hold references in `app/main.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/api/routers/diagnostics.py`, and `app/services/outbox_worker.py`.
4. **Step 4: Retire Automatic Waitlist Promotion:**
   - Waitlist entries remain passive data records. Remove automatic promotion to holds from cancellation hooks.
5. **Step 5: Replace Test Cases:**
   - Replace hold tests in `test_concurrency.py`, `test_audit_fixes.py`, and `test_scheduling_edge_cases.py` with rigorous first-submit-wins concurrency tests.
   - Remove all `xfail` decorators on booking races.

---

## 4. Affected Files Allowlist

| Component | Target File | Action |
|---|---|---|
| Routing | `app/api/routers/holds.py` | DELETE |
| Routing | `app/api/routers/public_bookings.py` | MODIFY (atomic conflict check + buffers + 409) |
| Routing | `app/api/routers/bookings.py` | MODIFY (remove waitlist auto-promotion, add atomic check) |
| Routing | `app/api/routers/diagnostics.py` | MODIFY (remove holds check) |
| Routing | `app/api/routers/__init__.py` | MODIFY (remove holds export) |
| Core | `app/main.py` | MODIFY (remove holds router) |
| Models | `app/models/hold.py` | DELETE |
| Models | `app/models/__init__.py` | MODIFY (remove Hold exports) |
| Schemas | `app/schemas/hold.py` | DELETE |
| Schemas | `app/schemas/__init__.py` | MODIFY (remove hold schemas) |
| Services | `app/services/hold_service.py` | DELETE |
| Services | `app/services/scheduling_service.py` | MODIFY (remove hold imports & active_holds queries) |
| Services | `app/services/scheduling_utils.py` | MODIFY (remove active_holds parameter) |
| Services | `app/services/outbox_worker.py` | MODIFY (remove hold event prefix) |
| Tests | `tests/test_concurrency.py` | MODIFY (replace hold races with atomic booking tests) |
| Tests | `tests/test_audit_fixes.py` | MODIFY (remove hold tests) |
| Tests | `tests/test_scheduling_edge_cases.py` | MODIFY (update waitlist tests) |
| Tests | `tests/test_numeric_id_bounds.py` | MODIFY (update route parameters) |
| Framework | All routers & schemas | MODIFY (Pydantic v2 `model_dump`, `ConfigDict`, `model_validate`) |
| Frontend | `frontend/src/*` | MODIFY (fix 51 lint warnings, add lazy route code-splitting) |
