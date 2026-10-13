# Business Assistant Frontend (`frontend/src/pages/admin/business-assistant`)

The Business Assistant frontend module provides the administrative conversational dialogue interface, application-wide presence, user-safe support ticket management, visible in-app onboarding automation, and real-time voice session capabilities (supporting both OpenAI GPT-Live and xAI Grok Voice) for business owners and operators within **FastAPI Bookings**.

---

## 1. Purpose & Scope

This module delivers both a full-page Business Assistant management view, a persistent application-wide floating drawer accessible across all authenticated admin routes, and the client-side execution framework for voice-first onboarding assistance.

Key capabilities owned by this module:
- **Application-Wide Presence**: Responsive slide-out drawer accessible throughout the authenticated admin shell via floating action button (`SupportButton`) or persistent header trigger (`AppHeader`).
- **Context Awareness Boundary**: Safely captures the active page context containing route and module identifiers only (`current_path`, `module_name`), strictly forbidding any DOM scraping, input inspection, or credential capture.
- **Navigation Persistence**: Conversation state and active sessions survive route transitions between admin modules without resetting or losing drafts.
- **Accessibility & Focus Discipline**: Standard ARIA landmarks (`role="dialog"`, `aria-label="Business Assistant"`, `aria-modal="true"`), keyboard dismissal via `Escape`, and automated focus save and restoration.
- **Non-Obstructive Layer Discipline**: Operates on a controlled `z-40` layer, guaranteeing that critical confirmation dialogs (`z-50`), destructive warning modals, and security notifications remain unobstructed.
- **Native LiveKit Agent Popup (`AgentPopup_01`)**: Embedded LiveKit `AgentPopup_01` block (`frontend/src/components/agents-ui/agent-popup.tsx`) with floating circular trigger bubble, expanding session popup, auto-scrolling transcript timeline, typing input ("Type something..."), animated 3-bar audio visualizer with device dropdown, camera toggle, screen share toggle, and transcript toggle.
- **Dual Realtime Voice Engines**:
  - **OpenAI GPT-Live (`direct_gpt_live`)**: Direct browser-to-server WebRTC audio stream with server-held SDP exchange.
  - **xAI Grok Voice (`xai_grok_voice`)**: Direct WebSocket audio transport powered by `grok-voice-think-fast-2.0` (`use-xai-grok-voice.ts`), processing 16-bit PCM 24kHz audio, client-side tool execution, and activity telemetry.
  - Configurable via `VoiceEngineSelector` inside `AssistantSettingsDialog`.
