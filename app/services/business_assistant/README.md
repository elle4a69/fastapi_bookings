# Business Assistant Foundation

## Purpose and scope

This package owns tenant- and user-scoped persistence operations and bounded
text generation for internal Business Assistant conversations. It deliberately
excludes tools, realtime media, external messaging, booking changes, coding
worker dispatch, deployment, and direct database access by a model.

## Architecture and key files

```text
app/services/business_assistant/
├── repository.py  # Scoped SQLAlchemy persistence operations
├── runtime.py     # Configured bounded provider request and tool-call loop
├── service.py     # Persist-before-generation text-turn coordinator
├── tickets.py     # Ticket-summary safety checks and duplicate fingerprinting
├── idempotency.py # Canonical payload hashes and key-reuse conflict checks
├── product_context.py # Read-only allowlisted native setup snapshot
├── tool_registry.py # Two server-authorised product-help read tools
├── realtime.py    # Server-held SDP exchange for authenticated voice sessions
└── __init__.py    # Public package exports
```

The ORM records are in `app/models/business_assistant.py` and validation
contracts are in `app/schemas/business_assistant.py`. They are intentionally
separate from customer conversation and message tables.

## Data safety and isolation

- Every repository instance requires an authoritative tenant ID and user ID.
- Reads and writes filter both tenant and initiating user ownership.
- Conversation, text-turn, and ticket request keys are bound to a canonical
  payload hash. Reusing a key with changed content returns a conflict rather
  than a prior result.
- Active duplicate ticket content is resolved only within the same tenant and
  user. A separate active-ticket claim table provides portable uniqueness while
  allowing a later transactional close workflow to release the claim.
- Ticket summaries are normalised before persistence. Secrets and direct
  customer identifiers are rejected rather than silently retained or relayed.
- Ticket lifecycle events are append-only and user-safe. This workflow creates
  only the initial `created` event with `awaiting_engineering` status.
- Tool audit records contain structural metadata only. Raw tool arguments,
  results, credentials, and worker logs must not be persisted there.

## Configuration and dependencies

The package uses the application SQLAlchemy session, existing `tenants` and
`users` tables, and migrations `g7h9j1k3m5n7` and `h8j0k2m4n6p8`. The latter is
an additive reconciliation migration for an environment where the foundation
tables were created before their Alembic revision was recorded: it creates any
absent foundation tables and repairs the conversation creation/idempotency
columns, constraint, and scope index without resetting data. The text path uses only validated
application settings: `OPENAI_API_KEY`, `BUSINESS_ASSISTANT_TEXT_MODEL`,
`BUSINESS_ASSISTANT_MAX_HISTORY_MESSAGES`,
`BUSINESS_ASSISTANT_MAX_OUTPUT_TOKENS`, and
`BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS`. Missing provider configuration
returns an explicit error after the user message has been safely persisted.
`BUSINESS_ASSISTANT_MAX_TOOL_ROUNDS` bounds product-help read-tool rounds.
Realtime voice uses server-held `OPENAI_API_KEY`,
`BUSINESS_ASSISTANT_REALTIME_MODEL`, and
`BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES`; absent configuration returns an
explicit unavailable result rather than a simulated exchange.

## Text API contract

The authenticated owner/admin route is mounted at `/api/admin/business-assistant`:

- `GET /conversations` lists the current user's tenant-scoped conversations.
- `POST /conversations` creates a conversation with an optional idempotency key.
- `GET /conversations/{id}/messages` returns bounded chronological history.
- `POST /conversations/{id}/messages` persists one user turn, makes one bounded
  text generation request, executes at most the configured number of
  server-authorised read tools, then persists the reply.

The request key on a text turn binds retries to the original persisted user
message and completed reply. A database claim marks a pending generation as
`running`; concurrent duplicates receive an explicit in-progress outcome and
cannot issue another provider call. Failed turns are marked retryable. No provider call can mutate bookings, send a
message, dispatch engineering work, or perform coding activity.

