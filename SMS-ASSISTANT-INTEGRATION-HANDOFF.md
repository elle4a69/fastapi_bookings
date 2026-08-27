# SMS Assistant / FastAPI Bookings Integration Handoff

> **Superseded:** Use `ANTIGRAVITY-CONSOLIDATED-HANDOFF.md` as the authoritative
> specification. This older document is retained only as historical implementation
> detail and contains an obsolete port-5190 integration recommendation.

Last verified: 2026-08-23 (Australia/Sydney)

## Fresh-agent mission

Continue integrating the existing SMS autoresponder/Assistant UI application into
FastAPI Bookings while keeping FastAPI Bookings authoritative for booking data and
keeping the Assistant application modular. Use HTTP APIs between the applications.
Do not import the booking application's ORM models into the Assistant, do not give
the Assistant direct access to the booking database, and do not overwrite or delete
the original Assistant project at `F:\Projects\assistant-ui`.

The initial copy and API adapter are already implemented. The immediate job is to
verify that the embedded UI is running from the copied integration (not the original
source tree), complete an end-to-end booking smoke test, and then incrementally
replace or hide the Assistant's legacy booking UI where the main booking application
already owns that functionality.

## User intent and constraints

- Original source: `F:\Projects\assistant-ui`
- Main application/repository: `F:\Projects\fastapi_bookings`
- Copy, do not move or delete, the Assistant application.
- Preserve the Assistant's SMS inbox, autoresponder, prompts, customer simulator,
  training/RAG, settings, provider webhooks, and messaging behavior.
- FastAPI Bookings must be the source of truth for services, availability, clients,
  providers, locations, and bookings.
- Begin with an API-only connection to reduce risk to the main FastAPI application.
- Keep the copied application isolated and independently runnable.
- Expose it from the booking admin via a navigation/menu item.
- Avoid broad refactors of the booking application.

## Implemented architecture

```text
Booking admin browser
  http://localhost:7070/admin/sms-assistant
                  |
                  | iframe
                  v
Copied Assistant frontend
  http://localhost:5190
                  |
                  | VITE_API_BASE=http://localhost:8026
                  v
Copied Assistant FastAPI backend
  http://localhost:8026
       |                         |
       | messaging/settings     | booking compatibility adapter
       v                         v
Assistant-local SQLite,       Main FastAPI Bookings API
SMS provider, RAG, etc.       http://127.0.0.1:8000
                              (authoritative bookings/catalogue)
```

The copy lives at `integrations/assistant-ui`. The original project remains at
`F:\Projects\assistant-ui` and was not removed.

### Isolation boundary

The copied Assistant retains its own:

- Python virtual environment and requirements
- Node dependencies and Vite frontend
- Assistant SQLite databases
- SMS provider integration and webhook processing
- messages, conversation state, autoresponder, prompts, RAG/training data, and settings
- local/Google Calendar implementation for explicit legacy-mode testing only

FastAPI Bookings remains responsible for:

- services, providers, locations, and their relationships
- availability calculation
- client identification/creation
- booking creation and confirmation
- admin booking list, rescheduling, status transitions, and cancellation

## Key files

### New integration files

- `integrations/assistant-ui/` — copied, independently runnable Assistant project
- `integrations/assistant-ui/INTEGRATION.md` — concise integration boundary/runtime notes
- `integrations/assistant-ui/backend/booking_api.py` — HTTP compatibility adapter
- `integrations/assistant-ui/backend/test_booking_api.py` — adapter tests
- `integrations/assistant-ui/backend/.env.example` — documented booking API settings
- `integrations/assistant-ui/frontend/.env.example` — `VITE_API_BASE` example
- `integrations/assistant-ui/start.bat` — clears 5190/8026 and starts copied API/UI
- `integrations/assistant-ui/clear_ports.ps1` — targeted cleanup for 5190 and 8026
- `start-assistant-ui.bat` — repository-root convenience launcher
- `frontend/src/pages/admin/sms-assistant.tsx` — embedded admin workspace

### Modified integration touchpoints in the main repository

- `frontend/src/components/navigation.ts`
  - adds `SMS Assistant` under the main booking section
  - route: `/admin/sms-assistant`
- `frontend/src/App.tsx`
  - imports and renders `SmsAssistantPage`
- `start.bat`
  - now launches booking API, booking frontend, and copied Assistant suite

No main booking backend modules were intentionally changed for this integration.
Many `app/` files are currently modified for other ongoing booking work; preserve them.

## Booking API adapter contract

Implementation: `integrations/assistant-ui/backend/booking_api.py`

The adapter sends `X-Tenant` when configured. Admin calls also send `X-Token`.
For a localhost API, `mock-admin-token` is the development default if no token is set.
Do not rely on that default outside local development.

### Main booking endpoints consumed

