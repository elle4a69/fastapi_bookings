# SMS Transports

## 1. Purpose & Scope

This package normalizes inbound carrier payloads, authenticates carrier
webhooks and submits already-authorized outbound SMS commands. It does not own
conversation lifecycle, booking state, tenant selection or retry policy.

## 2. Architecture & Key Files

- `base.py` defines normalized inbound, outbound result and delivery-update
  contracts.
- `mobilemessage.py` implements the MobileMessage HTTP adapter.
- `fake.py` is the no-network synthetic adapter used in tests.
- `__init__.py` resolves an allowlisted adapter by transport type.

## 3. Setup, Configuration & Dependencies

MobileMessage credentials are read from the selected `SmsAccount` through its
encrypted credential property. Every MobileMessage line receiving inbound or
delivery webhooks must have a nonblank string `webhook_secret` in that encrypted
mapping. Missing, malformed or undecryptable webhook credentials fail closed
with a generic service-unavailable response. Valid secrets are compared in
constant time. `httpx` performs outbound HTTPS calls. Tests must patch the
client or use the fake adapter; they must never use live credentials or
destinations.

## 4. Core Workflows & Contracts

Inbound parsing returns normalized domain input or a generic HTTP error.
Outbound submission returns a structural status/code. Provider rejection,
HTTP bodies, exception text and receipt error text are never returned or
logged. Successful delivery may return the provider message ID required for
later receipt correlation.

MobileMessage delivery receipts accept only the exact bounded provider states
`queued`, `sent`, `delivered` and `failed`, which map to the same internal
states. Malformed, unknown and oversized states are rejected before any
message lookup. The router locks the exact account-scoped outbound message and
permits only `queued|sending -> sent|delivered|failed` and
`sent -> delivered|failed`. `delivered` and `failed` are terminal. Duplicate,
out-of-order, terminal-state and untracked receipts are acknowledged without
mutation. Every accepted or no-op receipt returns only `{"status":"success"}`;
it never confirms message correlation or reflects provider identifiers/status.

## 5. Data Safety & Isolation

Adapters receive a previously scoped account and must not select another
tenant/provider. Logs contain fixed event descriptions only. Message bodies,
addresses, credentials, provider response bodies and provider error details
are confidential.

## 6. Known Issues, Edge Cases & Outstanding Work

- Provider retry and final state are owned by the SMS outbox worker.
- The provider message ID is used only to resolve an existing outbound
  message. Delivery receipts retain a canonical status and fixed failure
  fields. Only an actual allowed status transition creates a receipt row;
  duplicates and incompatible transitions have no persistence effect.
- Provider-specific delivery guarantees have not been established.

## 7. Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_sms_credential_privacy.py tests/test_sms_foundation.py -q
```
