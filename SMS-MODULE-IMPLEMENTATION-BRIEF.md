# FastAPI Bookings SMS Module — Implementation Brief

**Status:** Build contract for Antigravity  
**Target repository:** `F:\Projects\fastapi_bookings`  
**Purpose:** Add production-quality multi-provider SMS, customer conversations, and optional AI assistance *inside* FastAPI Bookings.  
**Authoritative business system:** FastAPI Bookings' existing providers, services, locations, schedules, clients, availability, bookings, notifications, and outbox.

## 1. Decision and outcome

Build the SMS system as a first-class, modular part of FastAPI Bookings. Do **not** embed, copy, or deploy a complete second Assistant UI application inside this repository.

The finished application must have one booking database and one source of truth:

```text
FastAPI Bookings
├─ existing booking domain
│  providers · services · locations · schedules · clients · bookings
│  confirmations · notifications · audit/outbox
│
└─ new SMS module
   ├─ provider adapter registry
   ├─ SMS accounts / phone lines
   ├─ inbound webhook handling
   ├─ conversations, messages, events and notes
   ├─ outbound delivery queue and receipts
   ├─ human inbox and simulator
   ├─ fixed autoresponders
   ├─ optional conversational AI and approval workflow
   ├─ provider-scoped knowledge and prompts
   └─ arrival and staff-notification workflow
```

The first configured transport is MobileMessage. It must be an adapter, **not** a special case baked into conversation, database, UI, or AI code. Future transports (for example Chatwoot, another SMS gateway, WhatsApp, email, or a simulator) must use the same normalized contract.

## 2. Non-negotiable principles

1. **FastAPI Bookings owns booking facts.** The AI and SMS module may ask booking-domain services to find availability or create/amend/cancel a booking. They must never calculate availability from cached messages, knowledge records, an independent calendar, or a duplicate booking table.
2. **One database, separated modules.** SMS tables live in the FastAPI Bookings database and reference existing entities by foreign key. They are not mixed into the existing booking tables or implemented as a second SQLite database.
3. **Every customer-visible action is provider/account scoped.** `provider_id` and `sms_account_id` are mandatory on all conversations, messages, knowledge, prompts, sender configuration, jobs, and delivery records.
4. **Inbound processing is idempotent and chronological.** A provider event may be delivered more than once or out of order; it must result in at most one stored inbound message and at most one response workflow for the final relevant customer turn.
5. **All outbound sends use a durable queue/outbox.** No request handler should call an SMS provider and treat an uncertain network outcome as safely completed.
6. **AI is optional and constrained.** The human inbox and manual SMS workflow must work with AI completely off. The AI can only use explicit internal tools and must never expose internal prompts, policies, tool arguments, hidden notes, credentials, or staff-only content.
7. **Do not merge applications blindly.** Reuse selected code patterns from Assistant UI; do not copy its database, booking implementation, large `main.py`, standalone settings files, or legacy background loops.
8. **No real test SMS without an explicit operational authorization.** Unit and integration tests use a fake provider adapter.

## 3. Scope: what the module must do

### 3.1 SMS account management

An administrator can create and manage multiple SMS sender accounts. An account represents one configured sender number/identity at one transport provider.

Each account has:

- an immutable ID;
- `provider_id` — the FastAPI Bookings provider/business it serves;
- `transport_type` — e.g. `mobilemessage`, `chatwoot`, `simulator`;
- a display name such as `Tori primary` or `Anonymous`;
- a sender address/phone number in canonical E.164 form where applicable;
- encrypted or externally referenced transport credentials; never return secrets to the browser;
- enabled/disabled state;
- inbound webhook configuration and verification state;
- outbound configuration, throughput limit, and quiet-hours policy;
- account-specific fixed autoresponder setting and text;
- account-specific AI enabled state and line prompt;
- creation/audit timestamps.

The same booking provider may have several SMS accounts. A given inbound sender number must map deterministically to exactly one enabled account. If it cannot be mapped, retain the provider event for diagnostics but do not create a customer conversation or send a reply.

### 3.2 Provider transport abstraction

Implement an internal interface such as `SmsTransportAdapter`. The module selects it from `transport_type`; no caller knows MobileMessage-specific request/response formats.

