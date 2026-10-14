# Business Assistant Foundation

## 1. Purpose & Scope

This package owns tenant- and user-scoped persistence operations, bounded text generation, and server-authorised tool execution for internal Business Assistant conversations within **FastAPI Bookings**. It supports conversational onboarding, live product help, tenant settings discovery, real-time appointment availability inquiry, visible administrative UI automation, real-time voice sessions (OpenAI Realtime and xAI Grok Voice), and authoritative business knowledge curation.

It deliberately excludes synthetic mocks (AGENTS.md Rule 3), unconfirmed booking writes, unconfirmed customer messaging broadcasts, autonomous website publication without owner approval, unapproved coding worker dispatch, and direct database access by language models.

---

## 2. Architecture & Key Files

```text
app/services/business_assistant/
├── repository.py        # Scoped SQLAlchemy persistence, memory lifecycle, and tool telemetry
├── runtime.py           # Configured bounded provider request and function-calling loop
├── service.py           # Turn coordinator, business rule drafting/activation, and curator workflows
├── confirmation.py      # Cryptographic confirmation tokens and dynamic-fact rejection policy
├── tickets.py           # Ticket-summary safety checks and duplicate fingerprinting
├── idempotency.py       # Canonical payload hashes and key-reuse conflict checks
├── product_context.py   # Read-only allowlisted native setup snapshot
├── tool_registry.py     # Modular tool packs and canonical 16-tool voice schema (VOICE_BUSINESS_ASSISTANT_TOOLS)
├── website_sanitiser.py # XSS, script injection, PII sanitiser and asset domain validator
├── realtime.py          # Server-held SDP exchange for authenticated WebRTC voice sessions
├── gpt_live/            # Isolated GPT-Live WebRTC session creation and delegation boundary
├── onboarding/          # Voice-first onboarding assistant, intent normalizer, plan service, and save guard
├── coding_worker.py     # Real isolated coding-worker connector, scope inspector & verification runner
├── ccc_bridge_service.py # Autonomous bridge for Codex Control Centre remediation, steering & UI verification
├── rollout.py           # Staged rollout lifecycle, stage gate evaluation and safe degradation
├── adapters/
│   ├── reads.py         # Scoped native read adapters for product help, settings, and scheduling
│   └── __init__.py      # Adapter exports
└── __init__.py          # Public package exports
```

The ORM records reside in `app/models/business_assistant.py` and `app/models/onboarding.py`; validation contracts reside in `app/schemas/business_assistant.py` and `app/schemas/onboarding.py`. They are intentionally separated from customer conversation and message tables.

---

## 3. Setup, Configuration & Dependencies

### Database & Migrations
The package uses the application SQLAlchemy session and existing tables (`tenants`, `users`, `services`, `providers`, `locations`, `curated_memories`, `tenant_websites`, `knowledge_proposals`, `onboarding_plans`, `onboarding_steps`, `onboarding_audit_logs`, `assistant_error_logs`, `business_assistant_diagnostic_settings`). Backed by Alembic migrations:
- `g7h9j1k3m5n7`: Business assistant tables & conversation entities
- `h8j0k2m4n6p8`: Curated memory & proposal updates
- `p1q2r3s4t5u6`: Coding worker claim and event ledger
- `u5v6w7x8y9z0`: Website proposal versioning and publication tables
- `v7w8x9y0z1a2`: Ticket deduplication and access approval gates
- `w8x9y0z1a2b3`: Business assistant tool audit telemetry
- `z1a2b3c4d5e6`: Voice-first onboarding workflow tables
- `a1b2c3d4e5f7`: Business assistant diagnostics settings & error logs

### Core Environment Settings
- **Text Engine Settings**:
  - `OPENAI_API_KEY`: Server-held API key for OpenAI chat completions and realtime voice.
  - `BUSINESS_ASSISTANT_TEXT_MODEL`: Primary LLM for chat completions (default: `gpt-4o`). Completion options dynamically adapt (`reasoning_effort="none"` passed strictly to models requiring it for function tools like `gpt-5*`, omitted for standard `gpt-4o`/`gpt-4o-mini`).
  - `BUSINESS_ASSISTANT_MAX_HISTORY_MESSAGES`: Upper bound on historical conversation messages loaded per turn.
  - `BUSINESS_ASSISTANT_MAX_OUTPUT_TOKENS`: Maximum tokens generated per assistant response.
  - `BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS`: Execution timeout bounding provider requests.
  - `BUSINESS_ASSISTANT_MAX_TOOL_ROUNDS`: Upper limit on sequential tool invocation rounds.
