# Business Assistant Foundation

## Purpose and scope

This package owns tenant- and user-scoped persistence operations, bounded
text generation, and server-authorised tool execution for internal Business
Assistant conversations. It supports conversational onboarding, live product
help, tenant settings discovery, real-time appointment availability inquiry,
and authoritative business knowledge curation.
It deliberately excludes synthetic mocks, unconfirmed booking writes, customer
messaging, coding worker dispatch, deployment, and direct database access by a
model.

## Architecture and key files

```text
app/services/business_assistant/
├── repository.py        # Scoped SQLAlchemy persistence, memory lifecycle, and tool telemetry
├── runtime.py           # Configured bounded provider request and function-calling loop
├── service.py           # Turn coordinator, business rule drafting/activation, and curator workflows
├── confirmation.py      # Cryptographic confirmation tokens and dynamic-fact rejection policy
├── tickets.py           # Ticket-summary safety checks and duplicate fingerprinting
├── idempotency.py       # Canonical payload hashes and key-reuse conflict checks
├── product_context.py   # Read-only allowlisted native setup snapshot
├── tool_registry.py     # Modular tool packs (product help, booking, business knowledge, website builder)
├── website_sanitiser.py # XSS, script injection, PII sanitiser and asset domain validator
├── realtime.py          # Server-held SDP exchange for authenticated voice sessions
├── coding_worker.py     # Real isolated coding-worker connector, scope inspector & verification runner
├── adapters/
│   ├── reads.py         # Scoped native read adapters for product help, settings, and scheduling
│   └── __init__.py      # Adapter exports
└── __init__.py          # Public package exports
```

The ORM records are in `app/models/business_assistant.py` and validation
contracts are in `app/schemas/business_assistant.py`. They are intentionally
separate from customer conversation and message tables.

## Data safety and isolation

- Every repository and adapter instance requires an authoritative tenant ID
  and user ID.
- Reads and writes filter both tenant and initiating user ownership.
- Sensitive settings and credentials (passwords, tokens, API keys, private IDs)
  are scrubbed; only allowlisted, safe business parameters are exposed.
- Tool arguments and results are validated by strict JSON schemas; model-chosen
  tenant or user IDs are forbidden.
- Scheduling slot inquiries execute real database availability calculation
  via `app.services.scheduling_service.compute_availability` without mocks.
- Role-awareness is strictly enforced: staff users with the `provider` role
  may only inspect their own schedules, while owners/managers have tenant-wide scope.
- Conversation, text-turn, and ticket request keys are bound to a canonical
  payload hash. Reusing a key with changed content returns a conflict rather
  than a prior result.
- Active duplicate ticket content is resolved only within the same tenant and
  user. A separate active-ticket claim table provides portable uniqueness while
  allowing a later transactional close workflow to release the claim.
- Ticket summaries are normalised before persistence. Secrets (private keys,
  bearer/JWT tokens, database URLs, API tokens, passwords) and direct customer
  identifiers (emails, phone numbers, credit cards, SSN/TFN) are strictly rejected
  across all text fields rather than silently retained or relayed.
- **Active Duplicate Ticket Detection**: Deduplication keys are computed from
  tenant scope, category, affected product area, and normalized title. When an active
  ticket (`awaiting_engineering`, `triaged`, `in_progress`, `pending_approval`,
  `pending_owner_approval`) already exists, subsequent submissions return the
  existing ticket with `duplicate_ticket=True` and append a `duplicate_referenced`
  lifecycle event.
- **Access / Security Approval Stop-Gate**: Tickets in `access` or `security`
  categories immediately trigger a triage stop gate: `status="pending_owner_approval"`,
  `authorisation_state="pending_approval"`, and `requires_owner_approval=True`.
  Only authenticated tenant owners may approve or reject elevated dispatch.
- **Closed Dispatch Gate**: Automatic coding worker dispatch remains strictly disabled
  while the worker gate is closed. Accepted and approved tickets remain in
  `status="awaiting_engineering"`; no worker processes are spawned.
- **Append-Only Lifecycle Events**: Every ticket transition is immutably recorded
  in `SupportTicketEvent` (`created`, `duplicate_referenced`, `approval_requested`,
  `owner_approved`, `owner_rejected`), ensuring an auditable and user-safe history.
- Tool audit records (`business_assistant_tool_runs`) contain structural
  metadata only (`tool_name`, `status`, `duration_ms`). Raw tool arguments,
  results, credentials, and worker logs are never persisted in telemetry.
