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
maps `BookingCommandError` to the existing error envelope; the service owns the
database transaction.

## Setup, Configuration & Dependencies

No new environment variables or external services are required. The command
uses the configured SQLAlchemy session and these existing tables:

- `tenants`, `clients`, `services`, `providers`, `locations` and relationship
  tables;
- provider workdays/special days, blocked time, and reserved time;
- `bookings`, `booking_slot_allocations`, and resource allocation tables;
- `audit_logs`, `outbox_events`, and configured webhook-delivery snapshots.

Schema migrations must already include the existing slot-allocation and outbox
safety revisions. This delivery intentionally adds no migration.

## Core Workflows & Contracts

`create_authoritative_booking(db, tenant_id=..., command=BookingCreate(...))`
performs the following ordered workflow:

1. Return an existing booking for a same-tenant idempotency replay without
   creating another client, allocation, event, or audit row.
2. Fail closed before mutation if the globally unique database key is already
   owned by another tenant.
3. Resolve an active service and provider inside the explicit tenant, lock the
   provider row where supported, and enforce service/provider/location pairs.
4. Normalize the start to UTC, derive the end from the stored service duration,
   and reject a caller-supplied interval that does not match.
5. Resolve the tenant client. Supplied phone numbers are canonicalized to an
   E.164-style digit string; existing formatted numbers are compared by their
   canonical value. Restricted clients fail with the existing 403 contract.
6. Recompute a full authoritative availability window and require an exact
   provider/start/end match. This includes schedules, special days, active
   bookings, blocks, reservations, buffers, relationships, and resources.
7. Create a `pending` booking, durable slot allocations, resource allocations,
   `booking.created` outbox event, and structural audit record in one commit.

The public request and response schemas, method, path, tenant dependency, and
error envelope are unchanged. Two intentional corrections use existing
validation/conflict semantics:

- an interval that differs from the authoritative service duration returns
  HTTP 400;
- a requested interval that is not an exact currently available slot returns
  HTTP 409.

The returned status is the actual stored `pending` status. This command never
claims a booking is confirmed.

## Data Safety & Isolation

- Every client, service, provider, and location lookup includes the explicit
  tenant boundary.
- Compatibility checks use tenant-scoped relationship rows.
- Idempotent replay is resolved by `(tenant_id, idempotency_key)` at the
  application layer.
- Failures roll back new clients, bookings, slot/resource allocations, audits,
  outbox events, and webhook snapshots together.
- Audit and outbox payloads are structural. Logs contain no customer identity,
  contact data, notes, request body, or idempotency key.
- Availability checks and tests perform no external network calls.

## Known Issues, Edge Cases & Outstanding Work

- `bookings.idempotency_key` is still globally unique in the database. Until an
  approved migration replaces it with a nullable unique constraint on
  `(tenant_id, idempotency_key)`, different tenants cannot use the same key.
  The service detects that condition before mutation and returns HTTP 409.
- The admin booking and configurable booking-form routes have not yet been
  migrated to this command. They must be consolidated in a separate parity-
  tested task.
- Client phone canonicalization has no database column or tenant-scoped unique
  constraint. Existing formatted values are compared in application code;
  concurrent first-time client creation can still produce duplicate clients.
- Availability currently follows the scheduling engine's UTC discipline.
  Customer-facing timezone display policy remains a separate product decision.
- Idempotency keys do not yet persist a request fingerprint, so callers must
  treat a key as belonging to one immutable booking command.

## Verification & Testing Commands

Run from a directory outside the repository to avoid local configuration or
cache side effects:

```powershell
$env:PYTHONPATH='F:\Projects\fastapi_bookings-authoritative-booking'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'F:\Projects\fastapi_bookings\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_booking_creation_service.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_booking_policies_remediation.py' `
  'F:\Projects\fastapi_bookings-authoritative-booking\tests\test_concurrency.py'
```

The focused suite uses labelled synthetic tenants, clients, providers,
services, schedules, locations, resources, and booking commands. It must never
send SMS, call external booking providers, or create production data.