- **OpenAI Realtime Voice Settings**:
  - `BUSINESS_ASSISTANT_REALTIME_MODEL`: Realtime voice model (default: `gpt-4o-realtime-preview`).
  - `BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES`: Maximum byte size for inbound WebRTC SDP offers (default: 65536 bytes).
- **xAI Grok Voice Settings**:
  - `XAI_API_KEY`: Server-held API key for xAI Grok voice and realtime WebSocket services.
  - `XAI_REALTIME_AGENT_ID`: Configured agent identifier for xAI Realtime voice assistant.
  - `XAI_REALTIME_URL`: Base WebSocket endpoint for xAI Realtime connections (`wss://api.x.ai/v1/realtime`).
- **Codex Control Centre (CCC) Autonomous Agent Bridge Settings**:
  - `CODEX_CONTROL_CENTRE_URL`: Base URL for Codex Control Centre API (default: `http://127.0.0.1:4500`).
  - `CODEX_CONTROL_CENTRE_TOKEN`: Optional Bearer token for authenticating with CCC.
- **Rollout Gating**:
  - `BUSINESS_ASSISTANT_ROLLOUT_STAGE`: Staged lifecycle gate (`disabled`, `internal_synthetic`, `owner_staging`, `enabled`).
  - `BUSINESS_ASSISTANT_SYNTHETIC_TENANT_IDS`: Comma-separated allowlist of synthetic tenant IDs for testing.
  - `BUSINESS_ASSISTANT_ALLOWLISTED_TENANT_IDS`: Comma-separated allowlist of staging tenant IDs.
- **Cryptographic Security**:
  - `SECRET_KEY`: Used for HMAC-SHA256 signing of business rule activations, website publication confirmations, and onboarding single-use save nonces.

---

## 4. Core Workflows & Contracts

### 4.1 Modular Tool Packs & Registry
The assistant accesses modular server-authorised tool packs defined in `tool_registry.py`:
1. **Product Help & Onboarding Pack**: `read_product_help`, `read_onboarding_progress`, `read_system_settings`.
2. **Booking & Availability Operations Pack**: `list_services`, `list_providers`, `check_slot_availability` (executes live 15-minute slot calculations via `compute_availability`; zero mocks).
3. **Business Knowledge & Curator Pack**: `list_curator_questions`, `draft_business_rule`, `get_business_rule`, `activate_business_rule`, `resolve_curator_question`.
4. **Customer Operations Pack**: `search_customer_conversations`, `get_customer_conversation_thread`, `prepare_customer_message_draft`, `create_campaign_proposal`.
5. **Support & Engineering Pack**: `create_support_ticket`, `get_ticket_status`, `list_support_tickets`, `request_ticket_approval`.
6. **Website Builder Pack**: `inspect_website_state`, `propose_website_edit`, `preview_website_edit`, `request_website_publication`, `rollback_website_version`.
7. **Diagnostic Pack**: `diagnostic_report` (evaluates 8-step live runbook, returning structured 5-part verdicts).
8. **Onboarding Pack**: `stage_fields`, `validate_form`, `request_save_authorization`, `commit_save`, `ask_clarification`, `pause_takeover`, `get_onboarding_status`.

### 4.2 Canonical 16-Tool Voice Schema (`VOICE_BUSINESS_ASSISTANT_TOOLS`)
To eliminate model confusion, hallucinated navigations, and token bloat during real-time voice sessions (across OpenAI Realtime, GPT-Live delegation, and xAI Grok Voice), the assistant maintains a canonical deduplicated 16-tool voice schema:
- **Navigation & UI (2 tools)**:
  - `navigate_route`: Single authoritative tool for switching administrative pages and sections.
  - `highlight_field`: Smoothly scrolls and applies non-intercepting focus rings to form controls.
- **Form & Onboarding Writes (6 tools)**:
  - `stage_fields`: Batches candidate form values into UI adapters without premature persistence (`staged_fields != saved`).
  - `validate_form`: Validates staged values against domain schemas.
  - `request_save_authorization`: Issues single-use HMAC confirmation nonce with 5-minute TTL.
  - `commit_save`: Authoritatively commits staged values after explicit user confirmation.
  - `ask_clarification`: Requests clarification on ambiguous user inputs without guessing.
  - `pause_takeover`: Acknowledges manual user takeover and pauses automation.