Text startup returns privacy-safe categories: `TEXT_CONFIGURATION_REQUIRED`
when the server lacks a text model setting, `TEXT_CLIENT_UNAVAILABLE` when the
configured client package is absent, and `TEXT_PROVIDER_UNAVAILABLE` after a
configured provider request fails. `TEXT_PROVIDER_REQUEST_REJECTED` identifies
a safe provider-side request rejection without exposing upstream response
bodies. These messages never expose credentials or provider response bodies.

The configured text model uses the provider's Chat Completions compatibility
path with `max_completion_tokens`; do not substitute the retired
`max_tokens` parameter for this model family. Tool-enabled requests also set
`reasoning_effort` to `none`, which is required by this model on that endpoint.
The client factory receives `api_key` by keyword so the configured provider
client's keyword-only constructor is used consistently.

The initial tool pack contains only `read_product_help` and
`read_onboarding_progress`. Their schemas accept no model-selected identifiers
and call tenant/user-scoped native reads. Each invocation persists structural
audit metadata only; tool arguments and results are never retained in a run.

## Realtime voice contract

- `POST /conversations/{id}/realtime` accepts a bounded `application/sdp`
  offer and relays it server-side to the provider's `/v1/realtime/calls`
  contract, returning the live provider answer as `application/sdp` with
  `Cache-Control: no-store`.
- `POST /conversations/{id}/realtime/turns` persists an authenticated completed
  transcript pair with stable session/event IDs and returns `user_message`,
  `assistant_message`, and `duplicate_turn`.

Transcript pairs are inserted transactionally with `realtime_voice` provenance
and unique tenant/user/conversation/session/event identity. Voice has no tools
and cannot access a broader capability set than text.

Voice startup returns privacy-safe categories rather than a generic failure:
`REALTIME_CONFIGURATION_REQUIRED` (a server setting is absent),
`REALTIME_INVALID_SDP` (the browser offer is invalid), or
`REALTIME_PROVIDER_UNAVAILABLE` (the configured provider cannot establish a
session). Category messages never include credentials or upstream response
bodies. The current local runtime has an API key configured but no realtime
model selected; setting `BUSINESS_ASSISTANT_REALTIME_MODEL` to an approved
provider-enabled model and allowing the backend reload is required before a
browser can start voice.

## Onboarding and product-help context

- `GET /onboarding` returns personal progress plus a live, read-only setup
  snapshot.
- `PUT /onboarding/progress` records one fixed personal milestone only. It
  never changes tenant configuration or any business record.

The snapshot is deliberately limited to enabled module keys and aggregate
counts of active services, providers, and locations. It is read from native
tenant-scoped records for each request. If those reads cannot be completed,
the API reports `unavailable` and returns no invented setup facts. The bounded
text runtime receives this same allowlisted context as a system data message;
it receives no operational tools.

## Support-ticket API contract

- `POST /tickets` creates a sanitised support, bug, feature, access, security,
  or upgrade ticket. Every accepted ticket remains `awaiting_engineering`.
- `GET /tickets` lists only the current authenticated user's tickets in that
  tenant.
- `GET /tickets/{id}` and `GET /tickets/{id}/events` enforce the same object
  boundary and return user-safe ticket fields and append-only public events.

The API has no worker connector, private work instructions, source access,
or dispatch behaviour. A duplicate active ticket returns its existing public
record; it does not create another event or contact an external service.
A future ticket-resolution workflow must delete the corresponding active claim
in the same transaction as the status transition; until that approved workflow
exists, all tickets remain `awaiting_engineering`.

## Current limitations

Confirmation-controlled mutations, memory activation, ticket triage, and worker
dispatch belong to later work packages after their contracts are approved.
Schema reconciliation preserves existing rows and is deliberately non-reversible;
database rollback procedures must restore from a verified backup rather than
dropping feature tables.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_business_assistant_foundation.py tests/test_business_assistant_api.py tests/test_business_assistant_tickets_api.py tests/test_business_assistant_idempotency.py tests/test_business_assistant_onboarding_api.py tests/test_business_assistant_realtime_api.py tests/test_business_assistant_tool_registry.py -q
```
