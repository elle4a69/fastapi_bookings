# fastapi_bookings — Production & AI-First Roadmap

> **Vision:** A fully-featured booking API that serves a mobile-first, AI-driven client experience.
> Clients interact via messaging (SMS / WhatsApp / in-app chat). An AI agent handles the
> conversation, takes bookings, manages reminders and reschedules — all via HTTP calls to this API.
> Human admins manage the business through a separate dashboard.

---

## Architecture Decision (read before writing any code)

```
Client (SMS / WhatsApp / In-App Message)
        │  incoming message
        ▼
  AI Orchestration Service          ← separate service, NOT inside this API
  (LLM · conversation state · tool dispatch)
        │  HTTP tool calls
        ▼
  fastapi_bookings API              ← stays clean — pure data / business logic
        │
        ▼
  PostgreSQL  +  Outbox  →  Notification Worker  →  Email / SMS / Push
```

**Keep the booking API dumb.** The LLM logic, conversation memory, and tool dispatch live in a
separate service. The booking API is its tool set. This separation means the API can be tested,
scaled, and replaced independently of the AI layer.

---

## Critical Blockers (these must be fixed before anything else)

These are not phased — they are prerequisites. Deploying without them is unsafe.

| # | Issue | Status |
|---|---|---|
| C1 | No Alembic migrations — SQLite auto-create only | ❌ **Still needed** |
| C2 | `SECRET_KEY = "changeme"` default in config | ❌ **Still needed** |
| C3 | No automated test suite (only `smoke.http`) | ❌ **Still needed** |
| C4 | SQLite volume-mounted in docker-compose | ❌ **Still needed** |
| C5 | `requirements.txt` completely unpinned | ❌ **Still needed** |
| C6 | Provider scheduling not enforced by availability engine | ⚠️ Schedule models added — engine not yet wired |
| C7 | No rate limiting on public/auth endpoints | ❌ **Still needed** |

---

## Phase 0 — Pre-Flight: Structural Decisions

**Do this before writing any feature code.**

These are decisions, not code changes. Getting them wrong early means painful refactors later.

- [ ] Decide on the messaging channel(s): WhatsApp Business API (Twilio), SMS (Twilio/SNS), or
      custom in-app. The AI orchestration service design depends on this.
- [ ] Decide on the AI provider: OpenAI function calling, Anthropic tool use, or open-source.
      The tool schema format differs.
- [ ] Decide on notification delivery: SendGrid, AWS SES (email) + Twilio (SMS).
- [ ] Decide on payment gateway: Stripe is assumed below — confirm this.
- [ ] Confirm multi-tenancy timeline: the model exists but is unwired. Decide whether Phase 1
      includes adding `tenant_id` or whether the app launches single-tenant first.

---

## Phase 1 — Foundation & Stabilisation

**Estimated effort: 4–6 days**
**Unlocks: safe to deploy at all; AI agent can begin basic testing**

### 1a. Database — migrate to Alembic + PostgreSQL

- Add `alembic` and `psycopg2-binary` (or `asyncpg`) to requirements
- `alembic init alembic`, generate the initial migration from current models
- Update `docker-compose.yml` to run a `postgres:16` container
- Pass `DATABASE_URL` as an environment variable — remove the SQLite file mount
- Confirm `Base.metadata.create_all` is removed from startup (Alembic owns schema now)

### 1b. Lock dependency versions

Pin everything in `requirements.txt`:
```
fastapi==0.115.x
uvicorn==0.30.x
sqlalchemy==2.0.x
pydantic==2.7.x
passlib[bcrypt]==1.7.4
python-jose==3.3.0
python-multipart==0.0.9
python-dateutil==2.9.0
pydantic-settings==2.3.x
alembic==1.13.x
psycopg2-binary==2.9.x
```

### 1c. Secrets management

- In `config.py`, raise `ValueError` if `SECRET_KEY == "changeme"` and `APP_ENV == "production"`
- Create `.env.example` documenting all required variables
- Add `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_API_KEY` to `docker-compose.yml` environment section
- Never commit `.env` — add to `.gitignore`

