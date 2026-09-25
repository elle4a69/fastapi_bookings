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
├── accounts.tsx                # SMS provider accounts (Twilio / Telnyx line setup)
├── agent-console-tab.tsx       # Live terminal console for internal agent state inspection
├── arrivals-tab.tsx            # Customer arrivals monitoring & acknowledgement board
├── assistant-bootcamp-page.tsx # Dedicated 1:1 replica of Assistant UI BootcampView (3-pane layout, style lab, 12 personas)
├── assistant-messages-page.tsx # Dedicated 1:1 replica of Assistant UI MobileInboxView
├── assistant-thread-panel.tsx  # Unified reusable thread workspace component (live messages & bootcamp simulation)
├── bootcamp-settings-tab.tsx   # Isolated Bootcamp settings (agent config, system prompts, learned facts, style preview)
├── bootcamp-tab.tsx            # Agent persona prompt tuning, guardrails & few-shot examples
├── chatwoot.tsx                # Chatwoot inbox mappings, webhook sync & token bindings
├── diagnostics.tsx             # Carrier latency, webhook health & message delivery telemetry
├── inbox.tsx                   # 3-pane SMS triage workspace, timeline stream, context & notes panel
├── operations-state.ts         # Pure inbox filter and ordering rules
├── operations-state.test.ts    # Regression tests for operations list state
├── quick-tools-sheet.tsx       # Quick tools bottom sheet with 5 programmable macros & calendar slot picker
├── settings.tsx                # Knowledge base RAG configuration, curator proposals & AI settings
├── simulator.tsx               # Synthetic conversation runner & multi-turn scenario tests
└── triage-tab.tsx              # AI draft approval, rejection & modification interface
```

### Core Components & Sub-Tabs
- **SMS Assistant Master Shell ([`../sms-assistant.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms-assistant.tsx))**: Houses the primary tab navigator (`Messages`, `Inbox`, `Arrivals`, `Draft Triage`, `Bootcamp`, `Camp Settings`, `Console`, `SMS Lines`, `Chatwoot`, `RAG & Prompts`, `Simulator`, `Diagnostics`). Supports event-driven cross-tab switching via the `sms-navigate-tab` custom event. Features an interactive horizontal tabs slider docked flush against the top border with a thin divider (`border-b border-border/80 bg-card/60 backdrop-blur-xs`), equipped with Left and Right slide/scroll buttons, edge gradient fade masks indicating off-screen overflow, strict non-wrapping tabs (`flex-nowrap shrink-0 whitespace-nowrap`), and automatic centering of active tabs. Docks flush within the route-aware operational viewport with zero outer padding (`p-0`) and zero tabs spacing bloat (`space-y-0`). Includes the persistent mobile bottom navigation bar (`data-testid="mobile-bottom-nav"`) spanning 7 mobile tabs (`Messages`, `Console`, `Arrivals`, `Triage`, `SMS Sim`, `Camp`, `Settings`) docking flush beneath the composer.
- **Unified Assistant Thread Workspace ([`assistant-thread-panel.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/assistant-thread-panel.tsx))**: Reusable, theme-aware conversation stream component shared between the live Messages tab and Tori Boot Camp. Provides a unified active conversation workspace:
  - Header bar with title, subtitle, back button, pin/block badges, and AI On/Off takeover toggle with compact vertical padding (`px-3 py-2`).
  - Expandable high-visibility red Information Request Accordion (`bg-red-700 hover:bg-red-800 text-white`) with prompt viewer, staff ground-truth textarea, and "Send reply and save learning" submission.
  - Authentic chat timeline with customer bubbles, staff manual reply bubbles, AI sent replies with AI Correction Flag button, AI draft cards (inline editing, approve, discard), arrival event pills, and simulation thinking pulse indicators:
    - **Header Timestamp Placement**: Timestamps are docked on the top-right of message bubbles across Customer Inbound, Staff Replies, AI Sent messages (with inline Flag button), and AI Draft cards (alongside "Pending approval"), removing legacy bottom timestamp rows.
    - **Compact Typography & Padding**: Standardized `text-[13px] leading-snug` body typography across all bubble types with tightened container padding (`px-3 py-2`).
  - Compact message composer & response input:
    - Outer container with slim padding (`p-2 space-y-1`).
    - Rounded auto-expanding textarea (`rounded-2xl px-3.5 py-1.5 text-[13px] min-h-[38px] max-h-32 leading-snug`) with auto-grow capped at 128px height.
    - Compact circular green send button (`h-[38px] w-[38px]` with `h-3.5 w-3.5` `<Send />` icon) supporting `Cmd+Enter` / `Ctrl+Enter`.
  - Mode-aware bottom 5-button toolbar (`showBottomToolbar?: boolean`, default `mode !== "bootcamp"`): Renders `AI On/Off`, `Tools` (`QuickToolsSheet`), `Booking` (deep-linking), `Pin/Unpin`, and `Block/Unblock` in Live SMS mode while cleanly suppressing the toolbar in Bootcamp mode.
  - AI Correction Flag Modal: Dialog prompting for correction reason and corrected ideal wording, submitting ground-truth evidence to learning queues without mutating durable knowledge.
- **Dedicated Assistant Messages Replica ([`assistant-messages-page.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/assistant-messages-page.tsx))**: Standalone 1:1 replica of Assistant UI's `MobileInboxView` with complete dark-theme and semantic-token compliance. Features a mobile-first centered card layout (`max-w-3xl bg-card text-card-foreground border-x border-border shadow-md`), compact list header with search and action pills (`px-3 py-2`), global Catch-up refresh button, global AI toggle pill, and Train toggle pill. In active conversation mode, seamlessly embeds `<AssistantThreadPanel mode="live" ... />` wired to live SMS endpoints and draft review actions.
- **Live Inbox ([`inbox.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/inbox.tsx))**: Full 3-pane triage workspace matching Assistant UI layout conventions. Features Pane 1 (searchable, state-filtered conversation list), Pane 2 (timeline stream with AI draft card moderation, audit events, manual composer with quick-tools trigger `<Zap />`, and `Cmd+Enter`/`Ctrl+Enter` dispatch), and Pane 3 (persistent right client context, linked booking/arrival snippet, chronological internal notes stream, and inline note composer). Supports desktop collapse/expand toggle and responsive mobile overlay drawer.
- **Quick Tools Bottom Sheet ([`quick-tools-sheet.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/quick-tools-sheet.tsx))**: Bottom sheet overlay providing 5 programmable macro buttons (with long-press customization up to 8 chars) and real-time calendar availability inspection grouped by day and service duration (15m–90m). Selecting any macro or slot automatically pastes text into the composer and closes the sheet.
- **Arrivals Board ([`arrivals-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/arrivals-tab.tsx))**: Displays arrived clients with elapsed waiting timers. Emits audio alerts when new arrivals register and provides one-click "Acknowledge" actions.
- **Triage Queue ([`triage-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/triage-tab.tsx))**: Human-in-the-loop draft triage workspace consuming `GET /api/admin/sms/conversations/drafts/queue`. Displays customer speech bubbles for inbound inquiry context, amber-dashed proposed AI drafts with character/segment counters, individual approve (`/messages/{id}/approve`), discard (`/messages/{id}/discard`), inline editing with single-turn review (`/drafts/{id}/review`), and multi-select bulk discard (`/drafts/bulk/discard`) with audited reasons.
- **Dedicated Assistant Bootcamp Page ([`assistant-bootcamp-page.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/assistant-bootcamp-page.tsx))**: Faithful 1:1 reproduction of Assistant UI's `BootcampView.tsx` with a responsive 3-column layout:
  - **Header Toolbar**: Title **"Tori Boot Camp"**, subtitle *"Simulated only · paced updates · no SMS or bookings"*, run status pill (`running` [emerald], `paused` [amber], `failed` [red], `completed`/`stopped` [slate], `idle`), action buttons (`Start`, `Pause`, `Resume`, `Stop`, `Reset`), "Bootcamp Settings" shortcut button (opens the isolated settings sheet or navigates to settings), and real-time notice banner.
  - **Left Column (Personas & Turn Controls)**: Header with dynamic thread counter, select all/clear controls, mobile-responsive persona selector for screens `< lg`, scrollable list of 12 persona cards (`cranky-carl`, `sarcastic-sam`, `deadpan-dave`, `passive-paul`, `happy-harry`, `nervous-neil`, `time-waster-terry`, `chatty-charlie`, `budget-bob`, `curious-colin`, `discreet-dominic`, `pushy-pete`) with category badges, description snippets, selection checkboxes, active thread highlights (`border-indigo-500 bg-indigo-500/10`), warning icons (`AlertTriangle`) when handoff is required, and turns slider (range 2 to 12, default 5) with live numerical readout.
  - **Middle Column (Interactive Conversation Stream)**: Embeds the unified `<AssistantThreadPanel mode="bootcamp" ... />`, rendering authentic bubble styling, live thinking pulse animation during turn processing, the high-visibility red Information Request Accordion for ground-truth learning capture (`POST /api/admin/sms/bootcamp/conversations/{id}/information-request/respond`), AI Correction Flagging (`POST /api/admin/sms/bootcamp/conversations/{id}/corrections`), and staff manual prompt injection.
  - **Right Column (Style Laboratory)**: Calibrate Tori's behavioral persona across 8 sliders (0 to 5 scale, step 1): `Flirtiness`, `Cheerfulness`, `Wit`, `Sarcasm`, `Warmth`, `Directness`, `Chattiness`, `Patience`. Values affect Boot Camp only until deliberately applied. Features **"Apply to Tori"** (`Save` icon) posting to `/api/admin/sms/bootcamp/profile/apply` and **"Undo"** (`Undo2` icon) posting to `/api/admin/sms/bootcamp/profile/undo`.
  - **Live Simulation Pacing & Polling**: Paces multi-turn simulated exchanges and polls `GET /api/admin/sms/bootcamp/runs/latest` every 2.5 seconds when active.
- **Isolated Bootcamp Settings ([`bootcamp-settings-tab.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/sms/bootcamp-settings-tab.tsx))**:
  Clean settings view completely isolated from FastAPI Bookings's main business settings:
  - **Agent Configuration**: Agent name (default "Tori"), synthetic model identifier (`gpt-4o-mini`, etc.), and active role description.
  - **Prompts & Instructions**: Monospace system prompt template editor supporting template variables (`{agent_name}`, `{traits}`, `{business_name}`).
  - **Training & Reference Data**: Custom training notes and learned facts editor captured during bootcamp information requests.
  - **Behavioral Settings Preview**: Readout comparing current active calibration vs prior applied profile across the 8 style dimensions.
  - **Save & Reset Actions**: Consumes `GET /api/admin/sms/bootcamp/settings` and `PUT /api/admin/sms/bootcamp/settings` with sandboxed fallback.
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
- `POST /api/admin/sms/conversations/drafts/bulk/discard`: Discards multiple drafts in bulk with an audited reason.
- `POST /api/admin/sms/conversations/messages/{id}/approve`: Approves and queues a draft for dispatch.
- `POST /api/admin/sms/conversations/messages/{id}/discard`: Discards a single draft.
- `GET /api/admin/sms/arrivals`: Polls active arrivals lobby sessions.
- `POST /api/admin/sms/arrivals/{id}/acknowledge`: Clears arrival alert.
- `GET /api/admin/sms/conversations/quick-tools`: Fetches the 5 programmable macro slots (0-4) for the active tenant/operator.
- `POST /api/admin/sms/conversations/quick-tools`: Saves or updates an individual macro slot (`{ slot_index, label, content }`).
- `GET /api/admin/sms/knowledge/proposals`: Lists pending knowledge proposals awaiting human curator review.
- `POST /api/admin/sms/knowledge/proposals/{id}/resolve`: Resolves a proposal with `{ action: 'approve' | 'dismiss' }`.
- `GET /api/admin/sms/curator/status`: Retrieves autonomous curation statistics (active memories, superseded memories, pending proposals, processed learning events).
- `POST /api/admin/sms/curator/process`: Triggers autonomous curation on pending learning events for the active tenant.
- `POST /api/admin/sms/conversations/{id}/answer-info-request`: Submits staff answer to an information request, queuing learning proposals for curator review.
- `GET /api/admin/sms/bootcamp/scenarios`: Returns available scenario packs (`basic_communication`, `booking`, `knowledge_gaps`) and scenarios for targeted testing.
- `POST /api/admin/sms/bootcamp/runs`: Initiates a simulated test run with selected personas, turns, autonomy level, scenario IDs, and style calibration.
- `POST /api/admin/sms/bootcamp/runs/start`: Legacy fallback runner endpoint.
- `POST /api/admin/sms/bootcamp/runs/pause`: Pauses active test run execution.
- `POST /api/admin/sms/bootcamp/runs/resume`: Resumes paused test runs.
- `POST /api/admin/sms/bootcamp/runs/stop`: Stops running test runs.
- `DELETE /api/admin/sms/bootcamp/runs`: Clears all simulated test run threads and resets state.
- `GET /api/admin/sms/bootcamp/runs/latest`: Polls current test run state and conversation progress.
- `POST /api/admin/sms/bootcamp/conversations/{id}/information-request/respond`: Submits owner ground-truth lesson for an information request handoff.
- `POST /api/admin/sms/bootcamp/conversations/{id}/drafts/{message_id}/review`: Reviews, approves, edits, or discards simulation drafts, advancing the turn upon approval.
- `POST /api/admin/sms/bootcamp/profile/apply`: Applies Style Laboratory calibration to Tori.
- `POST /api/admin/sms/bootcamp/profile/undo`: Reverts to the previous style calibration.
- `GET /api/admin/sms/bootcamp/settings`: Fetches isolated Bootcamp agent settings and prompt templates.
- `PUT /api/admin/sms/bootcamp/settings`: Persists isolated Bootcamp agent settings and prompt templates.

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

