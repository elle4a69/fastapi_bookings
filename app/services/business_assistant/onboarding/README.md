# Voice-First Onboarding & In-App Assistance Subsystem

## Purpose & Scope

The `app/services/business_assistant/onboarding` package delivers the backend business logic, conversational intent normalization, setup planning state machine, cryptographic delegation guards, and gateway adapters for the voice-first onboarding assistant in FastAPI Bookings.

The system guides newly registered and existing business owners through an end-to-end conversational setup of their business without requiring tedious manual form filling. The assistant operates the live application visibly, navigating administrative screens, staging candidate values into React form adapters, and highlighting controls while the user watches.

Key architectural tenets:
- **Visible Form Operation Over Background Persistence**: Agent commands stage values into UI adapters without prematurely saving to the database, enforcing the foundational invariant: `staged_fields != saved`.
- **Absolute Prohibition of Mocks**: All routers, services, form adapters, and tools interact with real database models, live LiveKit agent tools, and authentic frontend RPC contracts.
- **Strict Control Epochs & Monotonicity**: Any manual user interaction (typing, clicking, modal dismissal) increments the plan's `control_epoch`, instantly invalidating and rejecting late in-flight agent writes.
- **Single-Tab Active Executor Leasing**: In multi-tab sessions, only the leased active-executor browser tab executes mutating form actions, preventing race conditions and duplicated submissions.
- **Cryptographic Delegation & Consequential Save Guards**: All persistent database commits for consequential domains (Business Identity, Location, Website Publication) require single-use HMAC-SHA256 authorization nonces with a 5-minute TTL.

---

## Architecture & Key Files

- `schemas.py`: Pydantic models and schemas defining typed field payloads (`FieldPayload`), auditable command envelopes (`OnboardingCommandEnvelope`), receipt state machines (`ReceiptState`, `OnboardingExecutionReceipt`), and custom error classes.
- `normalizer.py`: `IntentNormalizer` translating spoken Australian English into exact application values. Preserves exact names, numbers, units, and currencies ($120 AUD, 90 mins, 15 km), enforces Australian spelling (`AU_SPELLING_MAP`), detects material ambiguities without silent guessing, and manages conversational corrections.
- `plan_service.py`: `OnboardingPlanService` managing the 8-domain onboarding plan lifecycle (`OnboardingPlan`, `OnboardingStep`, `OnboardingAuditLog`), step dependencies, staged vs saved transitions, control epoch advancement, and active executor lease enforcement.
- `save_guard.py`: `DelegationSaveGuard` enforcing session-level delegation modes (`autonomous`, `delegated`, `supervised`, `manual_only`), per-domain authorization policies, and cryptographic HMAC-SHA256 nonce generation/consumption.
- `router.py`: FastAPI REST API endpoints exposing onboarding plan initialization and retrieval, field staging, authoritative step saving, step skipping, manual takeover signaling, active executor leasing, and authorization nonce issuance.
- `tools.py`: Scoped onboarding agent tools registered with LiveKit (`read_context`, `plan_step`, `prepare_fields`, `navigate_show`, `fill_form`, `validate_form`, `save_form`, `read_status`, `pause_takeover`) conforming to the Section 13 tool catalogue.
- `gateway.py`: `OnboardingGateway` managing tool dispatch, session context binding, monotonic control epoch verification, and RPC receipt translation.
- `interview.py`: `InlineInterviewFlow` driving natural 8-domain conversational dialogues, smooth topic transitions (`DOMAIN_TRANSITIONS`), multi-modal input resolution (voice, click, text), and interruption handling with polite Australian resumption.
- `website_generator.py`: `OnboardingWebsiteGenerator` creating draft single-page websites from gathered onboarding facts, respecting public vs clinical media separation and owner publication approval gates.

---

## Setup, Configuration & Dependencies

### Python Dependencies
The onboarding subsystem operates within the project's standard virtual environment (`.venv`) and requires:
- `fastapi` (HTTP routing and dependency injection)
- `sqlalchemy` (authoritative ORM persistence and transaction management)
- `pydantic` (data validation and typed command envelopes)
- `livekit-agents` and `livekit-api` (agent tool definitions and participant RPC dispatch)

### Database Models & Migrations
The subsystem is backed by Alembic migration `z1a2b3c4d5e6_add_onboarding_workflow_tables.py` and SQLAlchemy models defined in `app/models/onboarding.py`:
- `onboarding_plans`: Persistent tenant onboarding setup plan, tracking status, current step, control epoch, active lease token, and 8-domain state JSON.
- `onboarding_steps`: Granular setup step records storing domain number (1-8), target route, form ID, required facts, answered facts, staged fields, and persisted entity identifiers.
- `onboarding_audit_logs`: Immutable audit trail recording every state change, stage action, takeover event, and save operation with actor attribution.

### Environment & Secrets
- `SECRET_KEY`: Used by `DelegationSaveGuard` for HMAC-SHA256 signing of single-use authorization nonces.

---

## Core Workflows & Contracts