- **Drafting vs. Activation Separation**: Users can draft business policies and
  inspect the assistant's structured interpretation without external effect.
  Drafts remain non-operational (`status="draft"`) until explicit activation.
- **Confirmation Binding**: Activating a business rule requires a cryptographic
  HMAC confirmation token bound to tenant, initiating user, target rule key,
  exact version, and payload hash. Tokens cannot be reused across versions,
  users, or tenants.
- **Dynamic Facts Prohibition**: Operational facts (live availability slots,
  calendar bookings, current pricing, specific booking IDs, temporal references,
  customer PII) are strictly rejected from static business knowledge and must
  be resolved via live domain services.
- **Actor and Provenance Tracking**: Every rule draft and activation records
  authoritative actor `user_id`, timestamps, and detailed provenance. Active
  rules sync into `CuratedMemory` for platform-wide knowledge retrieval.
- **Strict Separate Website Lifecycle (WP10)**: Website content changes advance across
  strict separate states: `draft` -> `preview` -> `published` -> `rolled_back`.
  Edits are created in `draft` status, rendered in `preview`, and can only be published
  via an explicit publication gate.
- **Prohibition of Conversational Auto-Publish**: Website publication CANNOT occur
  from ordinary conversational confirmation alone. It requires explicit owner authorization,
  optimistic version validation, and a cryptographically signed HMAC confirmation token.