- `GET /health`
- `GET /api/public/bootstrap`
- `GET /api/admin/services?page=1&page_size=100`
- `GET /api/public/availability?service_id=...&provider_id=...&date=...`
- `POST /api/public/clients`
- `POST /api/public/clients/identify?phone=...`
- `PUT /api/admin/clients/{id}`
- `POST /api/public/bookings`
- `GET /api/admin/bookings`
- `GET /api/admin/bookings/{id}`
- `PUT /api/admin/bookings/{id}`
- `POST /api/admin/bookings/{id}/confirm`
- `POST /api/admin/bookings/{id}/reschedule`
- `POST /api/admin/bookings/{id}/complete`
- `POST /api/admin/bookings/{id}/noshow`
- `POST /api/admin/bookings/{id}/cancel`

### Behavior

- Services come from public bootstrap and are mapped into the legacy Assistant shape.
- Admin service data is used to resolve service/provider relationships when a token is
  available; bootstrap and admin service results are cached for 30 seconds.
- The default service/provider/location environment variables take precedence.
- Without explicit defaults, the adapter selects an eligible provider and first
  location using existing relationship/schedule information.
- Availability is queried day-by-day for up to `BOOKING_API_AVAILABILITY_DAYS`
  (clamped to 1–10 days). A 429 after some slots have been collected ends the scan.
- Client identity is resolved by phone. If an admin token is available, a changed
  client name is updated through the admin API.
- Bookings are created through the public API and, when configured, immediately
  confirmed through the admin API.
- Admin booking rows are mapped back into the Assistant calendar's legacy schema.
- Remote write failures return an error. They do not silently fall back to local
  SQLite/Google Calendar storage, preventing split-brain bookings.

### Assistant compatibility routes switched to the adapter

In `integrations/assistant-ui/backend/main.py`:

- `GET /api/calendar/bookings`
- `PUT /api/calendar/bookings/{booking_id}`
- `DELETE /api/calendar/bookings/{booking_id}`
- `GET /api/calendar/freebusy`
- `GET /api/services`
- booking actions used by automated SMS scheduling flows

When `BOOKING_API_MODE=remote`, the Assistant service catalogue is read-only and its
service-create endpoint tells the caller that services are managed in FastAPI Bookings.

## Configuration

Copied backend example: `integrations/assistant-ui/backend/.env.example`

```dotenv
PORT=8026
BOOKING_API_MODE=remote
BOOKING_API_BASE_URL=http://127.0.0.1:8000
BOOKING_API_TENANT=simplydemo
BOOKING_API_TOKEN=mock-admin-token
BOOKING_API_TIMEOUT_SECONDS=30
BOOKING_API_AVAILABILITY_DAYS=7
BOOKING_API_DEFAULT_SERVICE_ID=
BOOKING_API_DEFAULT_PROVIDER_ID=
BOOKING_API_DEFAULT_LOCATION_ID=
BOOKING_API_AUTO_CONFIRM=true
```

Copied frontend:

```dotenv
VITE_API_BASE=http://localhost:8026
```

Optional main frontend configuration:

```dotenv
VITE_ASSISTANT_UI_URL=http://localhost:5190
```

If omitted, the admin page defaults to `http://localhost:5190`.

Never print or commit `.env`, OpenAI keys, SMS provider credentials, Google service
account JSON, or database files. The copied integration's `.gitignore` excludes
`.env*` except examples, `.venv`, `node_modules`, credentials, SQLite files, generated
training datasets, caches, and frontend build output.

## Ports

| Port | Intended service |
|---:|---|
| 8000 | Main FastAPI Bookings API |
| 7070 | Main booking Vite frontend |
| 8026 | Copied/integrated Assistant API |
| 5190 | Copied/integrated Assistant Vite frontend |
| 8025 | Original/legacy Assistant API; not part of the integrated runtime |

Do not configure the copied frontend to use 8025.

## Startup

From `F:\Projects\fastapi_bookings`:

```bat
start.bat
```

This launches all four intended services. To launch only the copied Assistant:

```bat
start-assistant-ui.bat
```

Manual commands:

```powershell
# Main API
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Main UI
npm run dev --prefix F:\Projects\fastapi_bookings\frontend

# Copied Assistant API
Set-Location F:\Projects\fastapi_bookings\integrations\assistant-ui\backend
.\.venv\Scripts\python.exe main.py

# Copied Assistant UI
Set-Location F:\Projects\fastapi_bookings\integrations\assistant-ui\frontend
npm run dev
```

The copied Assistant launcher deliberately kills only listeners on 5190 and 8026
before starting. Verify command lines afterward because an external watcher for the
original project may reclaim 5190.

## Validation baseline

Verified on 2026-08-23:

```powershell
Set-Location integrations\assistant-ui\backend
.\.venv\Scripts\python.exe -m pytest -q
# 122 passed, 2 deprecation warnings, 44.35s

Set-Location ..\frontend
npm run build
# success; 2161 modules; one >500 kB chunk-size warning
```

The two test warnings are currently non-blocking:

- Starlette TestClient/httpx deprecation warning
- Pydantic class-based `Config` deprecation at `main.py:1727`

Live HTTP checks returned 200 on 2026-08-23 for:

- main API `/health`
- main API `/api/public/bootstrap`
- main UI `/admin/sms-assistant`
- copied Assistant API `:8026/api/services`
- frontend `:5190/`

The main frontend production build was previously known to report numerous
TypeScript errors in the broader dirty worktree. Those errors were not attributed to
`sms-assistant.tsx`; re-run and triage before claiming a clean full-repository build.

## Important current runtime mismatch

At the 2026-08-23 check, all ports were listening, but port 5190 was owned by:

```text
F:\Projects\assistant-ui\frontend\...\vite.js --port 5190
```

That is the original frontend, whose `.env` points to port 8025. The copied frontend's
`.env` correctly points to 8026. Therefore a plain browser check of 5190 does not prove
the integrated frontend/API path is active.

Before further testing:

1. Stop the process on 5190 (and any watcher that restarts it).
2. Run `start-assistant-ui.bat` from the booking repository.
3. Verify the 5190 command line contains
   `F:\Projects\fastapi_bookings\integrations\assistant-ui\frontend`.
4. In browser developer tools, verify Assistant requests target 8026, not 8025.
5. Load `http://localhost:7070/admin/sms-assistant` and verify the iframe works.

At the same check, 8025 was the original Assistant API and 8026 responded with the
larger integrated service set. Treat 8025 as an unrelated legacy process.

## Git/worktree safety

Current branch at handoff:

```text
master at debfb0a
origin/master at debfb0a
```

The worktree is substantially dirty with unrelated, user-owned booking work, database
files, logs, generated files, and other features. Integration-specific status is:

```text
 M frontend/src/App.tsx
 M frontend/src/components/navigation.ts
 M start.bat
?? frontend/src/pages/admin/sms-assistant.tsx
?? integrations/assistant-ui/
?? start-assistant-ui.bat
```

`App.tsx` and `navigation.ts` also contain unrelated work (media, relationship views,
public upload routes, etc.). Do not replace either file wholesale or discard hunks.
`App.tsx` currently appears to contain duplicated route-selection clauses for packages,
resources, and relationship pages; investigate ownership before changing them.

Do not use `git reset --hard`, `git checkout --`, broad cleanup commands, or blanket
staging. If committing the integration, stage only reviewed integration paths/hunks.
The entire `integrations/assistant-ui` directory is currently untracked, while its
internal ignore rules keep secrets, environments, dependencies, and runtime data out.

## Recommended next actions

1. Reclaim port 5190 for the copied frontend and verify it calls 8026.
2. Perform an end-to-end test through the embedded admin page:
   - service list comes from FastAPI Bookings;
   - scheduling intent returns real booking availability;
   - selecting a slot creates one booking in the main booking API;
   - auto-confirm behavior matches configuration;
   - reschedule/status/cancel operations update that same main booking;
   - no parallel booking is written to the Assistant SQLite database.
3. Cancel/delete any test booking using the supported API so test data is documented.
4. Run the main frontend build and distinguish existing errors from integration errors.
5. Decide whether to keep the iframe boundary for now (safest) or later introduce a
   reverse proxy/same-origin route. Do not merge the two backends prematurely.
6. Gradually remove or hide duplicate Assistant booking-management UI only after the
   corresponding FastAPI Bookings workflow is accessible. Preserve SMS booking intent
   and conversation features that rely on the compatibility routes.
7. Replace the development token and tenant defaults with real environment-specific
   configuration before deployment.
8. Review the large copied tree before staging; include source/tests/docs/examples,
   exclude databases, credentials, `.env`, `.venv`, `node_modules`, caches, build
   output, and generated training data.

## Acceptance criteria

- The booking admin has a working `SMS Assistant` menu item.
- `/admin/sms-assistant` embeds the copied frontend and offers an external-tab link.
- Browser-to-Assistant traffic uses 5190 -> 8026.
- Assistant booking operations use 8026 -> main booking API on 8000.
- FastAPI Bookings is the only authoritative booking store in remote mode.
- Messaging/autoresponder/provider/RAG features continue to use Assistant-owned data.
- A booking API outage produces a visible error and never silently writes a local
  fallback booking.
- Original `F:\Projects\assistant-ui` remains intact.
- No unrelated dirty work or secrets are overwritten, deleted, or committed.

## Suggested prompt for a fresh agent

> Read `SMS-ASSISTANT-INTEGRATION-HANDOFF.md` and
> `integrations/assistant-ui/INTEGRATION.md` completely. Inspect the dirty worktree and
> preserve all unrelated changes. First correct the current runtime mismatch so port
> 5190 runs the copied frontend under this repository and calls the copied Assistant
> API on 8026. Then perform the documented end-to-end booking smoke test through the
> `/admin/sms-assistant` page. Keep the integration API-only and modular; do not import
> booking ORM models, access the booking database directly, delete the original
> `F:\Projects\assistant-ui`, or broadly refactor the main FastAPI app. Report exact
> commands, results, created test data, remaining failures, and files changed.