### 3. Standalone Draft Triage Queue & Bulk Actions Workflow

1. **Direct Queue Ingestion**: The standalone triage tab loads pending drafts directly via `GET /api/admin/sms/conversations/drafts/queue`, eliminating previous N+1 query loops over conversations.
2. **Empty State Integrity**: When no drafts are pending, renders an authoritative empty state ("All caught up! No pending AI drafts to review.") with zero mock fallback data.
3. **Customer Inbound Context**: Inbound inquiries (`inbound_snippet` or `customer_message`) are rendered in dedicated customer speech bubbles above the proposed AI draft. Missing context on selected drafts is lazily populated from the conversation timeline.
4. **Draft Moderation & Amber-Dashed Styling**: Proposed drafts mirror inbox styling (`bg-amber-500/10 border-dashed border-amber-500/40`), display "AI Draft" badges, and include character and segment counters (160 characters per SMS segment, max 1600 characters).
5. **Audited Single-Turn Edits**: In-place edits are submitted and approved via `POST /api/admin/sms/conversations/drafts/{id}/review` with `{ action: 'approve', text }`. This maintains draft audit lineage, dispatches the edited message, and avoids unintended human takeover transitions.
6. **Individual & Bulk Moderation Actions**:
   - Single approval: `POST /api/admin/sms/conversations/messages/{id}/approve`
   - Single discard: `POST /api/admin/sms/conversations/messages/{id}/discard`
   - Multi-select bulk discard: Operators select multiple draft cards or click "Select All" to trigger `POST /api/admin/sms/conversations/drafts/bulk/discard` with `{ message_ids, reason }`. A mandatory modal dialog captures the audited reason before execution.