```python
class SmsTransportAdapter(Protocol):
    transport_type: str

    def verify_webhook(self, request: Request, account: SmsAccount) -> None: ...
    def parse_inbound(self, request: Request, account: SmsAccount) -> NormalizedInboundMessage: ...
    def send(self, account: SmsAccount, message: OutboundSmsCommand) -> TransportSendResult: ...
    def parse_delivery_receipt(self, request: Request, account: SmsAccount) -> DeliveryUpdate: ...
    def normalise_address(self, value: str) -> str: ...
```

The normalized inbound contract must include a provider event ID where one exists, external message ID where one exists, account/sender destination, customer source address, body, provider timestamp, media metadata, and raw payload retention reference. Do not assume every provider has all fields.

Required adapters:

- **Fake/simulator adapter:** deterministic, internal-only, no network sending. It is used by tests and the staff SMS simulator.
- **MobileMessage adapter:** port and adapt the working parsing/sending concepts from Assistant UI `backend/mobilemessage_service.py`; credentials only from the new account secret configuration.

Planned adapters must not require a database redesign: Chatwoot, another gateway, and channels with non-phone identities should fit the same contracts.

### 3.3 Customer identity, conversations, messages and events

Conversation identity is `(sms_account_id, normalised_customer_address)`, not merely a phone number. This prevents a Tori and Anonymous conversation from being confused even if the same customer contacts both lines.

Data model minimum:

| Entity | Purpose | Key relationships |
|---|---|---|
| `SmsAccount` | One sender line/transport configuration | belongs to existing `Provider` |
| `SmsConversation` | One account/customer thread | account, provider, optional existing Client |
| `SmsMessage` | One inbound/outbound/draft/system message | conversation, account, provider |
| `SmsInboundReceipt` | Idempotency record for a raw provider event | account; unique transport event key |
| `SmsDeliveryReceipt` | Delivery/failure status history | outbound message |
| `SmsConversationEvent` | Audit trail: arrival, takeover, AI job, status transitions | conversation |
| `SmsNote` | Staff-only note | conversation, author |
| `SmsOutboundJob` | Durable pending/retryable outbound delivery | message, account |
| `SmsAiJob` | Debounced/cancellable AI processing request | conversation, customer-turn fingerprint |
| `SmsKnowledgeEntry` | Curated service/business knowledge | provider scope; optional account scope |
| `SmsPromptProfile` | Shared + provider/account AI instructions | provider/account scope |
| `SmsArrivalSession` | Booking-bound arrival interaction | existing Booking, conversation |

`SmsMessage` should retain:

- immutable body and normalized body/fingerprint;
- direction: `inbound`, `outbound`, `draft`, `system`;
- author/source: `customer`, `staff`, `fixed_autoresponder`, `ai`, `system`;
- chronological source timestamp and server receipt timestamp;
- provider message ID and parent/outbound correlation ID where available;
- lifecycle state: received, queued, sending, sent, delivered, failed, cancelled, draft, discarded;
- a “customer turn” or inbound sequence reference for deduplicating replies;
- AI generation/approval metadata, but never model prompt content in customer-visible fields.

Order every conversation by `(occurred_at, received_at, id)`. Never rely on insertion order alone. The UI must show all messages in that deterministic order.

### 3.4 Inbound webhook pipeline

The webhook path is transport/account-specific, for example:

```text
POST /api/sms/webhooks/{transport_type}/{account_public_id}
POST /api/sms/webhooks/{transport_type}/{account_public_id}/delivery
```

Inbound pipeline:

1. Resolve an enabled SMS account from the opaque public account ID or verified destination number.
2. Verify the provider signature/credential according to the adapter. Reject unauthenticated traffic before processing it.
3. Parse and normalize the payload.
4. Store/lock an `SmsInboundReceipt` using a provider event/message idempotency key. A duplicate returns success without creating a duplicate message or reply.
5. Resolve/create the provider-scoped conversation and, where safely matched, link the existing Booking Client.
6. Store the inbound message and a conversation event in one transaction.
7. Update conversation last activity and unread state.
8. Decide whether a first-contact fixed autoresponder is eligible. Queue it once only; it is **not** conversational AI.
9. If AI is enabled for the account and the conversation has not been taken over, enqueue/debounce an `SmsAiJob`.
10. Return quickly. Do not call the model or SMS provider synchronously from the webhook request.

The provider must receive a correct acknowledgement even when downstream AI is disabled or a later job fails. Failures are observable in the inbox and diagnostics.