### 1d. Switch auth header to `Authorization: Bearer`

- Change `deps.py` to read `Authorization: Bearer <token>` instead of `X-Token`
- This is the standard all mobile SDKs, HTTP clients, and AI frameworks expect
- Update `smoke.http` and `contracts/` to match

### 1e. Timezone-aware datetimes (AI + mobile requirement)

- Add `timezone=True` to all `DateTime` columns in every model
- Return all datetimes as ISO 8601 with `+00:00` suffix
- Generate an Alembic migration
- Mobile clients in different timezones and AI agents parsing natural-language dates both depend on this

### 1f. Fix `updated_at` auto-refresh

- Add `onupdate=datetime.utcnow` to every `updated_at` column in every model
- Generate an Alembic migration

### 1g. Phone and email indexes on `Client`

- Add `index=True` to `Client.phone` and `Client.email`
- Every incoming AI message will do a lookup by phone number — a full table scan is unacceptable
- Generate an Alembic migration

### 1h. Structured error codes (AI requirement)

AI agents need machine-readable errors to decide what to do next — not just a human-readable string.

Change all `HTTPException` raises in public-facing routes to include an `error_code`:

```python
raise HTTPException(
    status_code=400,
    detail={"error_code": "SLOT_UNAVAILABLE", "message": "Requested slot is not available"}
)
```

Core error codes to define now:

| Code | Meaning |
|---|---|
| `SLOT_UNAVAILABLE` | Time slot is taken or held |
| `PROVIDER_NOT_ELIGIBLE` | Provider cannot perform this service |
| `CLIENT_NOT_FOUND` | No client matches the supplied identity |
| `INVALID_TIME_RANGE` | end must be after start |
| `HOLD_EXPIRED` | Hold no longer valid |
| `INVALID_TRANSITION` | Booking status transition not allowed |
| `DUPLICATE_REQUEST` | Idempotency key already used |

---

## Phase 2 — AI-Readiness: API Primitives

**Estimated effort: 4–6 days**
**Unlocks: AI agent can be built and tested end-to-end**

These are specific additions to the API that an AI agent cannot function without.

### 2a. `find_or_create_client` endpoint

This is the most critical missing piece. An AI agent receiving a WhatsApp message knows the
sender's phone number. It does not know their `client_id`. Without this, every booking fails.

```
POST /api/public/clients/identify
{
  "phone": "+61400000000"     // or
  "email": "user@example.com"
}
→ 200: { "ok": true, "data": { "id": 42, "name": "...", "created": false } }
→ 201: { "ok": true, "data": { "id": 43, "name": null,  "created": true  } }
```

Logic: look up by phone OR email → return if found; create a minimal record if not.
The `created` flag lets the AI know whether to ask for a name.

### 2b. Idempotency keys on booking and hold creation

LLMs retry. Networks fail. Without this, a single user intent creates duplicate bookings.

- Accept an optional `X-Idempotency-Key` header on:
  - `POST /api/public/bookings`
  - `POST /api/public/holds`
  - `POST /api/admin/bookings`
- Store `(key, response_body, expires_at)` in an `idempotency_keys` table
- On duplicate key: return the stored response immediately without re-executing
- Keys expire after 24 hours

### 2c. Hold expiry enforcement

`Hold.expires_at` exists but nothing expires holds automatically. An abandoned AI conversation
blocks a slot indefinitely.

- Add a `POST /api/admin/holds/expire-stale` admin endpoint that expires all holds past
  `expires_at` — callable by a cron job or startup hook
- Add a check in `create_hold` and `create_booking` that first cleans up expired holds for the
  same slot before conflict-checking

### 2d. Fix availability search for partial queries

`GET /api/public/availability` currently requires both `service_id` and `provider_id`.
`POST /api/public/search-availability` exists but returns `[]` when no service is given.

An AI conversation often starts without either — "I want a haircut Thursday."

- Implement the multi-service/category path in `search_availability`
- If only a category is supplied, search across all services in that category
- Default `date_from` to now, `date_to` to now + 7 days if not provided
- Return results grouped by provider so the agent can offer choices

