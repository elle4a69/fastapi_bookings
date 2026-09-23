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
├── quick-tools-sheet.tsx    # Drawer for quick booking injection & fact extraction
├── settings.tsx             # Knowledge base RAG configuration & baseline AI settings
├── simulator.tsx            # Synthetic conversation runner & multi-turn scenario tests
└── triage-tab.tsx           # AI draft approval, rejection & modification interface
```

### Core Components & Sub-Tabs
- **SMS Assistant Master Shell ([`../sms-assistant.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms-assistant.tsx))**: Houses the primary tab navigator (`Inbox`, `Arrivals`, `Draft Triage`, `Bootcamp`, `Console`, `SMS Lines`, `Chatwoot`, `RAG & Prompts`, `Simulator`, `Diagnostics`). Supports event-driven cross-tab switching via the `sms-navigate-tab` custom event.
- **Live Inbox ([`inbox.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/inbox.tsx))**: Responsive dual-pane conversation navigation with polling, search, operational filters, unread/pin/block/AI state, optional priority/SLA/booking/arrival indicators, mixed message/event presentation, linked client/booking/arrival navigation, manual replies, and inline draft moderation. Unsupported operational actions remain disabled with an explanatory tooltip until their audited backend contracts exist.
- **Arrivals Board ([`arrivals-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/arrivals-tab.tsx))**: Displays arrived clients with elapsed waiting timers. Emits audio alerts when new arrivals register and provides one-click "Acknowledge" actions.
- **Triage Queue ([`triage-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/triage-tab.tsx))**: Human-in-the-loop draft queue displaying incoming snippet, proposed AI draft, and action buttons (`Approve & Send`, `Edit Draft`, `Discard`).
- **Scenario Simulator ([`simulator.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/simulator.tsx))**: Interactive test bench that fires synthetic webhook payloads against `/api/admin/sms/simulator/seed` and `/api/admin/sms/simulator/step`, enabling comprehensive regression tests without live carrier messaging.

---

## Setup, Configuration & Dependencies

### External Integrations
- **SMS Gateways**: Twilio / Telnyx numbers registered under `/admin/sms-assistant` (`SMS Lines` tab).
- **Chatwoot Messaging**: Configured via `chatwoot.tsx` with base URL, API access tokens, and webhook secrets.

### Backend Endpoints
- `GET /api/admin/sms/conversations`: Lists active SMS threads.
- `GET /api/admin/sms/conversations/{id}/messages`: Returns conversation history.
- `POST /api/admin/sms/conversations/{id}/messages`: Dispatches manual staff SMS.
- `POST /api/admin/sms/conversations/{id}/takeover`: Suspends automated AI responses.
- `GET /api/admin/sms/arrivals`: Polls active arrivals lobby sessions.
- `POST /api/admin/sms/arrivals/{id}/acknowledge`: Clears arrival alert.
- `GET /api/admin/sms/triage/drafts`: Lists drafts pending staff sign-off.
- `POST /api/admin/sms/simulator/seed`: Populates synthetic test fixtures.

---

## Core Workflows & Contracts

### 1. Human Takeover Workflow
1. Inbound SMS arrives; AI begins conversation under `state: 'auto-reply'`.
2. Staff clicks **Take Over** in `inbox.tsx`.
3. Frontend posts to `/api/admin/sms/conversations/{id}/takeover`.
4. Conversation transitions to `state: 'taken-over'`. The AI engine halts automated responses, leaving the channel entirely in staff control until explicitly released.

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
  - Notifies practitioner
  - Sends confirmation SMS to client
```

---

## Data Safety, Multi-Tenancy & PII Isolation

- **Carrier Safety Guarantee (Rule 3 & 4)**: The Scenario Simulator strictly utilizes synthetic fixtures (`client_phone: '0411000001'`) and mocks carrier delivery. It never contacts live phone numbers.
- **Provider & Tenant Isolation**: SMS accounts and conversations are strictly segmented by `tenant_id` and `provider_id`. Staff members only view messaging streams permitted by their organizational role.
- **Phone Number Masking**: Client contact numbers are masked or restricted to authenticated administrative staff to prevent unauthorized PII leakage.
- **Server-Owned Controls**: Pin, block, and automated-response settings come from the tenant-scoped API. They are not stored in `localStorage`, preventing stale or cross-session policy state.
- **No Silent Learning**: The inbox does not convert staff corrections or dynamic customer facts directly into durable AI knowledge. Correction and curator workflows require explicit audited backend contracts.
- **Booking Authority**: Messaging UI navigates to FastAPI Bookings booking management. It does not issue a direct booking write from incomplete conversation context.

---

## Known Issues, Edge Cases & Outstanding Work

- **Polling vs WebSockets**: The inbox and arrivals tabs currently use interval polling (4s to 10s intervals). Migration to a unified WebSocket stream for lower latency updates is planned.
- **Audio Autoplay Restrictions**: Certain modern browsers block the arrival chime until the user interacts with the page (clicks anywhere on the document). An explicit audio toggle is provided in the header.
- **Backend-dependent operations**: Escalation with reason, resolution notes, internal notes, correction evidence, conversation-level CSV/audit export, durable priority/SLA fields, and enriched booking/arrival indicators need dedicated tenant-scoped backend contracts. The inbox exposes these as disabled, labelled controls rather than issuing invented requests.
- **Review filter enrichment**: The `Needs review` filter consumes `needs_review` when provided by the conversation list contract and also recognises `info-needed`. A backend aggregate is still required for a complete cross-conversation draft count.

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