### 3.5 Outbound queue, retries and delivery receipts

All sends — staff replies, fixed autoresponders, AI replies, confirmations, reminders and arrival instructions — create an `SmsMessage` plus `SmsOutboundJob` transactionally.

Worker behaviour:

- claims jobs using a database-safe lease;
- obeys account-level rate and concurrency limits;
- uses an idempotency key that remains stable across retries;
- records the provider result and external message ID;
- retries only transient errors with bounded exponential backoff;
- marks permanent failures as failed and creates a visible staff alert/draft where appropriate;
- never sends twice because a worker crashes after an uncertain transport call;
- updates delivery receipts independently without changing the message body;
- has a dead-letter/failed queue view for staff.

Initial implementation may use the existing FastAPI Bookings outbox worker pattern if it can meet those constraints. Do not introduce Redis, Celery, Kafka, or a second deployment merely for the first version. Revisit only if database-backed job throughput is demonstrably insufficient.

### 3.6 Human inbox and staff actions

Build SMS pages inside the existing FastAPI Bookings frontend/admin navigation. Do not iframe a second frontend.

Required views:

- **Inbox:** filters by provider, SMS account/line, status, assigned staff member, unread, pending draft/review, arrival, and search.
- **Conversation:** complete chronological conversation, account badge/colour, customer and booking context, delivery state, staff-only notes, associated booking(s), and current AI state.
- **Reply composer:** visible Send button, character/segment indication, selected account shown, safe send confirmation only when appropriate.
- **Draft review:** approve, edit and send, discard, or take over. Editing an AI draft may create a proposed learning item, never silently change global knowledge.
- **Queue/diagnostics:** failed sends, pending jobs, webhook failures, duplicate receipts, and account health.
- **Settings:** SMS accounts, fixed autoresponders, AI controls, prompts, knowledge, retention, catch-up cutoff, notification sound/push settings.
- **Simulator:** internal/admin-only page that inserts a fake inbound event into the selected account’s isolated thread and visibly reports errors. It must never call a live provider.

Use the existing Assistant UI as UX reference only:

- `frontend/src/MobileInboxView.tsx` — mobile inbox and conversation interaction;
- `frontend/src/SmsTriageDashboard.tsx` — desktop triage, status and calendar context patterns;
- `frontend/src/SmsClientView.tsx` — simulator ideas;
- `frontend/src/messageTimestamp.ts` — timestamp presentation;
- `frontend/src/incomingMessageAlarm.ts` — sound/push interaction patterns.

Port components selectively into the FastAPI Bookings frontend conventions; do not transplant the full application shell or `api.ts` wholesale.

### 3.7 Fixed autoresponders

“Autoresponder” has one precise meaning: a saved, fixed preconfigured message. It is not an AI response.

Each SMS account can have its own first-contact autoresponder with:

- enabled state;
- text/template;
- optional service/provider variable placeholders from authoritative data;
- eligibility rules (first contact only, no more than once per conversation or configurable cooldown);
- a delivery record and visible message source `fixed_autoresponder`.

The outcome must be deterministic: with the fixed responder off, no fixed responder sends. With conversational AI off, a fixed responder may still send if the account setting is on. These controls must be visibly separate in settings and diagnostics.

### 3.8 Conversational AI

AI is a controlled assistant, not a direct database client and not an autonomous source of booking facts.

#### Prompt hierarchy

Assemble each request from:

1. immutable platform safety rules;
2. shared booking-conversation policy;
3. provider-level prompt/profile: business identity, services, tone, location-specific information;
4. account/line-level prompt: sender identity, line-specific link or wording;
5. current chronological conversation for the same `sms_account_id` only;
6. relevant provider-scoped knowledge entries;
7. live tool results, where needed.

Do not mix one account/provider’s conversation, knowledge, links, images, credentials, or prompt text into another. A generic knowledge record is permitted only when it is explicitly marked generic and safe for all providers.

#### Required AI tools

Tools are application service calls, not unrestricted SQL or HTTP access:

- `get_provider_profile(provider_id)`
- `list_provider_services(provider_id)`
- `get_service_details(provider_id, service_id)`
- `find_live_availability(provider_id, service_id, requested_window, duration)`
- `create_booking(provider_id, client_data, service_id, start, idempotency_key)`
- `amend_booking(booking_id, requested_change, idempotency_key)`
- `cancel_booking(booking_id, reason, idempotency_key)`
- `get_booking_status(booking_id)`
- `create_information_request(conversation_id, question, reason)`

