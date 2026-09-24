# Assistant Booking Bridge

## Purpose & Scope

Private, disabled-by-default booking-domain bridge for Assistant UI's single `primary` line. It owns neither messaging, AI, SMS, calendar synchronization nor customer-facing staff workflow.

## Architecture & Key Files

`assistant_booking_bridge.py` verifies a keyed, replay-protected server-to-server proof, derives scope exclusively from a durable binding, and calls scheduling/allocation services.

## Setup, Configuration & Dependencies

Create a binding through a controlled administrative migration/runbook: a `primary` line, tenant, provider, optional default location, key id, base64 Ed25519 public key and `enabled=false`. The Assistant private key belongs only in its runtime secret configuration; it is never supplied to FastAPI.

## Core Workflows & Contracts

`GET /api/internal/assistant-booking-bridge/catalog`; `POST /availability`; `POST /proposals`; `POST /confirmations`. Each request requires key-id, epoch timestamp (five minutes), nonce, and base64 Ed25519 signature. The canonical UTF-8 input is `METHOD + "\\n" + PATH + "\\n" + TIMESTAMP + "\\n" + NONCE + "\\n" + SHA256(raw request body hex)`. Catalogue returns only customer-safe services and the authoritative business timezone. A proposal returns a customer-safe canonical summary (service, duration, price, time, timezone and display names), never scope identifiers. Proposals expire in ten minutes and reserve nothing; confirmations create only `pending` bookings after revalidation.

## Data Safety & Isolation

The request cannot submit tenant/provider/location. Scope is loaded from the binding. Nonces are durable and unique per binding. The booking idempotency key is the first durable request claim; it is bound to the bridge binding and inbound request ID, while a non-PII command fingerprint rejects altered request-ID reuse. No outbox, SMS, Chatwoot or AI call occurs. Customer matching is tenant-scoped and ambiguous matches fail closed.

## Known Issues, Edge Cases & Outstanding Work

Binding provisioning and secret delivery must be implemented as a separate owner-approved operational procedure before staging. The current secret-proof format requires TLS and must not be exposed to browsers.

## Verification & Testing Commands

`python -m pytest -p no:cacheprovider -q tests/test_assistant_booking_bridge.py`
`python -m compileall app/services/assistant_booking_bridge.py app/api/routers/assistant_booking_bridge.py`
`alembic heads`