- **Canonical 16-Tool Voice Schema Alignment**: Complete frontend support for the 16 canonical voice tools (`VOICE_BUSINESS_ASSISTANT_TOOLS`), executing UI automation RPCs and backend tools seamlessly while strictly omitting non-voice duplicate aliases.
- **Single-Tab Active Executor Lease Token Forwarding**: Ensures UI automation RPCs triggered by voice models (`xai-grok-voice`, `direct-gpt-live`) automatically inherit the active tab's lease token, preventing lease validation errors while preserving multi-tab isolation.
- **Route Normalization & Aliases**: Client-side navigation (`normalizeRoute`) resolving aliases (e.g. `/admin/services` -> `/admin/catalog/services`) and enforcing strict security allowlists (`isRouteAllowlisted`).
- **Visible Form Automation & Form Adapters**: Concrete form adapters for Business Settings (`business-settings-adapter.ts`) and Catalog Services (`catalog-services-adapter.ts`), managed through an extensible `OnboardingFormAdapter` registry (`adapters/registry.ts`).
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
├── business-assistant-context.tsx        # React context managing persistent conversation, voice state, and drawer
├── context-boundary.ts                   # Strict route and module context extraction boundary
├── use-livekit-voice.ts                  # LiveKit WebRTC agent hook for voice sessions & RPC dispatch
├── use-xai-grok-voice.ts                 # xAI Grok Voice WebSocket hook (PCM audio, tool parsing, lease forwarding)
├── minimized-voice-controller.tsx        # Compact floating voice call controls and audio indicator
├── realtime-protocol.ts                  # Realtime tool parsing, output formatting, and agent activity schemas
├── adapters/                             # Concrete Onboarding Form Adapters
│   ├── index.ts                          # Adapter exports
│   ├── registry.ts                       # OnboardingFormAdapter registry and lookup
│   ├── business-settings-adapter.ts      # Settings adapter with autosave staging guards
│   ├── catalog-services-adapter.ts       # Services catalog adapter with modal/active/price handling
│   └── adapters.test.ts                  # Unit test coverage for adapters and registry
├── components/                           # In-App Assistant UI Primitives
│   ├── index.ts                          # Component exports
│   ├── AssistantSettingsDialog.tsx       # Modal dialog for Voice Transport and Diagnostic Mode administration
│   ├── DiagnosticModeToggle.tsx          # Real-time diagnostic mode toggle connected to BusinessAssistantContext
│   ├── FieldPointerOverlay.tsx           # Non-intercepting visual field highlight and pointer
│   ├── LiveAgentActivityConsole.tsx      # Real-time streaming activity console for agent thoughts & tool runs
│   ├── ManualTakeoverControl.tsx         # Monotonic takeover banner and control epoch advancement
│   ├── OnboardingStatusDock.tsx          # Real-time onboarding status dock and progress tracking
│   ├── useFieldHighlight.ts              # Hook for smooth scrolling and highlighting form fields
│   ├── VoiceEngineSelector.tsx           # Dual realtime engine selector (xAI Grok & OpenAI GPT-Live)
│   ├── VoiceTransportSwitcher.tsx        # Dynamic transport switcher between Direct WebRTC, Local, and Cloud LiveKit
│   └── takeover-pointer.test.ts          # Unit tests for takeover and pointer overlay
├── rpc/                                  # Typed LiveKit RPC Subsystem & Active Executor
│   ├── index.ts                          # RPC subsystem exports
│   ├── types.ts                          # RPC action models, payloads, and execution receipt schemas
│   ├── action-catalogue.ts               # Allowlisted routes, aliases, lease validation, and execution schemas
│   ├── executor-coordinator.ts           # Single-tab lease coordinator and epoch manager
│   ├── useActiveExecutor.ts              # React hook managing executor lease and takeover listeners
│   ├── rpc-receiver.ts                   # RPC handler dispatching to form adapters with receipts
│   ├── sender-validation.ts              # Strict identity verification for RPC message senders
│   ├── executor-coordinator.test.ts      # Unit tests for lease lifecycle and epoch monotonicity
│   ├── onboarding-protocol.test.ts       # Protocol and schema validation tests
│   └── rpc-action-receiver.test.ts       # Unit tests for RPC dispatch, route normalization, and lease forwarding
├── ticket-status.tsx                     # User-safe ticket status display cards and event timeline
├── business-assistant-presence.test.ts   # Regression tests for drawer, context boundary, voice, and tickets
├── business-assistant-page.test.ts       # Full-page layout and history drawer structure tests
├── livekit-voice-ui.test.ts              # Unit tests for LiveKit voice UI and controller
├── gpt-live-voice-integration.test.ts    # Integration tests for xAI Grok voice and active executor leasing
└── README.md                             # Living documentation (AGENTS.md Rule 10)
```

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React 19 & TypeScript**: Strongly typed component hierarchies, custom hooks, and state context.
- **Lucide React**: Icons for bot, microphone, phone hangup, tickets, history, and status alerts.
- **LiveKit Client (`livekit-client`)**: Native browser WebRTC client handling audio tracks, RPC registration, and DataChannel messaging.
- **Web Audio API**: Browser `AudioContext`, `ScriptProcessorNode`, and `MediaStream` for 16-bit PCM 24kHz audio capture and playback in `use-xai-grok-voice.ts`.
- **API Client (`apiClient` / `authenticatedAdminFetch`)**: Central HTTP client injecting bearer authentication and `X-Tenant` headers.

### Environment & Permissions
- Microphone permission (`getUserMedia`) required for real-time voice modes.
- Communicates with authenticated backend endpoints:
  - Text & tickets: `/api/admin/business-assistant/*`
  - OpenAI Realtime voice: `/api/admin/business-assistant/conversations/{id}/realtime`
  - xAI Grok token & relay: `GET /api/admin/business-assistant/realtime/xai-token` and WebSocket relay `/api/admin/business-assistant/voice/realtime/xai-ws`
  - LiveKit voice: `/api/admin/business-assistant/voice/conversations/{id}/session`
  - Onboarding plan & takeover: `/api/business-assistant/onboarding/*`

---

## 4. Core Workflows & Contracts

### 4.1 Application-Wide Drawer & Popup Lifecycle
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

### 4.4 LiveKit & Direct GPT-Live WebRTC Voice
1. **Microphone Access**: Requests browser audio stream via `getUserMedia({ audio: true })`.
2. **Session Token Issuance**: Posts to `/api/admin/business-assistant/voice/conversations/{id}/session` to obtain a scoped room token and participant identity.
3. **Room Connection & RPC**: Connects to the LiveKit room, binds remote audio tracks to an HTML `<audio>` element, and registers RPC receivers via `registerAssistantRpcMethods(room, context)`.
4. **Captions**: Displays received transcript deltas on the DataChannel grouped by session intervals.
5. **Teardown**: Cleans up audio tracks and RPC handlers upon call hangup or unmount.

### 4.5 xAI Grok Voice Transport & WebSocket Relay
1. **Token Retrieval**: Fetches connection parameters from `GET /api/admin/business-assistant/realtime/xai-token` (providing agent ID, connection URL, API key, and local relay URL).
2. **WebSocket Audio Pipeline**: `useXAIGrokVoice` opens WebSocket connection, captures microphone stream, converts audio to 16-bit PCM at 24kHz using `floatTo16BitPCM`, and streams Base64 audio chunks to the server.
3. **Incoming Audio & Captions**: Decodes incoming PCM audio via `base64ToFloat32Array` for scheduled playback through `AudioContext`, simultaneously appending streaming captions to the transcript timeline.
4. **Realtime Tool Parsing & Execution**: When Grok produces function calls, `parseRealtimeToolCalls` extracts tool requests:
   - UI automation tools (`navigate_route`, `highlight_field`, `stage_fields`) are executed immediately via `executeRpcAction`.
   - Backend tools (`list_services`, `list_providers`, `check_slot_availability`, `diagnostic_report`) are executed against `POST /conversations/{id}/realtime/tools`.
5. **Tool Output Response**: Formats structured tool receipts with `formatRealtimeToolOutput` and sends `conversation.item.create` + `response.create` events back over the WebSocket.

### 4.6 Canonical 16-Tool Voice Schema Alignment (`VOICE_BUSINESS_ASSISTANT_TOOLS`)
The frontend voice infrastructure enforces exact alignment with the canonical 16-tool voice schema:
- **Navigation**: `navigate_route` is the sole authorized navigation tool for page switching.
- **UI Guidance**: `highlight_field` applies non-intercepting focus rings without page jumps.
- **Form Automation**: `stage_fields`, `validate_form`, `request_save_authorization`, `commit_save`, `ask_clarification`, `pause_takeover`.
- **System Reads**: `list_services`, `list_providers`, `check_slot_availability`, `get_onboarding_status`, `read_system_settings`, `diagnostic_report`.
- **Rule Management**: `draft_business_rule`, `activate_business_rule`.
- Duplicate aliases (`save_form`, `prepare_fields`, `fill_form`, `navigate_show`, `read_status`, `read_context`) are omitted to prevent tool selection errors during voice sessions.

### 4.7 Single-Tab Active Executor Lease Token Forwarding
1. **Single Leased Tab**: Across multiple open browser tabs in a tenant session, only one tab acquires the `active_executor_lease` (`executorCoordinator.claimActiveExecutor()`).
2. **Lease Token Forwarding for Voice**: When a voice caller (`xai-grok-voice`, `direct-gpt-live`, `realtime-voice`) executes UI automation tools, LLMs do not supply a client lease token.
3. The RPC executor (`action-catalogue.ts`) detects trusted voice caller identities and automatically forwards the active tab's lease token (`leaseMgr.getActiveLease().token`).
4. This ensures voice commands dispatched within the active tab pass lease validation seamlessly, while background tabs remain blocked from executing conflicting automations.

### 4.8 Route Normalization & Alias Architecture
1. Dispatched navigation commands pass through `normalizeRoute(rawRoute)`:
   - Resolves aliases to canonical paths:
     - `services`, `catalog`, `/admin/services`, `/admin/catalog` -> `/admin/catalog/services`
     - `website`, `website_editor` -> `/admin/website`
     - `media` -> `/admin/media`
     - `onboarding`, `settings`, `/admin/settings` -> `/admin/settings/business`
     - `bookings` -> `/admin/bookings`
   - Strips search parameters and hash fragments before comparison.
2. Route safety is verified by `isRouteAllowlisted(targetPath)`: strictly rejects dangerous protocols (`javascript:`, `http:`, `https:`, `//`) and directory traversal (`..`).

### 4.9 Visible Form Automation & Autosave Staging Guard
1. **Adapter Registration**: When a target view mounts (e.g. Business Settings or Catalog Services), it registers an `OnboardingFormAdapter` instance with the central registry (`adapters/registry.ts`).
2. **Field Staging**: When an RPC `stage_fields` or `fill_fields` action arrives, the adapter stages values into component state and sets a 600ms autosave staging guard.
3. **Receipt Distinction**: The adapter generates a structured receipt distinguishing `fields_staged` (`saved=False`, `persisted_entity_id=None`) from committed persistence (`saved=True`).

### 4.10 Monotonic Control Epoch & Manual Takeover Priority
1. **Epoch Tracking**: A monotonic `control_epoch` integer is maintained across the session.
2. **Takeover Invalidation**: When the user clicks "I'll do this part" or types into any field, `advanceControlEpoch()` increments the epoch and emits a takeover signal.
3. **Rejection of Stale Commands**: Any in-flight or queued automated action bearing an epoch lower than the current epoch is immediately rejected with HTTP 409 / `STALE_CONTROL_EPOCH`.

### 4.11 Visual Pointer Overlay & Field Highlighting
1. **Highlight Request**: An RPC `highlight_field` or adapter step triggers `useFieldHighlight`.
2. **Smooth Scroll**: The viewport smoothly scrolls to the target element if outside the visible area.
3. **Non-Intercepting Ring**: `FieldPointerOverlay` renders a pulsating accent ring around the target element with `pointer-events: none`, preserving full native user interaction.

### 4.12 Support Ticket Management
1. **Listing**: Loads tickets via `GET /tickets` displaying status badges (`awaiting_engineering`, etc.).
2. **Creation**: Submits sanitized problem summary and description with unique `request_key`.
3. **Timeline**: Expands ticket to fetch append-only lifecycle events via `GET /tickets/{id}/events`.

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
- **Voice Assistant Navigation & Lease Token Inheritance**: Voice sessions running in the active executor tab (`xai-grok-voice`, `direct-gpt-live`, `realtime-voice`) automatically inherit the active tab lease token during tool execution, enabling client-side UI navigation (`navigate_route`) across all allowlisted admin routes and aliases (such as `/admin/services` -> `/admin/catalog/services`).
- **Turn Tool Quotas & Reset Lifecycle**: Voice engines (`use-xai-grok-voice.ts`, `use-gpt-live.ts`) enforce a 20-round turn quota (`MAX_CONSECUTIVE_TOOL_CALLS = 20`) providing ample capacity for sequential onboarding actions (`get_onboarding_status` -> `stage_fields` -> `validate_form` -> `commit_save`). Turn tool counters reset reliably across all boundary events (`input_audio_buffer.speech_started`, `conversation.item.created`, `input_audio_transcription.completed`, and non-tool `response.done` spoken completions).
- **Authoritative Burst Rate Protection**: Backend tool execution in `BusinessAssistantService` enforces a 20-call per 3-second burst limit to support multi-step tool turns while preventing uncontrolled runaway cascades.
- **Awaiting Engineering State**: Support tickets remain in `awaiting_engineering` until approved or claimed by a verified engineering worker.

---

## 7. Verification & Testing Commands

To verify the business assistant module:

```powershell
# 1. Run all unit and regression tests (including adapters, rpc, takeover, and voice)
npm test

# 2. Run focused voice and active executor lease tests
npm test -- frontend/src/pages/admin/business-assistant/gpt-live-voice-integration.test.ts
npm test -- frontend/src/pages/admin/business-assistant/rpc/rpc-action-receiver.test.ts
npm test -- frontend/src/pages/admin/business-assistant/livekit-voice-ui.test.ts

# 3. Run TypeScript compilation check
npx tsc -b

# 4. Run frontend production build
npm run build

# 5. Verify living documentation compliance (Rule 10)
python scripts/verify_living_docs.py --path frontend/src/pages/admin/business-assistant/README.md
```