### 1. Conversational Interview & Intent Normalization
1. The assistant queries unanswered facts for the current domain via `plan_step`.
2. The user answers via voice (e.g., "We do mobile dog grooming, $120 AUD for a 90-minute full groom").
3. `IntentNormalizer` normalizes the spoken intent into structured field values (`duration=90`, `price=120`, `qualifier='AUD'`), enforcing Australian spelling and units.
4. If the user is ambiguous (e.g., "About an hour, sometimes longer"), `IntentNormalizer` withholds candidate values and issues a targeted clarification question without guessing.
5. If the user corrects themselves ("Actually, make that ninety, not sixty"), the prior candidate is invalidated and replaced.

### 2. Visible Field Staging & Autosave Protection
1. `prepare_fields` or `fill_fields` invokes `OnboardingPlanService.stage_step_fields`.
2. Fields are staged into `step.staged_fields` and dispatched via RPC `fill_fields` with `staging_guard: true, prevent_autosave: true`.
3. The frontend `BusinessSettingsAdapter` or `CatalogServicesAdapter` stages values into component state without firing the 600ms debounce autosave or blur handlers.
4. A truthful `fields_staged` receipt is returned with `persisted_entity_id=None` and `saved=False`.

### 3. Manual Takeover & Epoch Invalidation
1. If the user clicks "I'll do this part" or types into a staged input, the frontend fires a manual takeover event.
2. The backend increments `plan.control_epoch` (e.g. from 1 to 2) and records the event in `OnboardingAuditLog`.
3. Any late or in-flight agent write carrying an older epoch is immediately rejected with `StaleControlEpochError` (HTTP 409 `STALE_CONTROL_EPOCH`).

### 4. Authoritative Save with Cryptographic Nonce
1. For consequential domains (Domain 1 Identity, Domain 2 Locations, Domain 7 Website Publication), the agent requests authorization via `request_save_authorization`.
2. A single-use HMAC-SHA256 nonce is issued with a 300-second (5-minute) TTL, bound to `tenant_id`, `plan_id`, and `step_id`.
3. The owner reviews staged values and confirms save.
4. The backend validates and consumes the nonce, executes the database transaction, advances the plan to the next domain, and returns a `saved` receipt with the committed entity ID.
5. Any replay of the consumed nonce is strictly rejected with `NonceAlreadyUsedError`.

---

## Data Safety & Isolation

- **Tenant Isolation**: Every database query, plan retrieval, step staging, and save operation is scoped strictly by `tenant_id` from the authenticated session. Cross-tenant access attempts return HTTP 404 `PLAN_NOT_FOUND` without leaking data.
- **Cryptographic Authorization Nonces**: Consequential mutations cannot be executed autonomously without a signed HMAC nonce, ensuring automated agents cannot overwrite core business identity or publish websites without owner approval.
- **Zero Hallucinated Credentials**: Normalizer synthesis and prompt pipelines strictly prohibit fabricated API keys, passwords, or credentials.
- **Telemetry & Audit Privacy**: Telemetry logs and `OnboardingAuditLog` records store structured action names and metadata without sensitive authentication tokens, passwords, raw speech transcripts, or PII.

---

## Known Issues, Edge Cases & Outstanding Work

- **Multi-Tab Lease Takeover**: When a user switches active browser tabs, the new tab must explicitly claim or refresh the active executor lease via `/lease`. A competing tab attempting concurrent execution receives HTTP 409 `LEASE_CONFLICT`.
- **Fuzzy Duration Extraction**: Colloquial expressions such as "an hour and a half" are handled via explicit numerical conversion ("90 mins" or "1.5 hours") or flagged as ambiguous to solicit an exact duration from the user.
- **Mobile Network Reconnection**: Transient WebSocket disconnections do not lose staged fields; client and backend reconcile state via `GET /plan/{id}` upon reconnection.

---

## Verification & Testing Commands

Execute all focused onboarding test suites using the project Python environment:

```powershell
# Run the 4 Stage 5 QA verification suites (Text/Intent, Form Automation, Takeover/Concurrency, Security/Privacy)
.\.venv\Scripts\python.exe -m pytest tests/test_onboarding_text_and_intent_qa.py `
  tests/test_onboarding_form_automation_qa.py `
  tests/test_onboarding_takeover_concurrency_qa.py `
  tests/test_onboarding_security_privacy_qa.py -v

# Run the complete onboarding backend and gateway test suite
.\.venv\Scripts\python.exe -m pytest tests/test_onboarding_backend.py `
  tests/test_onboarding_interview_flow.py `
  tests/test_onboarding_router.py `
  tests/test_onboarding_schemas.py `
  tests/test_onboarding_tools_and_gateway.py `
  tests/test_onboarding_text_and_intent_qa.py `
  tests/test_onboarding_form_automation_qa.py `
  tests/test_onboarding_takeover_concurrency_qa.py `
  tests/test_onboarding_security_privacy_qa.py -v

# Verify Living Documentation compliance (Rule 10)
.\.venv\Scripts\python.exe scripts/verify_living_docs.py
```