All booking tools call existing FastAPI Bookings services/routers or a thin internal service facade. They revalidate provider/service eligibility, booking rules, minimum notice, buffer, holds, conflicts and client details at execution time.

#### AI rules

- Read the relevant full conversation before responding; do not react to an isolated final message.
- Consolidate bursts: wait a short configurable debounce window, then answer the latest unresolved customer turn once.
- Cancel stale AI jobs when a newer inbound message, a staff reply, takeover, or conversation resolution supersedes them.
- A response fingerprint plus customer-turn reference prevents identical AI replies from being sent repeatedly.
- No internal instruction/fallback/policy text can be sent. Enforce an outbound sanitizer and hard blocklist, then create a staff-visible failure instead.
- AI must not invent prices, services, availability, booking confirmations, locations, links, or policies.
- Availability only comes from a successful live booking lookup. Stored learning, past messages, and RAG must never be used for availability options.
- Bookings require live validation immediately before creation. Do not offer/confirm a time that fails the live call.
- Existing-booking corrections and amendments receive normal agent handling, not a customer-visible “stay focused on bookings” or equivalent internal fallback.
- If required information is unavailable, remain silent or create an Information Request according to account policy; never bluff a customer answer.
- Customer replies should be informal and concise. Once service, time and first name are clear and live creation succeeds, do not ask for redundant summary confirmation. The booking system sends its standard confirmation.

#### Modes

Per SMS account:

- **Off:** inbox/manual handling only.
- **Draft/review:** AI creates a draft only; no outbound send without staff approval.
- **Autopilot:** eligible replies can queue for outbound send under all safeguards.
- **Paused/takeover:** no AI generation or send for the conversation; staff controls it.

Changing a mode is audited. Global defaults can exist, but an account-level disable always wins.

### 3.9 Knowledge, learning and retrieval

Knowledge is not a bag of past answers. It must be structured, scoped, reviewed, and safe to retrieve.

`SmsKnowledgeEntry` minimum fields:

- provider scope: generic / exact `provider_id`;
- optional account scope;
- category: service, policy, location, FAQ, tone example, internal-only, availability-prohibited;
- text/content and source/reference;
- status: proposed, approved, rejected, archived;
- provenance: manual, information request response, edited draft proposal, imported;
- created/approved/reviewed timestamps and author;
- embedding/retrieval metadata if semantic search is later enabled.

Do not store current or future availability, offered slots, or “next available” answers as reusable knowledge. Categorize and reject those records on ingestion.

Phase one retrieval may use deterministic keyword/category filtering plus approved records. Semantic embeddings/ranking are a later enhancement, only after the scope and audit model works. If added, embed and search only approved provider-scoped entries, rank results, inject a small bounded number of results, and log which entries were used. A cheap embedding model or local model is an implementation choice, not a reason to weaken isolation or live-calendar rules.

Edited AI drafts may become **proposed** learning entries with before/after text and context, ready for staff review. They never silently retrain or alter a prompt.

### 3.10 Booking behaviour

Use the FastAPI Bookings domain as-is wherever possible. The SMS module must honour existing booking configuration and add no parallel scheduler.

Required behaviour:

- services, provider eligibility and location come from the existing booking domain;
- availability is live and provider-specific;
- minimum notice is at least 30 minutes unless the authoritative provider policy says more;
- apply the existing 15-minute booking buffer policy where configured;
- do not use internal slot language with customers unless needed; slots are an implementation detail;
- bookings, amendments and cancellations are idempotent;
- normal booking confirmations, address and arrival link delivery are generated by the authoritative confirmation workflow exactly once;
- the AI does not send a competing “confirmation link” or duplicate confirmation SMS;
- a booking API/domain failure creates a visible error and does not fall back to a local SMS-side booking.

### 3.11 Catch-up and backfill

Catch-up is an explicit, account-scoped operation. It must support a configurable age cutoff in days and never sweep the full historic inbox by accident.

For every candidate:

- skip threads with a staff reply/takeover or already resolved final customer turn;
- skip messages older than the account’s configured cutoff;
- enforce the same debounce, idempotency, booking and AI-mode rules as live inbound messages;
- send real messages only in autopilot mode; draft/review mode creates drafts only;
- show a dry-run count and an execution report;
- make cancellation possible and safe.