### 2e. Wire the outbox

`OutboxEvent` and `BookingEvent` models exist but are never written to.
An AI agent needs to know when an admin confirms, cancels, or reschedules a booking so it
can message the client.

Add outbox writes in these router actions:
- `confirm_booking` → `booking.confirmed`
- `cancel_booking` → `booking.cancelled`
- `complete_booking` → `booking.completed`
- `noshow_booking` → `booking.no_show`
- `reschedule_booking` → `booking.rescheduled`
- `create_booking` / `create_public_booking` → `booking.created`

```python
event = OutboxEvent(
    type="booking.confirmed",
    payload=json.dumps({"booking_id": booking.id, "client_id": booking.client_id})
)
db.add(event)
# committed in same transaction as the booking update
```

### 2f. AI tool manifest (generate from OpenAPI)

The existing `contracts/route-manifest.json` is one step from an OpenAI/Anthropic tool schema.

Add a `GET /api/public/tool-manifest` endpoint that returns the API's capabilities in the format
expected by the AI provider you chose in Phase 0. This lets the AI orchestration service
auto-configure its tool set from the booking API rather than hardcoding it.

---

## Phase 3 — Test Coverage & CI

**Estimated effort: 5–7 days**
**Unlocks: confidence to iterate; required before AI agent testing is reliable**

### 3a. pytest suite

- Use `TestClient` + `pytest-asyncio` + in-memory SQLite for test DB
- Cover at minimum:
  - Auth flows (admin login, public token, invalid credentials)
  - Booking creation, state transitions, conflict detection
  - Hold → confirm → booking conversion
  - `find_or_create_client` (found, created, duplicate phone)
  - Idempotency key deduplication
  - Availability basic cases (no conflicts, with conflicts)
  - Error code format on all failure paths

### 3b. CI pipeline

- Lint: `ruff`
- Type check: `mypy --strict` on `app/`
- Tests: `pytest --cov=app --cov-report=term-missing`
- Fail below 65% coverage to start; raise to 80% over time
- Run on every push and PR

### 3c. Upgrade `/health` to include DB probe

```python
@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, "db": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"ok": False, "db": "error"})
```

---

## Phase 4 — Scheduling Engine Completion

**Estimated effort: 5–8 days**
**Unlocks: accurate availability — the AI agent's core capability**

### 4a. Provider working schedules

Currently the engine treats all hours as available — a provider with no schedule appears available
24/7.

- Add `ProviderSchedule` model: `(provider_id, day_of_week, open_time, close_time, location_id)`
- Wire availability engine to only generate slots within schedule hours
- Add CRUD: `GET/POST/PUT/DELETE /api/admin/providers/{id}/schedule`
- Add to route manifest and AI tool manifest

### 4b. Buffer times between bookings

- Add `buffer_before` and `buffer_after` (minutes) to `Service` model
- Adjust slot-sweep to block `buffer_before` minutes before and `buffer_after` minutes after each
  existing booking for the same provider

### 4c. Automatic audit trail on booking transitions

- Add a SQLAlchemy event listener (or inline writes in each transition endpoint) that writes an
  `AuditLog` row automatically on every booking status change
- Remove the manual `POST /api/admin/audit-log` — auditing must not be opt-in

### 4d. Soft-delete on core entities

- Add `deleted_at` to `Service`, `Provider`, `Client`
- Filter all list queries with `deleted_at IS NULL`
- Never hard-delete any entity that has associated bookings (FK safety)
- Return `410 Gone` with `error_code: ENTITY_DELETED` when accessing a deleted entity

---

## Phase 5 — Notifications, Outbox Worker & AI Orchestration Layer

**Estimated effort: 6–10 days**
**Unlocks: the AI agent can send messages; the full conversational loop closes**

### 5a. Outbox worker

Build a background worker (FastAPI `BackgroundTasks`, Celery, or ARQ with Redis) that:

1. Polls `OutboxEvent` where `processed = false`
2. Dispatches to the appropriate handler based on `type`
3. Marks `processed = true` and sets `processed_at` on success
4. Logs failures without crashing (retry with exponential backoff)

### 5b. Email / SMS notification dispatch

- Integrate your chosen providers (e.g. SendGrid for email, Twilio for SMS)
- Template types needed:
  - `booking.created` → "Your booking request has been received"
  - `booking.confirmed` → "Your booking is confirmed for {time}"
  - `booking.cancelled` → "Your booking has been cancelled"
  - `booking.rescheduled` → "Your booking has been moved to {new_time}"
  - Reminder (24h before) → "Reminder: you have a booking tomorrow at {time}"
- Notification delivery goes through the outbox worker, not directly from routes

### 5c. Waitlist fulfillment

When a booking is cancelled, the outbox worker should:
1. Query `WaitlistEntry` for the same service/time window
2. Emit a `slot_released` event
3. Notify waiting clients (via the AI agent or directly)

### 5d. AI Orchestration Service (external, not inside this API)

Build as a separate Python service or serverless function:

```
Incoming message (Twilio webhook / WebSocket / polling)
    → Extract sender identity (phone/channel)
    → Call POST /api/public/clients/identify to get client_id
    → Load conversation state (Redis / DB)
    → Send message + state + tool definitions to LLM
    → LLM returns tool calls (e.g. search_availability, create_hold, confirm_hold)
    → Execute tool calls against booking API
    → Store LLM response in conversation state
    → Send reply to client
```

Key design rules for this service:
- Conversation state is stored externally (Redis or a `conversations` table in this DB)
- Every tool call includes an idempotency key derived from `(conversation_id, turn_number, tool_name)`
- The AI service handles natural language → ISO datetime conversion before calling the API
- The AI service does NOT have database access — only the booking API does

### 5e. Conversation model (add to this API)

Add a `Conversation` model to track AI dialogue sessions:

```python
class Conversation(Base):
    __tablename__ = "conversations"
    id          = Column(String, primary_key=True)   # UUID
    client_id   = Column(Integer, ForeignKey("clients.id"), nullable=True)
    channel     = Column(String)   # "whatsapp" | "sms" | "in_app"
    channel_id  = Column(String)   # phone number / device ID
    status      = Column(String, default="active")
    created_at  = Column(DateTime)
    updated_at  = Column(DateTime)
```

Add `GET /api/admin/conversations` (paginated) so admins can review AI conversations.

---

## Phase 6 — Payments

**Estimated effort: 5–8 days**
**Unlocks: revenue; deposit collection at booking time**

### 6a. Stripe integration

- Add `stripe` to requirements
- Add `stripe_payment_intent_id` and `stripe_customer_id` to `Payment` model
- On booking creation (admin or public), optionally create a PaymentIntent
- Add `POST /api/webhooks/stripe` to receive Stripe events:
  - `payment_intent.succeeded` → mark payment as paid, confirm booking if pending
  - `payment_intent.payment_failed` → mark payment as failed, notify client via outbox
- The AI agent can use `GET /api/public/orders/{booking_id}/payment-link` to send a link to the client

### 6b. Deposit support

- Add `deposit_amount` and `deposit_paid` to `Booking` model
- Allow partial payment at booking time, remainder at completion

---

## Phase 7 — Mobile Polish & Push Notifications

**Estimated effort: 3–5 days**
**Unlocks: native mobile experience; proactive push reminders**

### 7a. Token refresh endpoint

Mobile apps stay logged in for months. Access tokens expire in 7 days by default.

- Add `refresh_token` field to `User` model (hashed, single-use)
- `POST /api/auth/refresh` — accepts refresh token, returns new access + refresh tokens
- Issue refresh token alongside access token on login

### 7b. Push notification tokens

- Add `DeviceToken` model: `(client_id, platform, token, created_at)`
- Add `POST /api/public/clients/{id}/device-token` and `DELETE` equivalent
- Outbox worker sends FCM (Android) or APNs (iOS) push alongside email/SMS