### 4. Arrival Notification Flow
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

### 5. 3-Pane Workspace & Internal Notes Workflow
1. **Persistent 3-Pane Layout**:
   - **Pane 1 (Left Sidebar, `w-80 border-r`)**: Real-time conversation list with search, status filters (`All`, `Automatic`, `Needs review`, `Human`, `Escalated`, `Resolved`), unread counters, pin badges, and SLA/booking indicators.
   - **Pane 2 (Center Workspace, `flex-1 min-w-0`)**: Conversation header with AI auto-reply toggling, quick action buttons, chronological message/event/note timeline, and manual SMS composer.
   - **Pane 3 (Right Panel, `w-80 border-l bg-muted/10`)**: Persistent client profile (name, phone, client ID, provider, line/account badges), active booking and arrival lobby snippets with deep links, dedicated internal staff notes stream, and inline note composer.
2. **Desktop Collapse & Mobile Drawer**:
   - On desktop viewports (`lg+`), Pane 3 is displayed inline and can be collapsed/expanded via the `PanelRight` header button (`showNotesPanel`).
   - On mobile and narrow viewports, the header provides a dedicated notes button that opens a slide-over notes drawer (`showNotesMobile`) without crowding message history.
3. **Internal Notes Stream & Submission**:
   - Filtered from the timeline (`kind === 'internal_note'`), notes display author/staff badges, precise timestamps, and note content in a scrollable list.
   - Inline composer allows staff to enter internal notes with a `Ctrl+Enter` / `Cmd+Enter` keyboard shortcut.
   - Note dispatch calls `POST /api/admin/sms/conversations/{id}/notes`, appends the note optimistically, and refreshes the timeline. Notes remain strictly internal to staff and are never dispatched to customer carriers.