- **Essential Reads (6 tools)**:
  - `list_services`: Queries active tenant services, prices, and durations.
  - `list_providers`: Queries active staff providers and role boundaries.
  - `check_slot_availability`: Computes live 15-minute availability slots from the scheduling engine.
  - `get_onboarding_status`: Returns current onboarding setup progress and unanswered facts.
  - `read_system_settings`: Safely reads allowlisted business settings (hours, timezone, currency).
  - `diagnostic_report`: Evaluates live 8-step diagnostic runbook for troubleshooting.
- **Rule Writes (2 tools)**:
  - `draft_business_rule`: Drafts policy rules with dynamic fact rejection.
  - `activate_business_rule`: Activates drafted policy rules using cryptographic HMAC tokens.
- **Voice Schema Hygiene**: Redundant aliases and non-voice tools (`navigate_show`, `save_form`, `prepare_fields`, `fill_form`, `read_status`, `read_context`, `read_onboarding_progress`, `confirm_business_rule`, `create_maintenance_handoff`) are strictly omitted from voice sessions while remaining accessible in `ALL_BUSINESS_ASSISTANT_TOOLS` for text chat.

### 4.3 Dual Realtime Voice Transports

#### OpenAI Realtime / Direct WebRTC (`direct_gpt_live`)
- Negotiated via `POST /api/admin/business-assistant/conversations/{id}/realtime`.
- Relays RFC 4566 compliant SDP offers server-to-server with OpenAI `/v1/realtime/calls` using server-held credentials (`OPENAI_API_KEY`).
- Session definitions (`instructions` and `tools`) are retrieved via `GET /conversations/{id}/realtime/session` and dynamically injected upon data channel connection.
- Transcript deltas stream over WebRTC data channels and persist chronologically with `channel="realtime_voice"` via `POST /conversations/{id}/realtime/turns`.

#### xAI Grok Voice Transport (`xai_grok_voice`) & WebSocket Relay
- Provides low-latency conversational audio streaming powered by `grok-voice-think-fast-2.0`.
- **Token & Discovery Endpoint**: `GET /api/admin/business-assistant/realtime/xai-token` returns the agent ID, authenticated connection URL, API key, and local relay URL (`/api/admin/business-assistant/voice/realtime/xai-ws`).
- **WebSocket Audio Pipeline**: Frontend hook `useXAIGrokVoice` converts microphone audio to 16-bit PCM at 24kHz, streaming over WebSocket.
- **Tool Parsing & Execution**: Upstream tool calls are parsed via `parseRealtimeToolCalls`, executing UI RPC actions via `executeRpcAction` and backend tools via `POST /conversations/{id}/realtime/tools`.
- **Graceful Fallback**: Missing xAI credentials degrade cleanly to Direct WebRTC or text chat with descriptive diagnostic notifications.

### 4.4 Single-Tab Active Executor Lease Token Forwarding
To eliminate race conditions across multiple open browser tabs while preserving voice assistant capabilities:
- Across multiple tabs in a tenant session, only one designated tab acquires the exclusive `active_executor_lease` (`executor-coordinator.ts`).
- When voice assistants (`xai-grok-voice`, `direct-gpt-live`, `realtime-voice`) invoke RPC actions (`navigate_route`, `highlight_field`, `fill_fields`), language models do not attach client tab lease tokens to tool payloads.
- The action catalogue detects trusted voice caller identities and automatically extracts and forwards the active tab lease token (`leaseMgr.getActiveLease().token`), validating against `LeaseTokenManager`.
- This ensures voice commands executed from the active tab succeed seamlessly without failing lease validation, while maintaining strict isolation against background inactive tabs.

### 4.5 Route Normalization & Aliases
All navigation actions dispatched via text or voice pass through `normalizeRoute(rawRoute)`:
- Maps friendly identifiers and legacy paths to canonical admin routes:
  - `services`, `catalog`, `/admin/services`, `/admin/catalog` -> `/admin/catalog/services`
  - `website`, `website_editor` -> `/admin/website`
  - `media` -> `/admin/media`
  - `onboarding`, `settings`, `/admin/settings` -> `/admin/settings/business`
  - `bookings` -> `/admin/bookings`
- Strips query parameters and hash anchors before route evaluation.
- Strictly validated by `isRouteAllowlisted(targetPath)`: rejects protocol schemes (`javascript:`, `http://`, `https://`, `//`), directory traversal (`..`), and unallowlisted administrative paths.