### 7c. Pagination on all remaining list endpoints

- `addons`, `categories`, `resources`, `packages`, `waitlist` all return unbounded lists
- Add `page`/`page_size` to all of them using the existing `pagination_params` dependency

---

## Phase 8 — Multi-Tenancy

**Estimated effort: 6–9 days**
**Unlocks: multiple business accounts on a single deployment**

The `Tenant` model exists. Nothing else is wired.

### 8a. Add `tenant_id` to core models

- `users`, `services`, `providers`, `clients`, `locations`, `bookings`, `conversations`
- Generate an Alembic migration

### 8b. Scope all queries by tenant

- Add `get_current_tenant` dependency reading `tenant_id` from JWT payload
- Inject into all admin and public routes; filter every query by `tenant_id`

### 8c. Tenant provisioning

- `POST /api/superadmin/tenants` — creates tenant + owner user
- Separate `superadmin` role, not accessible via normal admin auth

---

## Phase 9 — Production Hardening

**Estimated effort: 3–5 days**
**Unlocks: production traffic; AI agent retry safety**

### 9a. Rate limiting

Add `slowapi` (or Redis-backed limiter). Protect:
- `POST /api/public/auth/token` — 10/min per IP
- `POST /api/admin/auth` — 10/min per IP
- `POST /api/public/bookings` — 30/min per client
- `POST /api/public/search-availability` — 60/min per token

AI retry loops make rate limiting more important here than in a typical API.

### 9b. Structured logging

- Replace all `print()` with Python `logging` using a JSON formatter (`python-json-logger`)
- Add a request ID middleware that generates a UUID per request and injects it into all log lines
- Log: method, path, status, duration, request_id, client_id (if available)

### 9c. TLS and reverse proxy

- Deploy behind nginx or Caddy with HTTPS termination
- Remove any `allow_origins=["*"]` — restrict to the exact frontend and AI service origins

### 9d. Secrets rotation support

- Document a secret rotation procedure (new `SECRET_KEY` invalidates all existing tokens)
- Consider short-lived tokens (1h) + refresh tokens (Phase 7) to minimise rotation blast radius

### 9e. Database connection pooling

