# Business Assistant Frontend (`frontend/src/pages/admin/business-assistant`)

The Business Assistant frontend module provides the administrative conversational dialogue interface, application-wide slide-out presence, user-safe support ticket management, and real-time WebRTC voice session capabilities for business owners and operators within **FastAPI Bookings**.

---

## 1. Purpose & Scope

This module delivers both a full-page Business Assistant management view and a persistent, application-wide floating drawer accessible across all authenticated admin routes.

Key capabilities owned by this module:
- **Application-Wide Presence**: Responsive slide-out drawer accessible throughout the authenticated admin shell via floating action button (`SupportButton`) or persistent header trigger (`AppHeader`).
- **Context Awareness Boundary**: Safely captures the active page context containing route and module identifiers only (`current_path`, `module_name`), strictly forbidding any DOM scraping, input inspection, or credential capture.
- **Navigation Persistence**: Conversation state and active sessions survive route transitions between admin modules without resetting or losing drafts.
- **Accessibility & Focus Discipline**: Standard ARIA landmarks (`role="dialog"`, `aria-label="Business Assistant"`, `aria-modal="true"`), keyboard dismissal via `Escape`, and automated focus save and restoration.
- **Non-Obstructive Layer Discipline**: Operates on a controlled `z-40` layer, guaranteeing that critical confirmation dialogs (`z-50`), destructive warning modals, and security notifications remain unobstructed.
- **Interactive Conversation View**: Chronological message stream, markdown text rendering, retryable error presentation, and draft composition.
- **Real-Time WebRTC Voice**: Direct browser-to-server WebRTC session with SDP offer/answer negotiation, microphone lifecycle management, transcript pairing, tool execution event handling, and graceful degradation to text.
- **User-Safe Support Tickets**: Ticket status tracking cards (`awaiting_engineering`, `in_progress`, `completed`, `cancelled`), category/severity classification, sanitized submissions, and append-only event timeline inspection.
- **Onboarding & Setup Readiness**: Real-time integration with tenant setup milestones and catalog capacity metrics.

This module strictly avoids browser-side LLM simulations, synthetic timeouts, fake frontend mocks (AGENTS.md Rule 3), or scraping DOM secrets.

---

## 2. Architecture & Key Files

```
frontend/src/pages/admin/business-assistant/
├── index.tsx                             # Full-page Business Assistant management, history drawer, and onboarding
├── conversation.tsx                      # Modular conversational message stream and input bar
├── assistant-drawer.tsx                  # Application-wide responsive slide-out drawer
├── business-assistant-context.tsx        # React context managing persistent conversation and drawer state
├── context-boundary.ts                   # Strict route and module context extraction boundary
├── use-realtime-voice.ts                 # Real WebRTC audio session hook connecting to backend realtime endpoint
├── use-business-assistant-realtime-voice.ts # Backward-compatible re-export of use-realtime-voice
├── realtime-protocol.ts                  # WebRTC SDP negotiation, transcript pairing, and tool call protocol
├── realtime-voice-protocol.ts            # Backward-compatible re-export of realtime-protocol
├── ticket-status.tsx                     # User-safe ticket status display cards and event timeline
├── business-assistant-presence.test.ts   # Regression tests for drawer, context boundary, voice, and tickets
├── business-assistant-page.test.ts       # Full-page layout and history drawer structure tests
├── realtime-voice-protocol.test.ts       # Realtime transcript pairing and protocol tests
└── README.md                             # Living documentation (AGENTS.md Rule 10)
```

### Key Files:
- [index.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/index.tsx): Full-page management interface displaying active conversation, history switcher, onboarding progress, and support tickets.
- [conversation.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/conversation.tsx): Interactive conversation component supporting text turns, voice call actions, and context attachment.
- [assistant-drawer.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/assistant-drawer.tsx): Persistent slide-out drawer providing seamless chat, history, and ticket tabs across admin views.
- [business-assistant-context.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/business-assistant-context.tsx): Provider holding thread selection, message history, voice status, and drawer visibility across in-app navigations.
- [context-boundary.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/context-boundary.ts): Pure function resolving only `current_path` and `module_name` while preventing DOM or secret leakage.
- [use-realtime-voice.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/use-realtime-voice.ts): Manages `navigator.mediaDevices.getUserMedia`, `RTCPeerConnection`, data channel events, and completed turn persistence.
- [realtime-protocol.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/realtime-protocol.ts): Serializes SDP exchanges, matches user/assistant audio transcript pairs, and parses OpenAI realtime function call events.
- [ticket-status.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/ticket-status.tsx): Renders user-safe ticket status badges, sanitized descriptions, creation form, and append-only event timelines.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React 19 & TypeScript**: Strongly typed component hierarchies, custom hooks, and state context.
- **Lucide React**: Icons for bot, microphone, phone hangup, tickets, history, and status alerts.
- **WebRTC API**: Native browser `RTCPeerConnection`, `MediaStream`, and `RTCDataChannel`.
- **API Client (`apiClient` / `authenticatedAdminFetch`)**: Central HTTP client injecting bearer authentication and `X-Tenant` headers.