4. **AI Draft Card Moderation & Keyboard Parity**:
   - AI drafts stand out with amber dashed borders (`bg-amber-500/10 border-dashed border-amber-500/40`), clear "AI Draft" badge, and one-click actions: **Approve & Send** (`POST /api/admin/sms/conversations/messages/{id}/approve`), **Edit Draft** (inline textarea with single-turn approval submission), and **Discard** (`POST /api/admin/sms/conversations/messages/{id}/discard`).
   - Manual SMS composer supports `Cmd+Enter` / `Ctrl+Enter` or `Enter` for rapid keyboard dispatch.

### 6. Assistant Quick Tools & Calendar Availability Insertion

1. **Programmable Macros (5 Slots)**:
   - Operators access 5 programmable macro keys (`0` to `4`) backed by `GET /api/admin/sms/conversations/quick-tools`.
   - Macros provide instantaneous standard responses (e.g. Pricing, Location, Hours, Cancellation Policy, Thanks).
   - Tapping any macro calls `onInsert(macro.content)`, pastes the snippet cleanly into the manual SMS composer (`composeText`), and immediately dismisses the sheet for rapid dispatch.
   - Long-pressing (500ms) or right-clicking any macro card triggers the macro editor modal dialog.
   - The label is strictly validated and capped at 8 characters (`maxLength={8}`) to preserve grid aesthetics on both desktop and mobile viewports.
   - Updates post individually to `POST /api/admin/sms/conversations/quick-tools` with payload `{ slot_index, label, content }`, persisting per-operator overrides in PostgreSQL while mirroring to `localStorage` as an offline fallback.