## 4. Arrival workflow and notifications

Port the customer-arrival concept, not the old data model.

1. The authoritative booking confirmation template can include an arrival short link.
2. Opening the link alone does not consume it. The client can reopen it before arrival.
3. Pressing **I’ve arrived** activates one booking-bound arrival session. Repeat presses are idempotent.
4. The linked SMS conversation gets a durable `customer_arrived` event/message badge.
5. Staff receive a push/audible notification. It repeats at a configured interval (for example 60 seconds) until staff acknowledge it by opening the linked conversation or arrival session.
6. The conversation can show a prominent “Client arrived” action that sends the provider/account’s saved arrival-instruction template.
7. Optional two-way arrival chat is linked to the same conversation, rather than becoming an isolated source of truth.
8. Short links must be opaque, high entropy, revocable, and booking-bound. Do not attempt brittle browser-side “self destruction.”

Useful source references:

- Assistant UI: `ArrivalClientView.tsx`, `ArrivalProviderView.tsx`, `incomingMessageAlarm.ts`, `PwaControls.tsx`;
- Assistant backend: arrival session/push functions in `backend/main.py` and its arrival/push tests.

## 5. Source reuse map

### Reuse or adapt after review

| Assistant UI source | Value | Required treatment |
|---|---|---|
| `backend/mobilemessage_service.py` | First transport adapter concepts | Extract into `app/modules/sms/transports/mobilemessage.py`; replace file configuration with account secret lookup; add typed normalized contracts and tests. |
| `backend/test_mobilemessage_service.py` | Adapter test cases | Port/adapt using fake HTTP and FastAPI Bookings models. |
| inbound webhook reliability tests | Idempotency/race test ideas | Rebuild against new receipt/message/job schema. |
| `messageTimestamp.ts` | Small safe UI utility | Port if frontend conventions permit. |
| `MobileInboxView.tsx` | Mobile inbox UX | Reimplement components against new API; retain deterministic order and explicit Send action. |
| `SmsTriageDashboard.tsx` | Desktop triage UX | Reimplement selectively; do not retain its polling assumptions or booking data calls. |
| `SmsClientView.tsx` and simulator tests | Internal simulator behaviours | Rebuild as a fake transport/admin endpoint. |
| `ArrivalClientView.tsx`, `ArrivalProviderView.tsx`, `incomingMessageAlarm.ts`, `PwaControls.tsx` | Arrival and PWA interaction patterns | Port only after new booking-bound arrival API exists. |
| `test_manual_reply_idempotency.py` | Manual send deduplication behaviour | Rebuild around the durable outbox. |
| `test_conversation_safety.py` and booking boundary tests | Safety regression scenarios | Preserve as acceptance behaviour, not literal copied tests. |

### Do not copy

| Source/area | Reason |
|---|---|
| `assistant-ui/backend/main.py` as a unit | It is a large monolith with independent SQLite models, file-backed settings, legacy booking code, operations console, and unrelated features. Extracting it wholesale recreates the current complexity. |
| `assistant-ui/backend/booking_tools.py` as booking authority | FastAPI Bookings already owns this domain. Replace tool internals with internal booking-service calls. |
| Assistant UI databases, `.env`, service accounts, credentials, data folders, training files, caches, or Git metadata | They contain runtime state/secrets or create a second source of truth. |
| Assistant UI booking/calendar/service settings files | They duplicate provider/service/scheduling configuration. |
| Existing AI fallback wording/legacy prompt assembly | It has produced customer-visible internal-policy failures and must not be propagated. |
| `bookings_ai_agent` booking model, calendar writes, or agent core | It maintains a duplicate local booking system and direct Google Calendar behaviour. It is a donor only. |

### `bookings_ai_agent` donor candidates

Read-only donor work, never a foundation:

- approval-desk UI and workflow ideas;
- onboarding interview that produces structured provider/prompt settings;
- persona/bootcamp simulator ideas;
- virtual-phone UX;
- optional Chatwoot adapter concepts.

Before porting any donor component, inspect it for untested assumptions, direct outbound side effects, hard-coded endpoints, and local booking writes.

## 6. Recommended project layout

Follow the existing FastAPI Bookings conventions, keeping the module small and testable:

```text
app/
  api/routers/
    sms_accounts.py
    sms_webhooks.py
    sms_conversations.py
    sms_settings.py
    sms_arrivals.py
  models/
    sms_account.py
    sms_conversation.py
    sms_message.py
    sms_receipt.py
    sms_outbox.py
    sms_knowledge.py
    sms_arrival.py
  schemas/
    sms_account.py
    sms_conversation.py
    sms_message.py
    sms_settings.py
  services/
    sms/
      transports/base.py
      transports/fake.py
      transports/mobilemessage.py
      inbound_service.py
      conversation_service.py
      outbound_service.py
      outbox_worker.py
      rate_limit_service.py
      ai_orchestrator.py
      prompt_service.py
      knowledge_service.py
      arrival_service.py
      simulator_service.py
  tests/
    test_sms_*.py

frontend/src/
  pages/admin/sms/
    inbox.tsx
    conversation.tsx
    accounts.tsx
    settings.tsx
    simulator.tsx
    diagnostics.tsx
```

Names may follow the repository’s actual convention, but preserve the boundaries: routers validate/authenticate, services perform domain work, transports isolate vendor APIs, and workers process durable jobs.

## 7. Delivery sequence

Do not attempt every feature in one branch or let multiple agents edit the same core module simultaneously.

### Phase A — discovery and contract (read-only first)

1. Inventory existing FastAPI Bookings Provider, Service, Client, Booking, Notification and Outbox models/services/routes.
2. Identify existing authenticated admin conventions and frontend routing conventions.
3. Identify all existing SMS-like code (`clicksend.py`, `chatwoot.py`, notifications/outbox) and decide whether to reuse or leave isolated.
4. Produce an API/data mapping and confirm no existing model is silently repurposed.
5. Create the database migration plan and tests before enabling any live transport.

### Phase B — transport-neutral foundation

1. Add migrations/models for SMS accounts, conversations, messages, receipts, events and outbound jobs.
2. Add fake transport adapter and internal simulator endpoint.
3. Implement inbound idempotency, ordering, conversation resolution and manual inbox APIs.
4. Implement durable outbound job processing with fake adapter.
5. Build account and inbox administration UI.
6. Verify two accounts receiving the same customer number remain fully separate.

### Phase C — MobileMessage and human operations

1. Implement MobileMessage adapter using test fixtures/mocks.
2. Add validated webhook endpoint and receipt handling.
3. Add manual send, retry, error display, staff notes, takeover and audit history.
4. Add fixed first-contact autoresponder, separately controlled per account.
5. Only after full fake/provider tests pass, configure a non-production/test line if available. Do not send a live test without approval.

### Phase D — booking integration

1. Add the small internal booking facade used by SMS/AI workflows.
2. Add live availability, create, amend, cancel and status calls with idempotency.
3. Add confirmation handoff so FastAPI Bookings sends its own standard confirmation once.
4. Add provider mapping screens and acceptance tests for buffer, notice and account/provider isolation.

### Phase E — AI and knowledge

1. Add draft/review mode first; no autopilot default.
2. Add scoped prompt/knowledge administration, information requests and approval workflow.
3. Add burst debounce, stale-job cancellation, reply fingerprinting and outbound safety filter.
4. Add autopilot only after the regression suite proves safe behaviour.
5. Add semantic retrieval only after curated scoped knowledge works deterministically.

### Phase F — arrival/PWA and optional enhancements

1. Add booking-bound arrival links and one-time activation semantics.
2. Add inbox arrival badge, acknowledgement and saved instruction action.
3. Add push/audible notifications and repeating-until-acknowledged rules.
4. Consider optional Chatwoot/other providers only through adapters.

## 8. Acceptance tests

The implementation is not accepted until automated tests cover at least:

### Provider/account isolation

- Same customer address on two accounts creates two conversations.
- No thread, prompt, knowledge, link, attachment, outbound sender, or reply crosses an account/provider boundary.
- Disabled account rejects/records inbound appropriately and sends nothing.

### Inbound/outbound safety

- Duplicate inbound provider event creates one message and at most one eligible reply workflow.
- Out-of-order provider timestamps render deterministically.
- A burst of inbound messages creates one AI job for the final unsuperseded customer turn.
- Staff reply/takeover cancels any pending AI job.
- A worker retry cannot send duplicate outbound text.
- Transport failure is visible and does not mark a message delivered.
- Simulator cannot send a live SMS or accept unauthenticated external traffic.

