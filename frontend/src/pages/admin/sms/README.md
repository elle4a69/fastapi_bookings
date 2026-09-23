# SMS Assistant Control Center

## Purpose & Scope
The `frontend/src/pages/admin/sms/` directory provides the command and operations center for the conversational SMS AI agent in **FastAPI Bookings**. It gives operational staff real-time visibility and intervention authority over inbound and outbound SMS communication.

Key responsibilities:
- **Live Two-Way Inbox**: Search and filter customer SMS threads, review unread and operational indicators, pause AI auto-replies, take over conversations, and dispatch manual responses.
- **Customer Arrivals Lobby**: Monitor check-ins, parking slot notices, and arrival timestamps with audio/visual alerts.
- **Draft Triage Queue**: Human-in-the-loop review station for pending AI drafts before message dispatch.
- **Persona Bootcamp & Prompt Playground**: Fine-tune agent tone, instructions, and business FAQs.
- **Scenario Simulator**: Execute synthetic customer conversations and arrival sequences without incurring carrier SMS fees.
- **Chatwoot Staff Messaging Integration**: Map provider lines to Chatwoot inboxes for external agent escalation.

---

## Architecture & Key Files

### Directory Layout
```
frontend/src/pages/admin/sms/
├── accounts.tsx             # SMS provider accounts (Twilio / Telnyx line setup)
├── agent-console-tab.tsx    # Live terminal console for internal agent state inspection
├── arrivals-tab.tsx         # Customer arrivals monitoring & acknowledgement board
├── bootcamp-tab.tsx         # Agent persona prompt tuning, guardrails & few-shot examples
├── chatwoot.tsx             # Chatwoot inbox mappings, webhook sync & token bindings
├── diagnostics.tsx          # Carrier latency, webhook health & message delivery telemetry
├── inbox.tsx                # Dual-pane SMS thread viewer, chat stream & manual composer
├── operations-state.ts      # Pure inbox filter and ordering rules
├── operations-state.test.ts # Regression tests for operations list state
├── settings.tsx             # Knowledge base RAG configuration & baseline AI settings
├── simulator.tsx            # Synthetic conversation runner & multi-turn scenario tests
└── triage-tab.tsx           # AI draft approval, rejection & modification interface
```