2. **Live Calendar Availability Inspector**:
   - The expanding calendar drawer fetches live catalog services and existing bookings to generate real-time opening slots across the next 5 days.
   - Operators can toggle service duration filters (15m, 30m, 45m, 60m, 90m) to recalculate slot conflicts dynamically.
   - Clicking an available slot immediately formats a natural client booking invitation (*"We have an available appointment slot on {day} ({date}) at {time} for a {duration}-min session. Would you like me to book this for you?"*), inserts it into the composer, and closes the quick tools drawer.

3. **Composer Trigger Button**:
   - A dedicated quick tools trigger button (`<Button variant="ghost" size="icon" onClick={() => setShowQuickTools(true)}><Zap className="h-4 w-4" /></Button>`) is embedded directly in the message composer toolbar next to the Send button.

### 7. Governed Knowledge Curator Review Workflow

1. **Governed Knowledge Ingestion**:
   - In accordance with Section 3 of `AGENTS.md`, conversation transcripts and operator corrections *never* silently or automatically mutate durable AI knowledge.
   - Candidate facts, ambiguities, and business changes detected during conversation analysis enter a review queue via `GET /api/admin/sms/knowledge/proposals`.
2. **Proposal Taxonomy & Visual Differentiation**:
   - `gap`: Missing operational or domain knowledge identified from unanswered customer inquiries (amber badge).
   - `conflict`: Contradictory business rules or schedule collisions requiring explicit staff resolution (rose badge).
   - `duplicate`: Redundant knowledge variations detected against existing durable memory (slate badge).
   - `add`: New candidate durable facts proposed for general RAG retrieval (emerald badge).
   - `stale` / `supersede`: Outdated information candidates flagged for archival or replacement (purple badge).
3. **Autonomous Curator Engine Status Card in `settings.tsx`**:
   - Docked prominently at the top of the **Curator Proposals** tab, consuming `GET /api/admin/sms/curator/status`.
   - Real-time 4-metric telemetry grid:
     - **Active Memories**: Approved facts actively informing AI responder context.
     - **Superseded Memories**: Outdated knowledge versions safely archived with provenance preserved.
     - **Pending Proposals**: Proposals awaiting operator sign-off.
     - **Processed Learning Events**: Total ingested learning events evaluated by the governance pipeline.
   - **Run Autonomous Curation Action**: Operators trigger batch evaluation of pending learning events via `POST /api/admin/sms/curator/process` with `{ limit: 50 }`. Emits a toast notification summarizing processed events and curated/superseded memory counts, then reactively refreshes curator status and proposal lists.
4. **Curator Review Station & Audited Resolution**:
   - Displayed under the **Curator Proposals** tab with real-time pending counter badge and a notification callout on the Shared Knowledge tab.
   - Each pending proposal card renders the original customer inquiry, proposed durable response text, reason code, and curator confidence score.
   - **Approve**: Calls `POST /api/admin/sms/knowledge/proposals/{id}/resolve` with `{ action: 'approve' }`. Promotes the proposed text into durable memory and automatically refreshes the active knowledge base.
   - **Dismiss**: Calls `POST /api/admin/sms/knowledge/proposals/{id}/resolve` with `{ action: 'dismiss' }`. Closes the proposal without altering tenant RAG context.

### 8. Assistant Messages Replica & Mobile Bottom Navigation Workflow