- Configure SQLAlchemy pool: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`
- Under AI agent load (many parallel tool calls) the default pool will exhaust quickly

---

## Summary Timeline

| Phase | Name | Effort | Key Outcome |
|---|---|---|---|
| 0 | Architecture decisions | 1 day | No wrong turns later |
| 1 | Foundation & stabilisation | 4–6 days | Safe to deploy |
| 2 | AI-readiness: API primitives | 4–6 days | AI agent can be built |
| 3 | Test coverage & CI | 5–7 days | Confidence to iterate |
| 4 | Scheduling engine | 5–8 days | Accurate availability |
| 5 | Notifications + AI orchestration | 6–10 days | Full conversational loop |
| 6 | Payments | 5–8 days | Revenue |
| 7 | Mobile polish + push | 3–5 days | Native mobile experience |
| 8 | Multi-tenancy | 6–9 days | Multiple business accounts |
| 9 | Production hardening | 3–5 days | Production traffic ready |

**Minimum viable AI booking agent: Phases 0 → 1 → 2 → 3 → 4 → 5**

---

## What is Already Done Well

These do not need to change:

- JWT auth with admin and public roles — correct and sufficient
- Booking state machine — well-defined, all transitions enforced
- Hold → confirm → booking flow — exactly right for multi-turn AI conversations
- `{"ok": bool, "data": ...}` response envelope — clean for LLM parsing
- `contracts/route-manifest.json` — one step from an AI tool manifest
- Resource allocation with conflict detection — real logic, not placeholder
- Public bootstrap endpoint — exactly what a mobile app needs on startup
- Docker + docker-compose baseline — ready to extend
- Provider working schedules — `ProviderWorkDay`, `ProviderSpecialDay`, `BlockedTime`, `ReservedTime` ✅ merged
- Public client portal — register, login, `find_or_create_client` (AI agent critical path) ✅ merged
- Notification templates + reminder rules + dispatch logs ✅ merged
- Device push tokens (FCM/APNs) ✅ merged
- Checkout / invoices / tax rates / promotions ✅ merged
- Additional / intake fields (configurable per scope) ✅ merged
- Recurring booking series ✅ merged
- Service ↔ provider / category assignment ✅ merged
- Public timeline — `/slots`, `/schedule`, `/first-available-day` ✅ merged
- Public entity listing — services, providers, categories, locations ✅ merged
- OpenTelemetry tracing + JSON structured logging ✅ merged
- `psycopg2-binary` in requirements (Postgres-ready) ✅ merged
- Webhook registration model + router ✅ merged (FastBook)
- Calendar notes model + router ✅ merged (FastBook)
- PluginState (runtime feature toggles) ✅ merged (FastBook)
- GdprConsent log ✅ merged (FastBook)
- **JSON-RPC removed entirely** ✅
- **All 14 schemas migrated from Pydantic v1 `orm_mode` → Pydantic v2 `ConfigDict`** ✅
- **`Booking` model — `series_id` FK + `series` back_populates added** ✅
- **`ProviderResponse` added to provider schema** ✅
- **All 204 DELETE routes fixed with `response_model=None`** ✅
- **Application imports cleanly — `python -c "from app.main import app"` passes** ✅

---

## Remaining work before the server can be fully tested

### Still needs doing before smoke testing

1. **Contracts are stale** — [x] **Done**. `contracts/route-manifest.json` and `contracts/types.ts` have been fully regenerated from the running backend's `/openapi.json` schema.

2. **Availability engine does not yet use provider schedules** — [x] **Done**. The availability engine fully utilizes provider working schedules, special overrides, and blockages to compute slots.

3. **Outbox not wired** — [x] **Done**. The Outbox worker is fully implemented and active in lifespan, and booking status transitions enqueue transactional outbox events correctly.

4. **`updated_at` still not auto-refreshing on PATCH** — the `onupdate` was added to `Booking.updated_at` in this session but not audited across all other models.

5. **`find_or_create_client` response shape** — [x] **Done**. The `/api/public/clients/identify` endpoint has been normalized to return `{"created": bool}` inside the schema data payload, and TypeScript contracts regenerated.

6. **Public Authentication Scoping** — [x] **Done**. Securing public endpoints to require the `X-Token` header and scoping queries by resolved `tenant.id`.

7. **Multi-Service Availability Search** — [x] **Done**. Implemented timezone-aware availability search across all tenant active services (optionally filtered by category) when `service_id` is omitted.



What Remains to Be Done (Future Scope)
All Phase 5, 6, and 7 integrations have been successfully implemented:
- Phase 5 (Notifications & Transactional Outbox Worker): Done. Polling worker, ClickSend SMS/MMS, and Chatwoot AUTO/TRAINING mode dispatching.
- Phase 6 (Payments): Done. Stripe payment webhook, session creation, deposit session generation.
- Phase 7 (Mobile Polish & Push Notifications): Done. Token refresh, device token registration, FCM push notification dispatch.

### OBJECTIVE
[x] **Done**. Phase 5, 6, and 7 implemented and fully verified with automated test suites passing. 



The system operates as an AI booking orchestrator backend integrated with a self-hosted Chatwoot Community Edition gateway. All database models and actions must respect multi-tenant isolation using our standard tenant/account identifier.



---



### PHASE 5: NOTIFICATIONS & TRANSACTIONS OUTBOX WORKER



1. **Database Integration (`OutboxEvent`)**

   - Ensure a robust `OutboxEvent` model exists (or create it) with fields: `id`, `tenant_id`, `event_type` (e.g., `SEND_SMS`, `SEND_MMS`, `CHATWOOT_REPLY`), `payload` (JSONB), `status` (PENDING, PROCESSED, FAILED), `retry_count`, `error_log`, `created_at`, `processed_at`.

   - All critical booking mutations must append a pending row to this table inside the same database transaction.



2. **Asynchronous Background Polling Worker**

   - Implement a dedicated, resilient background polling mechanism (e.g., via an asyncio loop registered on the FastAPI application lifecycle startup/lifespan).

   - The worker must run a continuous loop (with configurable sleep interval) to fetch unfulfilled `OutboxEvent` records ordered by `created_at` ascending.

   - Implement exponential backoff for retries, locking mechanism or row-level atomic selects (`FOR UPDATE SKIP LOCKED`) to ensure concurrency safety.



3. **Dispatch Services**

   - **ClickSend SMS & MMS Client:** Build a dedicated, non-blocking async utility utilizing `httpx` to process `SEND_SMS` and `SEND_MMS` payloads via the ClickSend v3 REST API (`https://rest.clicksend.com/v3/sms/send` and `/v3/mms/send`). Authenticate via Basic Auth using your API credentials. The MMS worker must explicitly support sending a message body, a subject line, and a `media_file` URL string.

   - **Chatwoot Orchestration Logic:** Handle `CHATWOOT_REPLY` outbox items. Read the client-tenant's setting from our database. If the conversation mode is `AUTO`, dispatch a public message via the Chatwoot REST API (`POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages`). If the mode is `TRAINING`, dispatch it with `is_private: true` to generate a yellow private note inside Chatwoot.



