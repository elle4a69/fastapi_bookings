# Application Models

## Purpose & Scope

The models package defines the tenant-aware SQLAlchemy persistence boundary for
FastAPI Bookings. `BookingCommandReceipt` is an internal replay authority for
the authoritative booking command. It is not a customer record, audit event,
API resource, or reusable knowledge store.

## Architecture & Key Files

- `booking.py`: pending and active booking records plus tenant-scoped command
  key uniqueness.
- `booking_command_receipt.py`: one internal authenticated command receipt per
  keyed booking.
- `booking_slot_allocation.py`: provider/time allocation rows used for atomic
  slot contention.
- `resource.py`: shared-resource requirements and booking allocations.
- `audit.py`: operational audit evidence; it is deliberately not replay
  authority.
- `__init__.py`: registers models with SQLAlchemy metadata.

## Setup, Configuration & Dependencies

Alembic revision `b6c2d4e8f0a1`, whose committed parent is
`d7e8f9a0b1c2`, creates `booking_command_receipts`. It also replaces the
historical global booking-key index with nullable unique
`(tenant_id, idempotency_key)` constraints. PostgreSQL and SQLite allow more
than one `NULL` under these constraints; only non-null keys are deduplicated.

The receipt HMAC is produced by the booking service from the existing
server-side `SECRET_KEY`. The model never reads configuration or computes the
HMAC itself.

## Core Workflows & Contracts

A keyed authoritative command creates its booking and receipt in the same
nested transaction. The receipt contains only tenant ID, booking ID,
idempotency key, fingerprint version, HMAC, and creation timestamp. A unique
tenant/key selects the first writer. A unique booking ID prevents multiple
receipt authorities for one booking.

The composite foreign key `(tenant_id, booking_id)` references the matching
`(tenant_id, id)` booking key, so a receipt cannot be linked to a booking from
another tenant. No router or response schema exposes receipt rows.

## Data Safety & Isolation

- Tenant/key uniqueness is database-enforced.
- Receipt-to-booking tenant integrity is database-enforced.
- `__repr__` omits the idempotency key and HMAC.
- HMACs, canonical request bytes, secrets, contact values, and booking notes
  must never be logged, placed in audit details, or returned to clients.
- Audit retention and tenant-admin audit creation cannot alter replay behavior.

## Known Issues, Edge Cases & Outstanding Work

- No receipt is backfilled from historical audit rows. Legacy keyed bookings
  fail closed until an approved reconciliation policy exists.
- `SECRET_KEY` rotation requires a versioned receipt/key migration before the
  old key is removed.
- A downgrade cannot restore historical global key uniqueness after different
  tenants have used the same non-null key without first reconciling those rows.
- Revision `b6c2d4e8f0a1` intentionally excludes the untracked unsafe `e8`
  migration in the dirty main worktree. That lineage is a deployment blocker
  until explicitly resolved.
- A real multi-session PostgreSQL contention test remains environment-dependent.

## Verification & Testing Commands

```powershell
python -m pytest -q -p no:cacheprovider tests/test_booking_command_receipts.py
python -m pytest -q -p no:cacheprovider tests/test_booking_creation_service.py
python -m py_compile app/models/booking.py app/models/booking_command_receipt.py
python -m ruff check app/models/booking.py app/models/booking_command_receipt.py
```

All tests use synthetic disposable data and must not create live bookings or
contact external services.
