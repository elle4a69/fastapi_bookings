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
├── tool_registry.py     # Modular tool packs (product help, booking, business knowledge)
├── realtime.py          # Server-held SDP exchange for authenticated voice sessions
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
- Ticket summaries are normalised before persistence. Secrets and direct
  customer identifiers are rejected rather than silently retained or relayed.
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

## Configuration and dependencies

The package uses the application SQLAlchemy session, existing `tenants`,
`users`, `services`, `providers`, `locations`, `curated_memories`, and
`knowledge_proposals` tables, migrations `g7h9j1k3m5n7`, `h8j0k2m4n6p8`, and
`p1q2r3s4t5u6`. The text path uses only validated application settings:
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

The assistant accesses three modular server-authorised tool packs:

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

### Realtime voice contract

- `POST /conversations/{id}/realtime` accepts a bounded `application/sdp`
  offer and relays it server-side to the provider's `/v1/realtime/calls`
  contract, returning the live provider answer as `application/sdp` with
  `Cache-Control: no-store`.
- `POST /conversations/{id}/realtime/turns` persists an authenticated completed
  transcript pair with stable session/event IDs and returns `user_message`,
  `assistant_message`, and `duplicate_turn`.

### Onboarding and product-help context

- `GET /onboarding` returns personal progress plus a live, read-only setup
  snapshot.
- `PUT /onboarding/progress` records one fixed personal milestone only. It
  never changes tenant configuration or any business record.

### Support-ticket API contract

- `POST /tickets` creates a sanitised support, bug, feature, access, security,
  or upgrade ticket. Every accepted ticket remains `awaiting_engineering`.
- `GET /tickets` lists only the current authenticated user's tickets in that
  tenant.
- `GET /tickets/{id}` and `GET /tickets/{id}/events` enforce the same object
  boundary and return user-safe ticket fields and append-only public events.

## Current limitations

Live customer SMS broadcast, external worker dispatch, and autonomous website
publication belong to later work packages after their specific gates pass.
Schema reconciliation preserves existing rows and is deliberately non-reversible;
database rollback procedures must restore from a verified backup rather than
dropping feature tables.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_business_assistant_foundation.py tests/test_business_assistant_api.py tests/test_business_assistant_tickets_api.py tests/test_business_assistant_idempotency.py tests/test_business_assistant_onboarding_api.py tests/test_business_assistant_realtime_api.py tests/test_business_assistant_tool_registry.py tests/test_business_assistant_adapters.py tests/test_business_assistant_tool_execution.py tests/test_business_assistant_knowledge_curation.py -q
```
