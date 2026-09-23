# Application Services

## Purpose & Scope

The services package contains FastAPI Bookings application and domain services.
`booking_creation_service.py` is the authoritative final-write boundary for new
public bookings. It validates live FastAPI Bookings data and atomically creates
a pending booking with its slot allocations, resource allocations, structural
audit record, and outbox event.

This service does not send SMS, call AI models, access Cal.com or another
calendar, create conversational holds, confirm bookings, or implement the
admin and booking-form entry points. FastAPI Bookings remains the only booking
and availability authority.

## Architecture & Key Files

- `booking_creation_service.py`: tenant-scoped client/entity resolution, exact
  slot revalidation, and the atomic booking command.
- `scheduling_service.py`: authoritative availability computation, including
  provider schedules, blocked/reserved time, buffers, relationships, and
  resources.
- `booking_relationship_resolver.py`: tenant-scoped compatibility between
  services, providers, and locations.
- `slot_allocation_service.py`: database-enforced first-submit-wins slot rows.
- `resource_service.py`: resource availability and booking allocations.
- `outbox_service.py`: transactional structural events for downstream work.

The public `POST /api/public/bookings` route delegates to
`create_authoritative_booking`. The router owns HTTP dependency resolution and
maps `BookingCommandError` to the existing error envelope. The command owns a
nested savepoint and flushes its rows; the public route owns the outer commit
and rollback. Other callers must likewise own their outer transaction.

## Setup, Configuration & Dependencies

No new environment variables or external services are required. Keyed booking
commands require the existing server-side `SECRET_KEY` to be non-default and
at least 32 characters. Blank, short, surrounding-whitespace, and known
repository placeholder values fail closed before replay lookup or mutation.
Validation compares a trimmed, case-folded value only to identify unsafe
configuration; an accepted secret is never normalized before HMAC derivation.
The command uses the configured SQLAlchemy session and these tables:

- `tenants`, `clients`, `services`, `providers`, `locations` and relationship
  tables;
- provider workdays/special days, blocked time, and reserved time;
- `bookings`, `booking_command_receipts`, `booking_slot_allocations`, and
  resource allocation tables;
- `audit_logs` and `outbox_events`.

Migration `b6c2d4e8f0a1` must be applied after the committed
`d7e8f9a0b1c2` head. It creates the internal receipt table, enforces its
composite tenant/booking foreign key, and replaces global booking-key
uniqueness with nullable tenant-scoped uniqueness. SQL unique constraints
permit multiple `NULL` keys while rejecting duplicate non-null keys in one
tenant.

## Core Workflows & Contracts

`create_authoritative_booking(db, tenant_id=..., command=BookingCreate(...))`
performs the following ordered workflow:

1. For a keyed command, require the configured server secret and query only the
   exact `(tenant_id, idempotency_key)` internal receipt. Authenticate the
   versioned canonical command with a context-derived HMAC-SHA256 and return
   only the receipt's exact tenant-linked booking. Replay does not re-run
   mutable provider, service, location, or client policy. Missing, malformed,
   ambiguous, legacy, mismatched, or unlinked receipts fail closed.
2. Resolve an active service and provider inside the explicit tenant, lock the
   provider row where supported, and enforce service/provider/location pairs.
3. Normalize the start to UTC, derive the end from the stored service duration,
   and reject a caller-supplied interval that does not match.
4. Resolve an active tenant client. Every supplied ID, canonical phone, and
   trimmed/lowercased email must identify the same single tenant client.
   Conflicting or duplicate contact matches fail closed before any command row
   is created, including ambiguity between active and inactive records.
   Restricted clients retain the existing 403 contract.
5. Recompute a full authoritative availability window and require an exact
   provider/start/end match. This includes schedules, special days, active
   bookings, blocks, reservations, buffers, relationships, and resources.
6. Apply the command's effective minimum 15-minute buffers consistently during
   final overlap validation and persisted slot allocation.
7. Create the pending booking and, for a keyed command, insert and flush its
   internal receipt before allocations or events. Tenant/key uniqueness on the
   booking serializes concurrent first use; the separately unique receipt is
   the replay authority. A losing savepoint is fully rolled back before the
   exact winner receipt is authenticated.
8. Lock eligible shared resource rows in deterministic order where the database
   supports row locks, recompute overlapping capacity under those locks, and
   allocate only tenant/type/location-scoped candidates. A booking without a
   location can use global resources only.
9. Create a `pending` booking, slot/resource allocations, `booking.created`
   outbox event, and structural audit record inside one nested savepoint. The
   outbox allowlist is `id`, `provider_id`, `service_id`, `start_time`,
   `end_time`, and `status`; it contains no client identifier or contact data.
   The audit details contain only status and source. Audit records never carry
   or control the replay HMAC. The caller commits all rows with its surrounding
   unit of work.

The public method, path, tenant dependency, and error envelope remain stable.
The unauthenticated route uses `PublicBookingCreate`, whose closed OpenAPI
schema does not include `client_id`. The route rejects any unknown input with a
generic, non-reflecting HTTP 422 before command construction. It requires
contact-based intake and returns a fully materialized `PublicBookingReceipt`
that omits client/contact data, notes, and idempotency keys. The receipt is
validated before the single outer commit; no database read or refresh occurs
after a successful commit. Other intentional corrections use existing
validation/conflict semantics:

- an interval that differs from the authoritative service duration returns
  HTTP 400;
- a requested interval that is not an exact currently available slot returns
  HTTP 409.

The public request schema retains the booking page's established `addon_ids`
and `product_ids` list fields so empty selections remain compatible. Any
non-empty selection is rejected with the same generic, non-reflecting HTTP 422
used for unsupported public fields before command construction. The command
does not partially apply commercial selections.

Idempotency keys are opaque values of 1-128 characters. Internal whitespace
and punctuation are preserved exactly, while blank or edge-whitespace values
receive the generic, non-reflecting HTTP 422 contract before command
construction.

The returned status is the actual stored `pending` status. This command never
claims a booking is confirmed.

## Data Safety & Isolation

- Every client, service, provider, and location lookup includes the explicit
  tenant boundary.
- Compatibility checks use tenant-scoped relationship rows.
- Idempotent replay is protected by database uniqueness on
  `(tenant_id, idempotency_key)` in both bookings and command receipts. The
  receipt has a database-enforced composite foreign key to the booking's exact
  tenant and ID. The canonical request, HMAC key, HMAC input, and HMAC output
  are never logged, returned, placed in audit data, or exposed by an API.
- Command failures roll back only command-created work to a savepoint. They do
  not commit or roll back unrelated work already owned by the caller.
- The public route commits only after the command returns and rolls back its
  outer transaction on every mapped or unexpected failure.
- Audit and outbox payloads use the explicit structural allowlists above. Logs
  contain no customer identity, contact data, notes, request body, HMAC,
  idempotency key, or rejected unknown-field value. Public unknown-field errors
  do not echo the submitted field name or value.
- Availability checks and tests perform no external network calls.

## Known Issues, Edge Cases & Outstanding Work

- The migration intentionally does not derive receipts from legacy `AuditLog`
  rows. Existing keyed bookings without an internal receipt fail closed with
  HTTP 409 and require an explicit, separately approved reconciliation policy.
- Receipt HMACs use the existing `SECRET_KEY`. Receipts store a fingerprint
  version but no HMAC key ID or historical key ring. Rotating that key therefore
  invalidates replay authentication for existing receipts unless a versioned
  key-rotation migration is performed first.
- Migration `b6c2d4e8f0a1` is based only on committed parent `d7e8f9a0b1c2`.
  The untracked unsafe `e8` migration in the dirty main worktree was not read,
  modified, deleted, or used. Its lineage must be resolved before integration
  or deployment. An online downgrade performs a read-only duplicate-key
  preflight before any DDL and aborts generically if different tenants have
  used the same non-null key, preserving receipt authority and the upgraded
  constraints. Offline downgrade generation is deliberately rejected before
  emitting destructive SQL because it cannot execute that data preflight.
- The admin booking and configurable booking-form routes have not yet been
  migrated to this command. They must be consolidated in a separate parity-
  tested task.
- Non-empty public add-on and product selections are rejected until their
  authoritative compatibility, price, duration, inventory, and booking linkage
  can be implemented together in the booking-form parity task.
- Client phone canonicalization has no database column or tenant-scoped unique
  constraint. Existing formatted values are compared in application code;
  concurrent first-time client creation can still produce duplicate clients.
- Availability currently follows the scheduling engine's UTC discipline.
  Customer-facing timezone display policy remains a separate product decision.
- Availability discovery and the final command do not yet share one effective-
  buffer helper. A service configured with zero buffers can advertise an
  adjacent slot that the command correctly rejects under its minimum 15-minute
  safety policy. A strict expected-failure regression records this mismatch;
  changing the shared discovery contract requires a separate scheduling task.
- Shared-resource row locking is compiled and unit-tested for PostgreSQL, and
  sequential two-provider/capacity-one behavior is covered. SQLite ignores
  `FOR UPDATE`. Receipt and booking tenant/key uniqueness, composite receipt
  linkage, synthetic loser rollback, and PostgreSQL DDL are tested, but a
  genuine multi-session PostgreSQL booking race still requires an integration
  environment. Writers that bypass this command remain unsupported.

## Verification & Testing Commands

Run from a directory outside the repository to avoid local configuration or
cache side effects:

```powershell
$env:PYTHONPATH='F:\Projects\fastapi_bookings-authoritative-booking'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'F:\Projects\fastapi_bookings\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_booking_command_receipts.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_booking_creation_service.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_booking_policies_remediation.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_concurrency.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_scheduling_constraints.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_scheduling_edge_cases.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_scheduling_intervals.py'
```

The focused suite uses labelled synthetic tenants, clients, providers,
services, schedules, locations, resources, and booking commands. It must never
send SMS, call external booking providers, or create production data.
The tests named `sequential` exercise deterministic replay/contention behavior;
they do not claim to be concurrent database race tests.
Validation-boundary integration is verified on its separately reviewed branch
and is not part of this booking-module command.
