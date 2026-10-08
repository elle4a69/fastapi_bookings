# Business Assistant Frontend (`frontend/src/pages/admin/business-assistant`)

The Business Assistant frontend module provides the administrative conversational dialogue interface, application-wide slide-out presence, user-safe support ticket management, visible in-app onboarding automation, and real-time WebRTC voice session capabilities for business owners and operators within **FastAPI Bookings**.

---

## 1. Purpose & Scope

This module delivers both a full-page Business Assistant management view, a persistent application-wide floating drawer accessible across all authenticated admin routes, and the client-side execution framework for voice-first onboarding assistance.

Key capabilities owned by this module:
- **Application-Wide Presence**: Responsive slide-out drawer accessible throughout the authenticated admin shell via floating action button (`SupportButton`) or persistent header trigger (`AppHeader`).
- **Context Awareness Boundary**: Safely captures the active page context containing route and module identifiers only (`current_path`, `module_name`), strictly forbidding any DOM scraping, input inspection, or credential capture.
- **Navigation Persistence**: Conversation state and active sessions survive route transitions between admin modules without resetting or losing drafts.
- **Accessibility & Focus Discipline**: Standard ARIA landmarks (`role="dialog"`, `aria-label="Business Assistant"`, `aria-modal="true"`), keyboard dismissal via `Escape`, and automated focus save and restoration.
- **Non-Obstructive Layer Discipline**: Operates on a controlled `z-40` layer, guaranteeing that critical confirmation dialogs (`z-50`), destructive warning modals, and security notifications remain unobstructed.
- **Interactive Conversation View**: Chronological message stream, markdown text rendering, retryable error presentation, and draft composition.
- **LiveKit & GPT-Live WebRTC Voice**: Direct browser-to-server WebRTC voice sessions with SDP negotiation, remote audio rendering, DataChannel caption deltas, and token refresh lifecycle (`use-livekit-voice.ts`, `minimized-voice-controller.tsx`).
- **Visible Form Automation & Form Adapters**: Concrete form adapters for Business Settings (`business-settings-adapter.ts`) and Catalog Services (`catalog-services-adapter.ts`), managed through an extensible `OnboardingFormAdapter` registry (`adapters/registry.ts`).
- **Single-Tab Active Executor Coordination**: Leased active executor coordinator (`rpc/executor-coordinator.ts`, `rpc/useActiveExecutor.ts`) ensuring only one designated browser tab executes mutating form automations per session, eliminating multi-tab race conditions.
- **Manual Takeover & Control Epoch**: Immediate user takeover banner ("I'll do this part" / `ManualTakeoverControl.tsx`) with monotonic epoch invalidation rejecting stale background commands upon any human typing or interaction.
- **Visual Non-Intercepting Pointer Overlay**: Smooth highlight and pulsing pointer overlay (`FieldPointerOverlay.tsx`, `useFieldHighlight.ts`) with `pointer-events: none` to guide users without interfering with native inputs.
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
├── use-livekit-voice.ts                  # LiveKit WebRTC agent hook for voice sessions & RPC dispatch
├── minimized-voice-controller.tsx        # Compact floating voice call controls and audio indicator
├── adapters/                             # Concrete Onboarding Form Adapters
│   ├── index.ts                          # Adapter exports
│   ├── registry.ts                       # OnboardingFormAdapter registry and lookup
│   ├── business-settings-adapter.ts      # Settings adapter with autosave staging guards
│   ├── catalog-services-adapter.ts       # Services catalog adapter with modal/active/price handling
│   └── adapters.test.ts                  # Unit test coverage for adapters and registry
├── components/                           # In-App Assistant UI Primitives
│   ├── index.ts                          # Component exports
│   ├── FieldPointerOverlay.tsx           # Non-intercepting visual field highlight and pointer
│   ├── ManualTakeoverControl.tsx         # Monotonic takeover banner and control epoch advancement
│   ├── OnboardingStatusDock.tsx          # Real-time onboarding status dock and progress tracking
│   ├── useFieldHighlight.ts              # Hook for smooth scrolling and highlighting form fields
│   └── takeover-pointer.test.ts          # Unit tests for takeover and pointer overlay
├── rpc/                                  # Typed LiveKit RPC Subsystem & Active Executor
│   ├── index.ts                          # RPC subsystem exports
│   ├── types.ts                          # RPC action models, payloads, and execution receipt schemas
│   ├── action-catalogue.ts               # Allowlisted routes, actions, and validation schemas
│   ├── executor-coordinator.ts           # Single-tab lease coordinator and epoch manager
│   ├── useActiveExecutor.ts              # React hook managing executor lease and takeover listeners
│   ├── rpc-receiver.ts                   # RPC handler dispatching to form adapters with receipts
│   ├── sender-validation.ts              # Strict identity verification for RPC message senders
│   ├── executor-coordinator.test.ts      # Unit tests for lease lifecycle and epoch monotonicity
│   ├── onboarding-protocol.test.ts       # Protocol and schema validation tests
│   └── rpc-action-receiver.test.ts       # Unit tests for RPC dispatch and adapter execution
├── ticket-status.tsx                     # User-safe ticket status display cards and event timeline
├── business-assistant-presence.test.ts   # Regression tests for drawer, context boundary, voice, and tickets
├── business-assistant-page.test.ts       # Full-page layout and history drawer structure tests
├── livekit-voice-ui.test.ts              # Unit tests for LiveKit voice UI and controller
└── README.md                             # Living documentation (AGENTS.md Rule 10)
```

### Key Files:
- [index.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/index.tsx): Full-page management interface displaying active conversation, history switcher, onboarding progress, and support tickets.
- [conversation.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/conversation.tsx): Interactive conversation component supporting text turns, voice call actions, and context attachment.
- [assistant-drawer.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/assistant-drawer.tsx): Persistent slide-out drawer providing seamless chat, history, and ticket tabs across admin views.
- [business-assistant-context.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/business-assistant-context.tsx): Provider holding thread selection, message history, voice status, and drawer visibility across in-app navigations.
- [context-boundary.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/context-boundary.ts): Pure function resolving only `current_path` and `module_name` while preventing DOM or secret leakage.
- [adapters/registry.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/adapters/registry.ts): Registry managing form adapters for visible form automation, field staging, and validation.
- [adapters/business-settings-adapter.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/adapters/business-settings-adapter.ts): Concrete adapter staging business settings (`name`, `abn`, `phone`, `timezone`, `currency`) while guarding against premature autosave debounces.
- [adapters/catalog-services-adapter.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/adapters/catalog-services-adapter.ts): Concrete adapter automating service catalog creation and updates (`name`, `duration_minutes`, `price`, `is_active`).
- [rpc/executor-coordinator.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/rpc/executor-coordinator.ts): Single-tab active executor coordinator enforcing exclusive automation lease and monotonic control epochs.
- [components/FieldPointerOverlay.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/components/FieldPointerOverlay.tsx): Visual overlay with smooth scrolling and animated focus ring without blocking clicks.
- [components/ManualTakeoverControl.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/components/ManualTakeoverControl.tsx): Compact floating banner allowing instant manual user takeover and cancelling automated actions.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React 19 & TypeScript**: Strongly typed component hierarchies, custom hooks, and state context.
- **Lucide React**: Icons for bot, microphone, phone hangup, tickets, history, and status alerts.
- **LiveKit Client (`livekit-client`)**: Native browser WebRTC client handling audio tracks, RPC registration, and DataChannel messaging.
- **API Client (`apiClient` / `authenticatedAdminFetch`)**: Central HTTP client injecting bearer authentication and `X-Tenant` headers.

### Environment & Permissions
- Microphone permission (`getUserMedia`) required for real-time voice mode.
- Communicates with authenticated text/ticket endpoints mounted at `/api/admin/business-assistant`, voice router at `/api/admin/business-assistant/voice`, and onboarding router at `/api/business-assistant/onboarding`:
  - `GET /api/admin/business-assistant/conversations`
  - `POST /api/admin/business-assistant/conversations`
  - `GET /api/admin/business-assistant/conversations/{id}/messages`
  - `POST /api/admin/business-assistant/conversations/{id}/messages`
  - `POST /api/admin/business-assistant/voice/conversations/{id}/session`
  - `POST /api/admin/business-assistant/voice/conversations/{id}/token/refresh`
  - `GET /api/admin/business-assistant/tickets`
  - `POST /api/admin/business-assistant/tickets`
  - `GET /api/admin/business-assistant/tickets/{id}/events`
  - `GET /api/business-assistant/onboarding/plan`
  - `POST /api/business-assistant/onboarding/takeover`

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

### 4.4 LiveKit & GPT-Live Voice Exchange
1. **Microphone Access**: Requests browser audio stream via `getUserMedia({ audio: true })`.
2. **Session Token Issuance**: Posts to `/api/admin/business-assistant/voice/conversations/{id}/session` to obtain a scoped room token and participant identity.
3. **Room Connection & RPC**: Connects to the LiveKit room, binds remote audio tracks to an HTML `<audio>` element, and registers RPC receivers via `registerAssistantRpcMethods(room, context)`.
4. **Captions**: Displays received transcript deltas on the DataChannel grouped by session intervals.
5. **Teardown**: Cleans up audio tracks and RPC handlers upon call hangup or unmount.

### 4.5 Support Ticket Management
1. **Listing**: Loads tickets via `GET /tickets` displaying status badges (`awaiting_engineering`, etc.).
2. **Creation**: Submits sanitized problem summary and description with unique `request_key`.
3. **Timeline**: Expands ticket to fetch append-only lifecycle events via `GET /tickets/{id}/events`.

### 4.6 Visible Form Automation & Autosave Staging Guard
1. **Adapter Registration**: When a target view mounts (e.g., Business Settings or Catalog Services), it registers an `OnboardingFormAdapter` instance with the central registry (`adapters/registry.ts`).
2. **Field Staging**: When an RPC `set_fields` action arrives, the adapter stages values into component state and sets a 600ms autosave staging guard.
3. **Receipt Distinction**: The adapter generates a structured receipt distinguishing `fields_staged` (`saved=False`, `persisted_entity_id=None`) from committed persistence (`saved=True`).

### 4.7 Leased Active-Executor Coordination & Multi-Tab Isolation
1. **Single Leased Tab**: Across multiple open browser tabs in a tenant session, only one tab acquires the `active_executor_lease` stored in `localStorage` or `sessionStorage`.
2. **Heartbeat & Expiration**: The active tab maintains the lease with periodic heartbeats; if stale (>15 seconds), secondary tabs may claim it.
3. **Targeted Dispatch**: Automated mutating RPC commands are executed solely by the leased tab; other tabs observe or ignore mutating RPCs.

### 4.8 Monotonic Control Epoch & Manual Takeover Priority
1. **Epoch Tracking**: A monotonic `control_epoch` integer is maintained across the session.
2. **Takeover Invalidation**: When the user clicks "I'll do this part" or types into any field, `advanceControlEpoch()` increments the epoch and emits a takeover signal.
3. **Rejection of Stale Commands**: Any in-flight or queued automated action bearing an epoch lower than the current epoch is immediately rejected with HTTP 409 / `STALE_CONTROL_EPOCH`.

### 4.9 Visual Pointer Overlay & Field Highlighting
1. **Highlight Request**: An RPC `highlight_field` or adapter step triggers `useFieldHighlight`.
2. **Smooth Scroll**: The viewport smoothly scrolls to the target element if outside the visible area.
3. **Non-Intercepting Ring**: `FieldPointerOverlay` renders a pulsating accent ring around the target element with `pointer-events: none`, preserving full native user interaction.

---

## 5. Data Safety & Isolation

- **Context Boundary Discipline**: The assistant receives zero scraped page content, form values, or secret data. Only authorized route and module identifiers are transmitted.
- **Tenant Scope Enforcement**: All HTTP and WebRTC requests pass authentication credentials validating tenant authorization (`X-Tenant` header and JWT token).
- **Absolute Prohibition of Mocks (Rule 3)**: No synthetic timeouts or mocked endpoints. All interactions communicate directly with real backend services and real DOM adapters.
- **Audio Privacy**: Microphone streams activate only when the user explicitly triggers voice mode. Session captions remain client-memory-only.
- **Non-Obstructive Layout**: Operates at `z-40`, ensuring critical confirmation modals (`z-50`) are never obscured.
- **Pointer Events Safety**: Visual highlight overlays enforce `pointer-events: none` so no clicks or keystrokes are intercepted or prevented.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Microphone Denied**: If a user declines microphone permissions, the interface provides a user-friendly notice and seamlessly preserves full text capability.
- **Multi-Tab Lease Contention**: If an inactive tab has focus, the active executor dock alerts the user and offers a one-click "Claim Automation Control" button.
- **Awaiting Engineering State**: Support tickets remain in `awaiting_engineering` until approved or claimed by a verified engineering worker.

---

## 7. Verification & Testing Commands

To verify the business assistant module:

```powershell
# 1. Run all unit and regression tests (131 tests including adapters, rpc, takeover, and voice)
npm test

# 2. Run TypeScript compilation check
npx tsc -b

# 3. Run frontend production build
npm run build

# 4. Verify living documentation compliance (Rule 10)
python scripts/verify_living_docs.py --path frontend/src/pages/admin/business-assistant/README.md
```