### AI safety

- AI off means no conversational reply is generated/sent.
- Fixed autoresponder remains independently controlled.
- Draft/review never sends before approval.
- Repeated identical AI fallback reply for a customer turn is blocked.
- Exact prohibited internal wording and equivalent internal prompt/policy text cannot be queued or sent outbound.
- Existing booking correction/amendment requests get normal handling.
- AI cannot offer availability without a successful live booking-domain tool result.
- AI cannot create a booking without final authoritative validation.

### Booking-domain integration

- Provider/account maps to correct provider, service list, schedule and confirmation configuration.
- minimum notice and booking buffer are enforced by the existing domain at creation/amendment.
- creation/amendment/cancellation are idempotent.
- standard booking confirmation is sent once and no competing AI confirmation is sent.
- booking-domain outage produces a visible failure, never a local fallback booking.

### Arrival

- Arrival link may be opened before arrival without consuming it.
- Activation is idempotent and bound to one booking.
- Staff alert repeats until the linked conversation/arrival session is acknowledged.
- The saved arrival instruction is sent from the correct account.

## 9. Operational constraints and observability

- Store credentials in the existing secret/configuration mechanism; encrypt at rest if credentials must be database-held. Never display them in APIs, logs or UI.
- Redact message body and phone numbers from general server logs; give authorized staff the inbox for content inspection.
- Add metrics/dashboard counts: inbound receipts, duplicates, jobs queued/sent/failed/cancelled, reply latency, AI failures, delivery failures, account health, unacknowledged arrivals.
- Log structured audit events with IDs, never raw secrets.
- Add retention settings for raw provider payloads, conversations, messages, knowledge proposals and arrivals.
- The active inbox may poll modestly at first; hidden tabs should not continue rapid requests. Later use server-sent events or WebSockets only if measured load requires it.
- Do not horizontally scale a SQLite deployment that uses a single mounted volume. If scaling becomes necessary, migrate the booking database deliberately to a multi-writer database first.

## 10. Explicit non-goals for the first release

- no second booking database;
- no direct Google Calendar booking writes from SMS/AI;
- no uncontrolled autonomous coding agent inside the customer-reply path;
- no bulk SMS campaign system;
- no import of historical Assistant UI conversations without a separate data migration and privacy review;
- no automatic semantic “training” from every conversation;
- no arbitrary external web search by the customer-reply AI;
- no production live SMS testing without authorization;
- no copying of `.git`, `.env`, databases, virtual environments, build artifacts, node modules or credentials from Assistant UI.

## 11. Architecture decision record

### ADR: Modular SMS inside FastAPI Bookings

**Status:** Accepted for implementation.

**Context:** FastAPI Bookings already owns the provider, service, schedule and booking graph. Assistant UI contains useful SMS/channel and UX work, but it also contains a separate database and legacy booking/AI logic. Maintaining both produces drift and booking errors.

**Decision:** Implement an internal, provider-neutral SMS module in FastAPI Bookings using the same authoritative database, with separate SMS tables and services. Reuse selected concepts/code only after review. Start with a database-backed worker and fake transport; add MobileMessage as the first adapter.

**Trade-off:** This requires deliberate migration work instead of copying a ready-looking app. It avoids duplicate booking authority, unreliable synchronization, cross-account leakage, and perpetual maintenance of copied projects.

**Revisit trigger:** Reconsider extracting the SMS module into a separate service only if there is measured operational need for independent scaling/deployment and a reliable shared database/event boundary has been established.

## 12. Instructions to Antigravity

1. Read this brief and the existing FastAPI Bookings source before changing code.
2. Treat the FastAPI Bookings worktree as user-owned and currently dirty. Never reset, clean, overwrite unrelated files, move databases, or stage broadly.
3. Start with Phase A and report the existing model/API mapping. Do not begin by copying `integrations/assistant-ui` or `bookings_ai_agent`.
4. Work in small reviewed branches/commits. One owner edits the SMS core at a time.
5. Use fake adapters/mocks in tests. Do not send real SMS or change production configuration without an explicit request.
6. For every phase, report changed files, migrations, tests run, test results, remaining gaps, and any test data created.
7. Stop and ask before a decision that changes customer-visible sending, data retention, credentials, provider configuration, or production deployment.
