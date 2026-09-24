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
encrypted credential property. `httpx` performs outbound HTTPS calls. Tests
must patch the client or use the fake adapter; they must never use live
credentials or destinations.

## 4. Core Workflows & Contracts

Inbound parsing returns normalized domain input or a generic HTTP error.
Outbound submission returns a structural status/code. Provider rejection,
HTTP bodies, exception text and receipt error text are never returned or
logged. Successful delivery may return the provider message ID required for
later receipt correlation.

## 5. Data Safety & Isolation

Adapters receive a previously scoped account and must not select another
tenant/provider. Logs contain fixed event descriptions only. Message bodies,
addresses, credentials, provider response bodies and provider error details
are confidential.

## 6. Known Issues, Edge Cases & Outstanding Work

- Provider retry and final state are owned by the SMS outbox worker.
- Delivery receipts retain only normalized status, a fixed failure code and
  the provider message ID required to resolve the existing outbound message.
- Provider-specific delivery guarantees have not been established.

## 7. Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_sms_credential_privacy.py tests/test_sms_foundation.py -q
```