- **Content Sanitisation & Injection Rejection**: Website edits recursively reject XSS scripts,
  `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, javascript: protocols, event handlers
  (`onerror=`, `onload=`, `onclick=`), and `eval()`.
- **Customer PII & Asset Domain Guardrails**: Public website proposals reject customer PII
  (names, credit cards, customer phone numbers, customer emails). External media assets are
  strictly scoped to allowlisted tenant domains and approved image hosts (e.g. Unsplash CDN,
  tenant custom domain).
- **Optimistic Version Concurrency & Rollback**: Proposals enforce optimistic concurrency
  checks to prevent concurrent overwrite. Owners can roll back to any previously published version,
  creating a new rollback proposal and restoring live website content safely.

## Configuration and dependencies

The package uses the application SQLAlchemy session, existing `tenants`,
`users`, `services`, `providers`, `locations`, `curated_memories`,
`tenant_websites`, and `knowledge_proposals` tables, migrations `g7h9j1k3m5n7`,
`h8j0k2m4n6p8`, `p1q2r3s4t5u6`, `u5v6w7x8y9z0`, `v7w8x9y0z1a2`, and `w8x9y0z1a2b3`. The text path uses only validated application settings:
`OPENAI_API_KEY`, `BUSINESS_ASSISTANT_TEXT_MODEL`,
`BUSINESS_ASSISTANT_MAX_HISTORY_MESSAGES`,
`BUSINESS_ASSISTANT_MAX_OUTPUT_TOKENS`, and
`BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS`. Missing provider configuration
returns an explicit error after the user message has been safely persisted.
`BUSINESS_ASSISTANT_MAX_TOOL_ROUNDS` bounds tool-calling rounds.
Realtime voice uses server-held `OPENAI_API_KEY`,
`BUSINESS_ASSISTANT_REALTIME_MODEL`, and
`BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES`; absent configuration returns an
explicit unavailable result rather than a simulated exchange.

## Core workflows and contracts

### Tool execution engine and tool packs

The assistant accesses five modular server-authorised tool packs:

1. **Product Help & Onboarding Pack:**
   - `read_product_help`: Returns live setup metrics (active services, providers,
     locations, enabled modules).
   - `read_onboarding_progress`: Reads caller's personal onboarding progress
     and durable milestones.
   - `read_system_settings`: Safely reads allowlisted tenant configurations
     (timezone, booking window, business profile) with sensitive credentials stripped.
2. **Booking & Availability Operations Pack:**
   - `list_services`: Lists active services in the tenant with durations, pricing,
     and buffers.
   - `list_providers`: Lists eligible staff providers, respecting service filters
     and provider role bounds.
   - `check_slot_availability`: Computes live 15-minute slot availability via the
     scheduling engine (`compute_availability`), taking into account provider workdays,
     special day overrides, existing bookings, and buffer times. Zero mocks are used.
3. **Business Knowledge & Curator Pack:**
   - `list_curator_questions`: Lists unresolved or pending curator questions
     scoped strictly to the tenant.
   - `draft_business_rule`: Drafts a business rule, validates against dynamic
     operational facts, and returns assistant interpretation and confirmation token.
   - `get_business_rule`: Inspects a drafted or active business rule and its stored
     assistant interpretation.
   - `activate_business_rule`: Confirms and activates a rule with cryptographic
     token bound to exact version and payload hash.
   - `resolve_curator_question`: Resolves or dismisses a curator item within tenant
     scope.
4. **Customer Operations Pack:**
   - `search_customer_conversations`: Searches authorised customer conversations
     within the tenant, automatically scoped to provider ID for staff with provider role.
   - `get_customer_conversation_thread`: Inspects customer conversation thread,
     recent messages, and client opt-in/opt-out status with masked PII preview.
   - `prepare_customer_message_draft`: Prepares a response message draft with versioning,
     idempotency, and confirmation token. Never executes live sending.
   - `create_campaign_proposal`: Evaluates server-authoritative audience selection with
     explainable inclusion/exclusion criteria, snapshotting recipients and issuing an approval token.
5. **Support & Engineering Pack:**
   - `create_support_ticket`: Creates a sanitised support or engineering ticket with
     structured attributes (`observed_behaviour`, `affected_product_area`, `user_impact`,
     `acceptance_criteria`) without automatic worker dispatch.
   - `get_ticket_status`: Inspects user-safe status and lifecycle events for an existing ticket.
   - `list_support_tickets`: Lists user-safe support tickets with optional status and category filters.
   - `request_ticket_approval`: Requests a confirmation token for an elevated access or security ticket.
6. **Website Builder Pack (WP10):**
   - `inspect_website_state`: Inspects the active tenant's website configuration, published status,
     current live version, and pending draft proposals.
   - `propose_website_edit`: Proposes bounded content, layout, template, or theme edits. Edits
     remain safely in draft state and cannot publish automatically.
   - `preview_website_edit`: Renders a full preview of proposed website changes merged with the live site
     and advances proposal status from `draft` to `preview`.
   - `request_website_publication`: Generates a cryptographic HMAC confirmation token for publication.
     Publication CANNOT occur through ordinary conversational confirmation alone.
   - `rollback_website_version`: Safely rolls back the website configuration to a previously published
     version with optimistic concurrency checks.

### Website Builder API and lifecycle contract (WP10)

- `GET /website/state`: Returns the active tenant's live website configuration, publication timestamp,
  active version, pending draft status, and recent proposal history.
- `POST /website/proposals`: Creates a versioned website edit proposal in `status="draft"`. Enforces
  recursive XSS sanitisation, PII filtering, asset domain allowlisting, and optimistic version checks.
- `GET /website/proposals/{id}/preview`: Renders a comprehensive live preview merged with the tenant's
  current website configuration, transitioning proposal status to `preview`.
- `POST /website/proposals/{id}/request-publish`: Generates a cryptographic HMAC confirmation token
  bound to proposal ID, version, and payload hash for explicit presentation to the tenant owner.
- `POST /website/proposals/{id}/publish`: Strictly restricted to authenticated tenant owners. Validates
  the confirmation token signature and payload hash before transitioning the proposal to `published`
  and updating `tenant_websites` to live.
- `POST /website/rollback`: Reverts the website configuration to a specified prior version, generating
  a new published proposal recording `rollback_version` and restoring live content safely.


### Text API contract

Mounted at `/api/admin/business-assistant`:

- `GET /conversations` lists the current user's tenant-scoped conversations.
- `POST /conversations` creates a conversation with an optional idempotency key.
- `GET /conversations/{id}/messages` returns bounded chronological history.
- `POST /conversations/{id}/messages` persists one user turn, makes one bounded
  text generation request, executes server-authorised tools through the function
  calling loop, records tool run telemetry, and persists the reply.
- `POST /conversations/{id}/tools` and `POST /conversations/{id}/realtime/tools`
  execute an allowlisted tool directly through the policy engine, returning structured
  results and recording telemetry.

### Business Knowledge and Curator API contract

- `POST /knowledge/rules/draft` drafts a business rule, checks for forbidden dynamic
  facts, persists a draft record, and returns an authoritative confirmation token.
- `GET /knowledge/rules` lists tenant-scoped business rules with optional status filter.
- `GET /knowledge/rules/{id_or_key}` retrieves a business rule and its interpretation.
- `POST /knowledge/rules/{id_or_key}/activate` activates a drafted rule using its
  cryptographically bound confirmation token, resolving any linked curator question
  and syncing into `CuratedMemory`.
- `GET /knowledge/curator/questions` lists pending curator questions in the current tenant.
- `POST /knowledge/curator/questions/{id}/resolve` marks a curator proposal as resolved,
  dismissed, or rejected.

### Customer Operations & Campaign Proposals API contract

- `GET /customer/conversations` searches customer conversations within tenant and provider boundary.
- `GET /customer/conversations/{id}` retrieves thread messages and opt-in/opt-out status.
- `POST /customer/conversations/{id}/draft` prepares a draft response with confirmation token.
- `GET /customer/drafts` lists prepared response drafts in tenant scope.
- `GET /customer/drafts/{id}` retrieves a specific response draft.
- `POST /campaigns/audience-preview` evaluates and previews server-authoritative audience criteria.
- `POST /campaigns/proposals` persists an explainable campaign proposal with confirmation token.
- `GET /campaigns/proposals` lists campaign proposals in the active tenant.
- `GET /campaigns/proposals/{id}` retrieves a campaign proposal by ID.
- `POST /campaigns/proposals/{id}/approve` approves a campaign proposal using its confirmation token; live broadcasting remains strictly disabled.

### Realtime voice contract (WP8)

- `POST /conversations/{id}/realtime`:
  - Validates inbound WebRTC SDP offers against RFC 4566 specifications (`v=0` header line, valid UTF-8, non-empty) and payload size limit (`BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES`, default 64 KB).
  - Validates request `Origin` header against configured `FRONTEND_ORIGINS` and request `Host`.
  - Securely relays the offer server-side to OpenAI `/v1/realtime/calls` using server-held credentials (`OPENAI_API_KEY`). API keys are never exposed to the client.
  - Classifies errors cleanly without simulated mock fallbacks:
    - `REALTIME_CONFIGURATION_REQUIRED`: Missing provider API key or model configuration.
    - `REALTIME_INVALID_SDP`: Non-RFC-compliant, malformed, empty, or oversized SDP body.
    - `REALTIME_PROVIDER_UNAVAILABLE`: Upstream provider unreachable, connection failure, or non-success status code.
  - Returns provider answer as `application/sdp` with `Cache-Control: no-store`.
- `POST /conversations/{id}/realtime/turns`:
  - Persists completed transcript pairs transactionally with `channel="realtime_voice"`.
  - Enforces transcript safety: empty or whitespace-only transcripts are rejected with 422 Unprocessable Entity, preventing partial or interrupted utterances from triggering side effects.
  - Validates distinct item IDs (`user_item_id != assistant_response_id`).
  - Enforces turn deduplication and idempotency on `(tenant_id, conversation_id, session_id, item_id)`. Re-submitting an existing completed turn returns `duplicate_turn=True` without duplicate database rows.
  - Persisted voice turns are chronologically integrated with text turns and visible via `GET /conversations/{id}/messages`.
- `POST /conversations/{id}/realtime/tools`:
  - Enforces absolute tool parity across all 5 server-authorised tool packs (`product_help`, `booking_availability`, `business_knowledge`, `customer_operations`, `support_engineering`). Voice sessions cannot access unallowlisted or broader tools than text sessions.
  - Enforces strict confirmation policy parity: side-effecting operations (e.g. activating business rules, preparing customer drafts) require valid cryptographic confirmation tokens.
  - Rejects forbidden, unknown, or unallowlisted tools with structured JSON error responses.
  - Records structural audit telemetry in `business_assistant_tool_runs` (`tool_name`, `status`, `duration_ms`), never persisting raw arguments, results, or credentials.
- Graceful degradation:
  - If realtime voice is unconfigured or upstream unavailable, clients cleanly fall back to standard text conversation endpoints without corruption or state loss.

### Onboarding and product-help context

- `GET /onboarding` returns personal progress plus a live, read-only setup
  snapshot.
- `PUT /onboarding/progress` records one fixed personal milestone only. It
  never changes tenant configuration or any business record.

### Support-ticket API contract

- `POST /tickets` creates a sanitised support, bug, feature, access, security,
  or upgrade ticket. For ordinary categories, accepted tickets remain `awaiting_engineering`.
  For `access` and `security` categories, tickets stop at `pending_owner_approval` with
  `requires_owner_approval=True` and issue a cryptographically bound confirmation token.
  Active duplicate tickets return the existing ticket with `duplicate_ticket=True` and
  append a `duplicate_referenced` lifecycle event.
- `GET /tickets` lists user-safe tickets in tenant scope with optional `status`
  and `category` query filters.
- `GET /tickets/{id}` and `GET /tickets/{id}/events` enforce object boundaries and
  return user-safe ticket fields and append-only lifecycle events (`created`,
  `duplicate_referenced`, `approval_requested`, `owner_approved`, `owner_rejected`).
- `POST /tickets/{id}/approve` allows only tenant owners to approve elevated access/security
  tickets. Transitions status to `awaiting_engineering` and records `owner_approved`. The closed
  dispatch gate is preserved (no coding worker dispatch).
- `POST /tickets/{id}/reject` allows only tenant owners to reject elevated tickets.
  Transitions status to `rejected`, records `owner_rejected`, and releases the deduplication claim.

### Coding-worker connector contract (WP7 / Section 8.1)

The coding-worker connector (`CodingWorkerConnector` in `coding_worker.py`) provides an isolated,
authoritative execution bridge fulfilling all 9 hard requirements of Section 8.1 with zero synthetic mocks:

1. **Idempotent Claim**: Claiming an eligible ticket in `awaiting_engineering` atomically
   transitions `status="in_progress"`, generates a unique `coding_task_id` (`cw-...`) and cryptographically
   secure `claim_token`, and appends a `worker_claimed` event. Concurrent duplicate claims are rejected
   (`DuplicateClaimError`). Tickets with elevated approval requirements cannot be claimed without owner approval (`TicketNotEligibleError`).
2. **Authorised Scope Inspection**: The worker is strictly restricted to authorised repository paths
   (`app/`, `frontend/`, `tests/`, `docs/`, `alembic/`, `scripts/`). Path traversal (`../`), `.env*`, `.git/`,
   `*.key`, `*.pem`, `id_rsa*`, secrets, and credential patterns are prohibited and rejected (`ScopeAccessViolationError`).
3. **Bounded Change Creation**: Modifications stage inside an isolated scratch sandbox (`CodingWorkerWorkspace`)
   enforcing safety caps: maximum 10 modified files (`MAX_FILES`), maximum 1 MB per file (`MAX_BYTES_PER_FILE`),
   and maximum 1000 diff lines (`MAX_DIFF_LINES`), guarding against uncontrolled codebase mutations (`BoundedChangeViolationError`).
4. **Test Verification & Real Exit Results**: Subprocess execution of authorised test runners (`sys.executable`,
   `pytest`, `npm`) measures duration, captures actual integer exit code, scrubs secrets, normalises absolute
   paths, and bounds output to 4000 characters without leaking credentials (`TestVerificationRunner`).
5. **Independent Review Request**: On successful verification (exit code 0), tickets transition to `status="pending_review"`
   and generate a verifiable `ReviewBundle` (ticket ID, task ID, patch ID, diff summary, test result, user-safe summary).
   A `review_requested` lifecycle event is appended.
6. **Commit/Diff Identifier & Sanitised Summary**: Changes produce unified diff statistics (files changed, additions,
   deletions) and a SHA-256 patch identifier. A user-safe resolution summary is generated that omits machine-specific
   filesystem paths, private worker prompts, and internal tokens.
7. **Honest Failure**: When tests fail, files are inaccessible, or bounded limits are violated, tickets fail cleanly
   (`status="failed"`), record user-safe failure reasons and exit codes in `SupportTicketEvent(event_type="worker_failed")`,
   and release active deduplication claims without database corruption.
8. **Separation of Deployment**: The worker is architecturally barred from deploying or pushing to production.
   Calling `deploy()` or attempting deployment instructions raises `DeploymentSeparationError`. Deployments remain gated
   behind separate owner approval.
9. **Interruption Recovery**: `reconcile_interrupted_tickets` identifies orphaned in-progress tickets exceeding an
   inactivity threshold, safely transitioning them to `failed` (with claim release) or resetting them to `awaiting_engineering`
   for re-dispatch without duplicate execution.

## Current limitations

Live customer SMS broadcast and autonomous website publication belong to later
work packages after their specific gates pass. Schema reconciliation preserves
existing rows and is deliberately non-reversible; database rollback procedures
must restore from a verified backup rather than dropping feature tables.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_business_assistant_foundation.py tests/test_business_assistant_api.py tests/test_business_assistant_tickets_api.py tests/test_business_assistant_idempotency.py tests/test_business_assistant_onboarding_api.py tests/test_business_assistant_realtime_api.py tests/test_business_assistant_tool_registry.py tests/test_business_assistant_coding_worker.py tests/test_business_assistant_realtime_voice.py tests/test_business_assistant_website_builder.py -q
```