1. **Standalone 1:1 Messages View (`assistant-messages-page.tsx`)**:
   - Replicates the exact UX, visual structure, and component styling of Assistant UI's `MobileInboxView` with strict semantic theme tokens supporting light and dark modes.
   - **Mobile-First Card Container**: Centered card (`max-w-3xl bg-card text-card-foreground border-x border-border shadow-md`) nested inside an outer wrapper (`flex-1 w-full flex flex-col overflow-hidden bg-background text-foreground`), filling vertical height cleanly without floating gaps.
   - **Header State**: Renders compact list header (`px-3 py-2`) with search bar (`bg-muted/60 dark:bg-muted/30 border-border text-foreground placeholder:text-muted-foreground`), global Catch-up refresh button (`border-border bg-muted/40 hover:bg-muted text-foreground`), global AI toggle pill, and Train toggle pill when viewing the conversation list; renders round back button (`bg-muted text-foreground hover:bg-muted/80`), customer contact header (`SMS · Active Chat`, title `text-foreground`), and thread AI status pill with compact padding (`px-3 py-2`) when inside an active thread.
   - **Thread List**: Renders gradient avatars (`from-indigo-500 to-violet-600`), customer name/phone (`text-foreground font-semibold`), preview snippet (`text-muted-foreground`), time, unread badge pill (`bg-emerald-500`), and badges with theme-aware borders for `SMS`, `Arrived`, `Draft`, and `Blocked`.
   - **Chat Timeline Viewport**: Structured viewport (`flex min-h-0 flex-1 flex-col bg-muted/30 dark:bg-background/80 overflow-y-auto px-3 py-3 space-y-2.5`) with authentic theme-aware bubble styling:
     - Customer inbound SMS: `self-start max-w-[82%] rounded-2xl rounded-bl-md bg-card dark:bg-muted/80 text-foreground border border-border/80 shadow-xs px-3.5 py-2.5 text-[14px]`
     - Staff manual reply: `self-end max-w-[82%] rounded-2xl rounded-br-md bg-slate-700 dark:bg-slate-800 text-white shadow-xs px-3.5 py-2.5 text-[14px]`
     - AI auto-reply (sent): `self-end max-w-[82%] rounded-2xl rounded-br-md bg-blue-600 dark:bg-blue-700 text-white shadow-xs px-3.5 py-2.5 text-[14px]` with top label `AI` and flag button opening the correction evidence modal (`POST /api/admin/sms/conversations/{id}/corrections`).
     - AI draft (unsent/pending): `self-end max-w-[85%] rounded-2xl rounded-br-md border border-blue-400/60 dark:border-blue-700/60 bg-blue-50/80 dark:bg-blue-950/40 text-foreground shadow-xs px-3.5 py-2.5` with top label `AI draft—not sent`, inline editable textarea, and action buttons: `[Edit]`, `[Discard]`, `[Send]`.
     - Client Arrived notification pill: Centered badge `border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-full px-3 py-1 text-xs font-bold shadow-xs`.
   - **Information Request Accordion**:
     - High-visibility red accordion bar (`bg-red-700 hover:bg-red-800 text-white text-xs font-black uppercase tracking-wider py-2.5 px-4 rounded-lg cursor-pointer flex justify-between items-center`) displayed when a thread requires staff information input.
     - Expanding drawer with prompt, staff ground-truth textarea, `[Send reply and save learning]`, and `[Remove request]`. Submissions call `POST /api/admin/sms/conversations/{id}/answer-info-request`.
   - **Composer**: Auto-expanding textarea (`bg-card dark:bg-muted/30 border-border text-foreground placeholder:text-muted-foreground focus:border-indigo-500 focus:bg-card focus:outline-none leading-snug flex-1 rounded-3xl border px-4 py-2.5 text-[14px] max-h-36 min-h-11 resize-none`) with circular green send button (`grid h-11 w-11 shrink-0 place-items-center rounded-full bg-emerald-600 text-white shadow-sm active:scale-95`) supporting `Cmd+Enter` / `Ctrl+Enter` dispatch.
   - **Bottom 5-Button Toolbar**: 5-column grid (`grid grid-cols-5 gap-1 pt-1 pb-1 border-t border-border/60`) providing buttons styled with `bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted` for `AI On / AI Off` takeover toggle, `Tools` (`QuickToolsSheet`), `Booking` (deep-linking to `/admin/bookings`), `Pin / Unpin`, and `Block / Unblock`.

2. **Mobile Bottom Navigation Bar & Horizontal Tabs Slider (`sms-assistant.tsx`)**:
   - Fixed mobile bottom navigation bar (`data-testid="mobile-bottom-nav"`, `sm:hidden z-40 flex h-16 w-full shrink-0 border-t border-slate-800 bg-slate-900 text-white shadow-lg select-none`).
   - 7 primary mobile operational destinations:
     - `messages` -> "Messages" (`MessagesSquare`)
     - `inbox` -> "Console" (`UserCheck`)
     - `arrivals` -> "Arrivals" (`DoorOpen`)
     - `triage` -> "Triage" (`Sparkles`)
     - `simulator` -> "SMS Sim" (`Smartphone`)
     - `bootcamp` -> "Camp" (`Bot`)
     - `settings` -> "Settings" (`Settings`)
   - Container layout uses `flex-1 min-h-0` so the message composer docks directly atop the bottom navigation bar without overlapping, clipping, or requiring manual padding spacers.
   - Interactive Horizontal Tabs Slider:
     - Wraps the top `<TabsList>` in a smooth-scrolling horizontal container with Left and Right chevron buttons (`scrollBy({ left: +/-200, behavior: 'smooth' })`).
     - Includes dynamic edge gradient fade masks that visually signal off-screen overflow when tabs can be scrolled.
     - Enforces strict non-wrapping tabs (`flex-nowrap shrink-0 whitespace-nowrap`).
     - Employs a `ResizeObserver` and scroll listener to enable/disable arrow controls reactively.
     - Automatically centers any active tab into view when selected via URL parameter or programmatic event (`activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })`).
   - Vertically streamlined layout: Redundant page title/subtitle header panel was removed to eliminate duplicate branding and reclaim vertical viewport real-estate for conversation timelines, queues, and composers.

