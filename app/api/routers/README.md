# API Routers

## 1. Purpose & Scope

`app/api/routers` maps HTTP contracts onto authenticated or capability-scoped
application services. Routers validate transport shape, establish auth/tenant
context and translate domain failures; they do not own provider credentials or
business persistence rules.

## 2. Architecture & Key Files

- `sms_webhooks.py` exposes public carrier inbound and delivery-receipt routes.
- `sms_conversations.py` exposes tenant-scoped staff messaging operations.
- `sms_chatwoot.py` exposes Chatwoot binding administration and webhook intake.
- Other router files expose booking, availability, tenant and administration
  contracts described by their response schemas.

## 3. Setup, Configuration & Dependencies

Routers use FastAPI dependencies from `app/api/deps.py`, SQLAlchemy sessions,
Pydantic schemas and service-layer contracts. Public SMS webhook routes require
the provider-specific server-side credential configured on the matched SMS
account.

## 4. Core Workflows & Contracts

Carrier routes are `POST /api/sms/webhooks/{transport_type}/{account_public_id}`
and `POST /api/sms/webhooks/{transport_type}/{account_public_id}/delivery`.
They return stable generic client errors. Staff conversation operations use the
application admin/tenant dependencies and preserve service-level conflict
status codes. Manual-message idempotent replay is valid only for the same
tenant/provider/account/conversation, request body and authenticated actor; a
different administrator reusing a key receives HTTP 409 without new effects.

## 5. Data Safety & Isolation

Public route values, request bodies, provider identifiers, phone numbers,
tokens and raw exceptions are never included in logs. Carrier failures are
reported with fixed structural messages. Authenticated routers must scope every
read/write through the current tenant and applicable provider/account.

## 6. Known Issues, Edge Cases & Outstanding Work

- Historical provider receipt rows may contain legacy raw payloads. This task
  stops new MobileMessage receipts from retaining raw error payloads but does
  not inspect or migrate existing rows.
- Credential rotation and legacy plaintext cleanup require the separately
  approved runbook documented in `app/models/README.md`.

## 7. Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_sms_credential_privacy.py tests/test_sms_operations_safety.py -q
```