### 4.6 Stock-Standard GPT-Live WebRTC Architecture
In `app/services/business_assistant/gpt_live/runtime.py` and `session_config.json`:
- **Zero Root Tools**: The root voice model (`gpt-live-1`) acts strictly as a conversational voice interface; `config["tools"]` is strictly omitted.
- **Stock Delegation Hierarchy**: Operational function tools reside exclusively within `delegation.responses.tools` for the reasoning model (`gpt-5.6-terra`), populated directly from `VOICE_BUSINESS_ASSISTANT_TOOLS` with `tool_choice: "auto"`.
- **Payload Sanitization**: `sanitize_gpt_live_session_payload` strips unauthorized top-level keys before sending session offers to OpenAI, preventing HTTP 400 `unknown_parameter` errors.

### 4.7 Text API Contract
Mounted at `/api/admin/business-assistant`:
- `GET /conversations`: Lists authenticated user's tenant-scoped conversations.
- `POST /conversations`: Creates a conversation with optional idempotency key.
- `GET /conversations/{id}/messages`: Returns chronological message history.
- `POST /conversations/{id}/messages`: Submits user turn, executes bounded function calling loop, records tool telemetry, and persists assistant response.
- `POST /conversations/{id}/tools`: Executes allowlisted tool directly through policy engine.

### 4.8 Business Knowledge & Curator API Contract
- `POST /knowledge/rules/draft`: Drafts business rules, validates against dynamic facts, and returns HMAC confirmation token.
- `GET /knowledge/rules`: Lists tenant-scoped business rules.
- `GET /knowledge/rules/{id_or_key}`: Retrieves rule definition and stored assistant interpretation.
- `POST /knowledge/rules/{id_or_key}/activate`: Confirms and activates rule via cryptographic token, syncing into `CuratedMemory`.
- `GET /knowledge/curator/questions`: Lists pending curator questions.
- `POST /knowledge/curator/questions/{id}/resolve`: Resolves or dismisses curator items.

### 4.9 Support Ticket API Contract & Closed Engineering Gate
- `POST /tickets`: Creates sanitized support, bug, or security tickets. Tickets in `access` or `security` categories trigger an immediate triage stop gate requiring owner approval.
- `GET /tickets`: Lists tickets in tenant scope.
- `GET /tickets/{id}/events`: Returns append-only lifecycle events (`created`, `duplicate_referenced`, `approval_requested`, `owner_approved`, `owner_rejected`, `worker_claimed`).
- `POST /tickets/{id}/approve` & `POST /tickets/{id}/reject`: Owner authorization gates for elevated tickets.
- **Closed Dispatch Gate**: Automatic coding worker execution remains strictly disabled; tickets stay in `awaiting_engineering` until explicit owner action.

### 4.10 Website Builder API & Lifecycle Contract
- `GET /website/state`: Returns live website configuration, active version, and pending proposals.
- `POST /website/proposals`: Creates draft website edit proposals with recursive XSS and PII sanitisation.
- `GET /website/proposals/{id}/preview`: Generates merged live preview and advances state to `preview`.
- `POST /website/proposals/{id}/request-publish`: Generates HMAC confirmation token for publication.
- `POST /website/proposals/{id}/publish`: Restricted to tenant owners; requires valid confirmation token.
- `POST /website/rollback`: Safely rolls back live website to a specified prior version.

### 4.11 Diagnostic Mode & 8-Step System Runbook Persistence
- `GET/PATCH /api/admin/business-assistant/diagnostic-mode`: Toggles diagnostic mode across tenant and user scope.
- When enabled, `diagnostic_report` evaluates the live 8-step runbook (session configuration, attached tool inventory, tool run logs, client snapshot state, navigation allowlists, onboarding plan, backend error logs, user permissions).
- Outputs structured 5-part verdicts (Verdict, Working Subsystems, Issues & Degradations, Operating Boundaries, Recommended Next Steps) persisted directly into `conversation_messages` with expandable `<details>`.

### 4.12 Autonomous Ticket Bridge & Codex Control Centre (CCC) Dispatch
Bridges support tickets (`SupportTicket`) in `awaiting_engineering` to local Codex Control Centre autonomous engineering workers:
- **Dispatch to CCC**: `POST /api/admin/business-assistant/tickets/{ticket_id}/dispatch-ccc`
  - Validates tenant-scoped ownership and constructs a comprehensive remediation prompt containing ticket summary, category, severity, observed behaviour, affected product area, user impact, and acceptance criteria.
  - Creates dedicated remediation thread in CCC (`POST /codex/threads`) targeting isolated worktree sandbox (`worktrees/wt-{ticket_id}`).
  - Starts autonomous remediation turn (`POST /codex/turns/start`).
  - Transitions ticket status to `in_progress`, binds `coding_task_id`, and records `dispatched_to_ccc` audit event.