### 9. Assistant Bootcamp Simulation & Information Request Learning Loop

1. **Persona Selection, Multi-Turn Setup & Run Configuration**:
   - Operators select from 12 distinct customer personas covering diverse customer behaviors (`cranky-carl`, `sarcastic-sam`, `deadpan-dave`, `passive-paul`, `happy-harry`, `nervous-neil`, `time-waster-terry`, `chatty-charlie`, `budget-bob`, `curious-colin`, `discreet-dominic`, `pushy-pete`).
   - The turns slider sets conversation depth from 2 to 12 turns (default: 5 turns).
   - **Autonomy Level Selector (Spec 37)**: Compact 3-option segmented control (`Level 1`, `Level 2`, `Level 3`):
     - `Level 1` (Review Every Turn): Tori generates unsent drafts on every turn, pausing the thread until operator approval/editing.
     - `Level 2` (Semi-Autonomous, Default): Automatically dispatches replies, pausing only on handoffs and knowledge gaps.
     - `Level 3` (Full Simulation): Fully autonomous multi-turn execution without human intervention.
   - **Scenario Pack Selector (Specs 33, 34)**: Dropdown consuming `GET /api/admin/sms/bootcamp/scenarios` allowing "All Scenarios" (balanced test distribution) or targeted scenario testing (e.g., *Pricing Enquiry*, *Unavailable Slot Negotiation*, *Booking Reschedule*, *Late Arrival Notice*, *Unknown Personal Preference*, *Impatient Client*, *Refund Policy Exception*).
   - Thread list indicates turn progression (`Turn X/Y`) and status (`idle`, `running`, `paused`, `completed`, `needs_handoff`).

2. **Style Laboratory Calibration**:
   - Calibrates 8 personality traits on a 0 to 5 scale: `Flirtiness`, `Cheerfulness`, `Wit`, `Sarcasm`, `Warmth`, `Directness`, `Chattiness`, and `Patience`.
   - Sliders dynamically reshape Tori's wording in real-time simulated exchanges without modifying production settings until explicitly saved.
   - **Apply to Tori**: Posts to `/api/admin/sms/bootcamp/profile/apply` and stores the active calibration for undo.
   - **Undo**: Posts to `/api/admin/sms/bootcamp/profile/undo` to restore previous calibration.

3. **Multi-Thread Simulated Execution**:
   - Clicking **Start** initiates multi-turn exchanges across all selected personas, dispatching payload `{ persona_ids, max_turns, style_profile, autonomy_level, scenario_ids }` to `POST /api/admin/sms/bootcamp/runs`.
   - Run status is prominently tracked via the header Status Pill (`running` [emerald], `paused` [amber], `failed` [red], `completed`/`stopped` [slate]).
   - Includes real-time simulation controls: **Pause**, **Resume**, **Stop**, and **Reset** (clearing all run threads via `DELETE /api/admin/sms/bootcamp/runs`).
   - Automatic polling and pacing executes every 2.5 seconds against `GET /api/admin/sms/bootcamp/runs/latest`.

4. **Unified Thread Panel & Tori Information Request Workflow**:
   - The middle column of Bootcamp embeds the shared `<AssistantThreadPanel mode="bootcamp" ... />`, replicating the exact look, feel, timeline bubbles, composer, and bottom toolbar used in the live Messages tab.
   - When a persona probes an unconfirmed policy, refund exception, or technical equipment specification (such as `cranky-carl` requesting an exception for a same-day no-show or `curious-colin` requesting autoclave spore testing specs), Tori flags the thread with `needsHandoff: true`.
   - The thread workspace triggers the high-visibility red **Information Request Accordion** (`bg-red-700 hover:bg-red-800 text-white`) displaying the knowledge gap prompt.
   - Operators input the ground-truth business fact into the staff answer textarea and click *"Send reply and save learning"*.
   - Frontend calls `POST /api/admin/sms/bootcamp/conversations/{id}/information-request/respond` with `{ information: answer }`.
   - Tori absorbs the lesson fact, clears the handoff state, retries the response incorporating the newly learned fact, and resumes multi-turn simulation.