### Core Components & Sub-Tabs
- **SMS Assistant Master Shell ([`../sms-assistant.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms-assistant.tsx))**: Houses the primary tab navigator (`Inbox`, `Arrivals`, `Draft Triage`, `Bootcamp`, `Console`, `SMS Lines`, `Chatwoot`, `RAG & Prompts`, `Simulator`, `Diagnostics`). Supports event-driven cross-tab switching via the `sms-navigate-tab` custom event.
- **Live Inbox ([`inbox.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/inbox.tsx))**: Responsive dual-pane conversation navigation with polling, search, lifecycle filters, unread/pin/block/AI state, mixed message/note/event timeline, linked client/booking/arrival navigation, manual replies, inline draft moderation, internal notes, escalation, resolution, review-state clearing, and correction evidence. CSV export remains visibly unavailable until its backend contract is approved.
- **Arrivals Board ([`arrivals-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/arrivals-tab.tsx))**: Displays arrived clients with elapsed waiting timers. Emits audio alerts when new arrivals register and provides one-click "Acknowledge" actions.
- **Triage Queue ([`triage-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/triage-tab.tsx))**: Human-in-the-loop draft queue displaying incoming snippet, proposed AI draft, and action buttons (`Approve & Send`, `Edit Draft`, `Discard`).
- **Scenario Simulator ([`simulator.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/simulator.tsx))**: Dedicated test bench for synthetic webhook turns and scenario fixtures. Scenario creation is deliberately absent from the live inbox.

---

## Setup, Configuration & Dependencies

### External Integrations
- **SMS Gateways**: Twilio / Telnyx numbers registered under `/admin/sms-assistant` (`SMS Lines` tab).
- **Chatwoot Messaging**: `chatwoot.tsx` manages staff-visible configuration and status. Credentials remain server-side; raw tokens and webhook secrets must never be returned to the frontend.

### Backend Endpoints
- `GET /api/admin/sms/conversations`: Lists active SMS threads.
- `GET /api/admin/sms/conversations/{id}/timeline`: Returns chronological messages, internal notes, and structural audit events.
- `POST /api/admin/sms/conversations/{id}/messages`: Dispatches manual staff SMS.
- `POST /api/admin/sms/conversations/{id}/takeover`: Suspends automated AI responses.
- `POST /api/admin/sms/conversations/{id}/release`: Returns an eligible conversation to automated handling.
- `POST /api/admin/sms/conversations/{id}/escalate`: Escalates with a required reason.
- `POST /api/admin/sms/conversations/{id}/resolve`: Resolves with a required note.
- `POST /api/admin/sms/conversations/{id}/notes`: Adds an internal staff note.
- `POST /api/admin/sms/conversations/{id}/corrections`: Records correction evidence without changing live knowledge.
- `POST /api/admin/sms/conversations/{id}/review-state/clear`: Clears review-only state without deleting drafts.
- `PATCH /api/admin/sms/conversations/{id}/controls`: Persists pin, block, and per-conversation AI settings.
- `GET /api/admin/sms/conversations/drafts/queue`: Lists drafts pending staff sign-off.
- `POST /api/admin/sms/conversations/drafts/{id}/review`: Edits, approves, or discards one draft.
- `GET /api/admin/sms/arrivals`: Polls active arrivals lobby sessions.
- `POST /api/admin/sms/arrivals/{id}/acknowledge`: Clears arrival alert.

---

## Core Workflows & Contracts

### 1. Human Takeover Workflow
1. Inbound SMS arrives; AI begins conversation under `state: 'auto-reply'`.
2. Staff clicks **Take Over** in `inbox.tsx`.
3. Frontend posts to `/api/admin/sms/conversations/{id}/takeover`.
4. Conversation transitions to `state: 'taken-over'`. The AI engine halts automated responses, leaving the channel entirely in staff control until explicitly released.
5. Release is disabled in the UI while a contact is blocked or a conversation is in review, escalated, or resolved state. The server performs the final line/account safety check.

### 2. Conversation Controls and Draft Review

1. Pin, block, and AI enablement are persisted with `PATCH /api/admin/sms/conversations/{id}/controls`; browser-local state is not authoritative.
2. Blocking a contact disables the composer and the backend pauses automated handling.
3. Drafts are visually distinct from sent messages. Approve/discard use the draft moderation endpoints.
4. An edited draft is submitted once through `POST /api/admin/sms/conversations/drafts/{id}/review` with `action: approve`; the UI does not create a second staff message and then discard the original draft.
5. The inbox links to the authoritative FastAPI Bookings client, booking, and arrival workspaces. It does not create a booking from local form state or claim a booking is confirmed.

### 3. Arrival Notification Flow
```
Client sends SMS ("I'm here in bay 4")
                 │
                 ▼
  Backend extracts arrival intent
                 │
                 ▼
  Arrivals Lobby Board (arrivals-tab.tsx)
  - Flashes amber badge
  - Plays chime (if audio unmuted)
  - Displays client name, provider, and elapsed timer
                 │
                 ▼
  Staff clicks "Acknowledge"
  - Records acknowledgement
  - Clears the active arrival alert
```

---

## Data Safety, Multi-Tenancy & PII Isolation

- **Provider & Tenant Isolation**: SMS accounts and conversations are strictly segmented by `tenant_id` and `provider_id`. Staff members only view messaging streams permitted by their organizational role.
- **Customer Address Visibility**: Customer SMS addresses are visible only inside the authenticated administrative workspace; they are not written to browser logs or telemetry by the inbox.
- **Server-Owned Controls**: Pin, block, and automated-response settings come from the tenant-scoped API. They are not stored in `localStorage`, preventing stale or cross-session policy state.
- **No Silent Learning**: The correction endpoint records audit and learning evidence only. It never changes live AI knowledge; any later curator promotion is a separate, explicitly reviewed workflow.
- **Booking Authority**: Messaging UI navigates to FastAPI Bookings booking management. It does not issue a direct booking write from incomplete conversation context.
- **Stale-response Protection**: Timeline responses carry a local request sequence and are applied only if the same conversation remains selected, preventing A-to-B selection races from displaying or addressing the wrong customer.
- **Idempotent Manual Send**: One stable `client_request_id` is retained for a failed/retried manual-send attempt, and the composer is locked while a send is in flight.

---

## Known Issues, Edge Cases & Outstanding Work

- **Polling vs WebSockets**: The inbox and arrivals tabs currently use interval polling (4s to 10s intervals). Migration to a unified WebSocket stream for lower latency updates is planned.
- **Audio Autoplay Restrictions**: Certain modern browsers block the arrival chime until the user interacts with the page (clicks anywhere on the document). An explicit audio toggle is provided in the header.
- **CSV export**: Conversation/audit CSV export remains unavailable pending an approved tenant-scoped backend contract and reporting authorization model.
- **List enrichment**: Durable priority/SLA, last-message preview, and booking/arrival indicator fields are optional UI capabilities but are not yet present in the base conversation response.
- **Review filter enrichment**: The `Needs review` filter recognises the authoritative `needs-review` lifecycle state and consumes `needs_review` if a future list aggregate supplies it.
- **Simulator isolation**: The Simulator tab must be configured with labelled synthetic accounts and data. Its webhook/account isolation requires separate combined runtime verification before it can be described as incapable of live carrier delivery.
- **Backend integration dependency**: Timeline and audited staff action UI depends on the corresponding FastAPI routes landing in the backend commit. Verify the combined tree before release.

---

## Verification & Testing Commands

```bash
# Typecheck SMS module components
cd frontend
npm run build

# Run Oxlint across SMS assistant files
npx oxlint src/pages/admin/sms

# Run focused operations-list regression tests
node --experimental-strip-types --test src/pages/admin/sms/operations-state.test.ts
```