- **Background SSE Stream & Milestone Tracking**:
  - Connects to `/codex/events/fastapi-bookings/{thread_id}` stream.
  - Automatically records milestones: `engineering_turn_started`, `command_executed`, `file_modified`, `clarification_requested`, `engineering_turn_completed`, `engineering_error`.
  - On `turn_completed` with `completed` status, advances ticket status to `awaiting_verification`.
- **In-Session Clarification & Natural Language Steering**:
  - When worker requests clarification or command approval (`clarification_requested`), an assistant message is injected into the active Business Assistant conversation for staff guidance.
  - Staff / Grok voice assistant can reply or steer via `POST /api/admin/business-assistant/tickets/{ticket_id}/steer`, forwarding instructions to `POST /codex/turns/steer` and logging `engineering_steer_sent`.
- **UI Verification Receipts & Resolution**:
  - Frontend Ticket Cockpit triggers UI inspection actions (`verify_ui_state`).
  - `POST /api/admin/business-assistant/tickets/{ticket_id}/verify-receipt` records receipt metadata (`route`, `verified_elements`, `resolution_summary`) via `ui_verification_receipt` event and marks ticket `resolved`.

---

## 5. Data Safety & Isolation

- **Authoritative Scoping**: Every repository, router, and adapter query strictly requires authoritative `tenant_id` and initiating `user_id`. Cross-tenant queries return HTTP 404.
- **Dynamic Facts Prohibition**: Operational facts (real-time availability slots, calendar bookings, current pricing, temporal references) are forbidden from static knowledge rules and must be resolved through live domain services.
- **Cryptographic Confirmation Binding**: All sensitive state transitions (business rule activations, website publications, consequential onboarding saves) require single-use HMAC-SHA256 tokens bound to tenant, initiating user, exact version, and payload hash.
- **Secret Scrubbing**: Server-side scrubbing via `scrub_sensitive_secrets()` redacts API keys, JWT tokens, `.env` credentials, and database connection strings from assistant responses and audit telemetry.
- **Telemetry Privacy**: Tool audit records (`business_assistant_tool_runs`) store structural metadata only (`tool_name`, `status`, `duration_ms`). Raw arguments, results, and speech audio are never persisted in telemetry.
- **Zero Legacy Reference Dependencies**: Runs 100% natively in FastAPI Bookings with zero runtime imports or database dependencies on legacy codebases.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Multi-Tab Lease Contention**: When multiple browser tabs are open, background tabs must explicitly claim the active executor lease via the UI dock or `/lease` endpoint before executing mutating form automations.
- **Voice Assistant Lease Forwarding**: Voice callers (`xai-grok-voice`, `direct-gpt-live`) running in the active tab automatically inherit the active lease token, but sessions initiated from an inactive tab will prompt the user to claim active control.
- **Autonomous Publishing & Live Messaging**: Conversational auto-publishing and live SMS broadcasting remain strictly gated behind owner review and cryptographic tokens.
- **Microphone Permissions**: Declining browser microphone access gracefully disables voice features while preserving full interactive text chat.

---

## 7. Verification & Testing Commands

Execute backend and contract test suites using the project Python environment:

```powershell
# 1. Run core Business Assistant foundation and API tests
.\.venv\Scripts\python.exe -m pytest tests/test_business_assistant_foundation.py `
  tests/test_business_assistant_api.py `
  tests/test_business_assistant_tickets_api.py `
  tests/test_ccc_bridge.py `
  tests/test_business_assistant_idempotency.py `
  tests/test_business_assistant_onboarding_api.py `
  tests/test_business_assistant_realtime_api.py `
  tests/test_business_assistant_tool_registry.py `
  tests/test_business_assistant_coding_worker.py `
  tests/test_business_assistant_realtime_voice.py `
  tests/test_business_assistant_website_builder.py `
  tests/test_business_assistant_hardening_and_rollout.py `
  tests/test_business_assistant_diagnostic_mode.py -v

# 2. Run Voice Transport and Realtime Integration tests
.\.venv\Scripts\python.exe -m pytest tests/test_voice_transport_toggle.py `
  tests/test_gpt_live.py -v

# 3. Verify Living Documentation compliance (Rule 10)
.\.venv\Scripts\python.exe scripts/verify_living_docs.py --path app/services/business_assistant/README.md
```