5. **AI Correction Flagging & In-Place Learning Loop**:
   - Sent AI responses in Bootcamp display the **Flag** icon button.
   - Clicking Flag opens the AI Correction Flag Modal, allowing operators to enter the correction reason and corrected ideal wording.
   - Submissions post to `POST /api/admin/sms/bootcamp/conversations/{id}/corrections` with `{ message_id, reason, corrected_wording }`, triggering `toast.success("Correction saved to learning queue")` and updating the message text in place within the simulated thread.

6. **Draft Turn Progression in Level 1 & Staff Injection**:
   - In Level 1 autonomy, Tori generates draft responses rendered as interactive draft cards in `<AssistantThreadPanel mode="bootcamp" ... />`.
   - **Approve Draft**: Clicking "Send" dispatches `action: 'approve'` to `POST /api/admin/sms/bootcamp/conversations/{id}/drafts/{message_id}/review`, marks the message as sent, and advances the simulation to the next customer turn.
   - **Edit & Send Draft**: Operators can modify the draft text inline before approval; submitting calls the review endpoint with the edited content, saving learning diffs and advancing the turn.
   - **Discard Draft**: Discarding marks the draft as discarded and stops the thread.
   - Staff can inject custom messages directly into the simulated exchange using the composer (`Cmd+Enter` / `Ctrl+Enter` or green send button), posting to `POST /api/admin/sms/bootcamp/conversations/{id}/messages`.
   - Quick Tools sheet (`Zap` button) allows testing macro inserts and calendar slot proposals directly in simulation.

7. **Sandbox Isolation & Safety**:
   - All Bootcamp conversations, runs, and settings are strictly sandboxed.
   - Zero carrier SMS messages are dispatched, and no live bookings or database records are modified.

### 10. Operational Viewport & Vertical Space Architecture

1. **Global Header Slimming (`app-header.tsx`)**:
   - The global application header height is slimmed from `h-16` (64px) to `h-12` (48px).
   - Horizontal padding is tightened from `px-3 sm:gap-3 sm:px-6` to `px-3 sm:gap-2 sm:px-4`.
   - Child components (SidebarTrigger, notification bell, action buttons) are standardized to compact sizes (`h-8 w-8`, `size="sm"`), reclaiming 16px of vertical screen real-estate across all admin viewports.

2. **Route-Aware Operational Mode in Global Shell (`admin-layout.tsx`)**:
   - The global layout detects high-density operational routes (`/admin/sms-assistant`, `/admin/calendar`, `/admin/messages`):
     ```typescript
     const isOperationalRoute = location.pathname.startsWith('/admin/sms-assistant') ||
                                location.pathname.startsWith('/admin/calendar') ||
                                location.pathname.startsWith('/admin/messages');
     ```
   - For operational routes, `#main-content` adopts a full-bleed, edge-to-edge vertical canvas with ZERO outer padding:
     `"min-h-0 flex-1 flex flex-col p-0 overflow-hidden"`.
     This completely eliminates redundant outer margins, padding, and nested duplicate scrollbars, allowing operational workspaces to dock flush against the header.
   - For standard document/form pages, padding is reduced from bloated `p-8` (32px) to compact responsive bounds:
     `"min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 md:p-5 min-w-0 overflow-x-hidden pb-[calc(1.5rem+env(safe-area-inset-bottom))]"`

3. **SMS Assistant Flush Docking (`sms-assistant.tsx`)**:
   - Root `<section>` outer padding is eliminated (`p-0` instead of `p-0 sm:p-3 md:p-4`).
   - Tabs container top margin bloat is eliminated (`space-y-0` instead of `space-y-1.5 sm:space-y-3`).
   - Horizontal slider tabs bar docks cleanly against the top border with a thin border-b:
     `<div className="border-b border-border/80 bg-card/60 backdrop-blur-xs shrink-0">`.
   - All `<TabsContent>` elements use `flex-1 min-h-0 overflow-hidden flex flex-col` so sub-tabs (Messages, Inbox, Bootcamp, Arrivals, Triage, Settings) span the full available viewport height without awkward double padding or viewport clipping.

4. **Messages Viewport Optimization (`assistant-messages-page.tsx`)**:
   - Centered card container fills vertical height cleanly without floating gaps (`mx-auto flex h-full w-full max-w-3xl flex-col bg-card text-card-foreground border-x border-border shadow-md relative overflow-hidden`).
   - List header uses compact vertical padding (`px-3 py-2`), reducing search and global control bar height from ~54px to ~40px.
   - Active chat header inside `AssistantThreadPanel` utilizes compact `px-3 py-2` padding for seamless vertical continuity.

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