### Environment & Permissions
- Microphone permission (`getUserMedia`) required for real-time voice mode.
- Communicates with authenticated endpoints mounted at `/api/admin/business-assistant`:
  - `GET /api/admin/business-assistant/conversations`
  - `POST /api/admin/business-assistant/conversations`
  - `GET /api/admin/business-assistant/conversations/{id}/messages`
  - `POST /api/admin/business-assistant/conversations/{id}/messages`
  - `POST /api/admin/business-assistant/conversations/{id}/realtime`
  - `POST /api/admin/business-assistant/conversations/{id}/realtime/turns`
  - `POST /api/admin/business-assistant/conversations/{id}/realtime/tools`
  - `GET /api/admin/business-assistant/tickets`
  - `POST /api/admin/business-assistant/tickets`
  - `GET /api/admin/business-assistant/tickets/{id}/events`
  - `GET /api/admin/business-assistant/onboarding`

---

## 4. Core Workflows & Contracts

### 4.1 Application-Wide Drawer Lifecycle
1. **Triggering**: Click either the floating support action button or the persistent header Assistant button.
2. **Focus Management**: On opening, focus moves into the drawer's primary interactive control; closing restores focus to the invoking button.
3. **Keyboard Dismissal**: Pressing `Escape` closes the drawer immediately.
4. **Navigation Persistence**: Navigating between admin pages maintains active conversation ID, draft, and message stream in `BusinessAssistantContext`.

### 4.2 Context Awareness Boundary
1. When attaching page context, `resolvePageContext(location.pathname)` extracts only `current_path` and `module_name`.
2. Form inputs, password fields, cookies, tokens, and DOM contents are strictly excluded.
3. The context is prepended cleanly as `[Context: path=..., module=...]` only when explicitly toggled.

### 4.3 Text Dialogue Lifecycle
1. **Session Fetch**: Loads conversation threads for the current user and tenant.
2. **Turn Submission**: Sends `{ content, request_key }` to `POST /conversations/{id}/messages`.
3. **Turn Persistence**: Displays verified user and assistant turns; preserves drafts upon network or upstream failures.

### 4.4 Realtime Voice Exchange
1. **Microphone Access**: Requests browser audio stream via `getUserMedia({ audio: true })`.
2. **SDP Exchange**: Generates client offer and posts to `/realtime`, setting remote answer description.
3. **Turn Pairing**: Events received on `RTCDataChannel` are paired chronologically into completed turns.
4. **Turn Persistence**: Persists pairs via `POST /realtime/turns`.
5. **Tool Execution**: Function call events from server audio model are dispatched via `POST /realtime/tools` and output is sent back on the data channel.

### 4.5 Support Ticket Management
1. **Listing**: Loads tickets via `GET /tickets` displaying status badges (`awaiting_engineering`, etc.).
2. **Creation**: Submits sanitized problem summary and description with unique `request_key`.
3. **Timeline**: Expands ticket to fetch append-only lifecycle events via `GET /tickets/{id}/events`.

---

## 5. Data Safety & Isolation

- **Context Boundary Discipline**: The assistant receives zero scraped page content, form values, or secret data. Only authorized route and module identifiers are transmitted.
- **Tenant Scope Enforcement**: All HTTP and WebRTC requests pass authentication credentials validating tenant authorization.
- **Absolute Prohibition of Mocks (Rule 3)**: No synthetic timeouts or mocked endpoints. All interactions communicate directly with real backend services.
- **Audio Privacy**: Microphone streams activate only when the user explicitly triggers voice mode and terminate cleanly upon ending the call or unmounting.
- **Non-Obstructive Layout**: Operates at `z-40`, ensuring critical confirmation modals (`z-50`) are never obscured.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Microphone Denied**: If a user declines microphone permissions, the interface provides a user-friendly notice and seamlessly preserves full text capability.
- **Network Interruptions**: Transient socket drops during voice mode cause clean teardown and return the state to idle without leaving dangling media streams.
- **Awaiting Engineering State**: Support tickets remain in `awaiting_engineering` until approved or claimed by a verified engineering worker.

---

## 7. Verification & Testing Commands

To verify the business assistant module:

```powershell
# 1. Run all unit and regression tests
npm test

# 2. Run TypeScript compilation check
npx tsc -b

# 3. Run frontend production build
npm run build

# 4. Verify living documentation compliance (Rule 10)
python scripts/verify_living_docs.py --path frontend/src/pages/admin/business-assistant/README.md
```