---



### PHASE 6: STRIPE PAYMENTS INTEGRATION



1. **Webhook Endpoint**

   - Create a dedicated public route: `POST /api/v1/webhooks/stripe`.

   - Implement strict Stripe signature verification using the `stripe.Webhook.construct_event` method with the raw request body and environment-stored signing secret.



2. **Event Processing Logic**

   - Parse and process the following Stripe events idempotently:

     - `checkout.session.completed`: Extract the payment metadata (which must contain `tenant_id` and `booking_id`). Update the booking record to an authorized/confirmed state. Append a `SEND_SMS` or `SEND_MMS` notification event to the `OutboxEvent` table using the ClickSend payload structures.

     - `invoice.payment_failed` / `charge.failed`: Extract the context from metadata, flag the booking as pending/cancelled due to non-payment, and add a failure alert into the `OutboxEvent` queue.



3. **Deposit Collection Engine**

   - Expose an endpoint or service function to generate a Stripe Checkout Session configured specifically for upfront deposit collection based on booking configurations.



---



### PHASE 7: MOBILE POLISH & SYSTEM PUSH NOTIFICATIONS



1. **Device Registration & Lifecycle**

   - Create a database model `UserDevice` tracking user/agent device tokens: `id`, `user_id`, `tenant_id`, `device_token`, `platform` (IOS, ANDROID), `is_active`, `updated_at`.

   - Create an endpoint `POST /api/v1/devices/register` to handle device registration. Ensure it performs a clean upsert (if a token moves to a different user, deactivate or reassign it correctly).

   - Create a corresponding token expiration/refresh or logout deactivation endpoint.



2. **Unified Firebase Notification Dispatch**

   - Integrate with the official Firebase Admin SDK (`firebase-admin`) to manage push notification routing across both iOS and Android devices using standard Firebase Cloud Messaging (FCM) channels. (Note: iOS APNs certificates are uploaded directly within the Firebase Console dashboard, allowing our FastAPI backend to leverage a single, clean FCM implementation).

   - Hook into the `OutboxEvent` worker and core application event listeners. When internal scheduling events occur (e.g., "New Booking Confirmed", "Booking Modified", or when an active conversation requires manual agent takeover), pull the active team member `UserDevice` tokens matching that specific `tenant_id` and dispatch the notification payload.

   - Structure the push payloads precisely to trigger immediate audible device chimes and lock screen system banners within our custom, white-labeled mobile app shell.



---



### VERIFICATION AND OUTPUT EXPECTATIONS

- Generate clean, production-grade Python code utilizing modern type-hinting, proper async/await patterns where blocking I/O is concerned, and explicit exception handling across external HTTP boundaries.

- Update/create all relevant router files, utility packages, and schema validations.

- Verify structural and path alignment across the edited files before declaring the tasks complete.