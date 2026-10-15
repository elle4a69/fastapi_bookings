# Services Module

## Purpose & Scope
This module contains the core business logic and external service integrations for the FastAPI Bookings engine. It serves as the middleware connecting our application's API endpoints to external SaaS providers, managing operations like tenant synchronization, webhook provisioning, and domain-specific processing.

## Architecture & Key Files
- `agent_runner.py`: Implements the end-to-end background execution of an AI agent's turn. Orchestrates database retrieval, dialogue graph progression, and dispatching responses back to Chatwoot.
- `chatwoot_provisioner.py`: Manages the Multi-Tenant Chatwoot ⇄ FastAPI Booking Engine Synchronization (Work Package 2). Connects to Chatwoot's Platform and App APIs.
- `contact_sync.py`: Implements the Contact Projection Synchronization Worker (Work Package 3). Synchronizes FastAPI client records to Chatwoot contacts with `client_id`, `street_address`, `suburb`, and `postcode` embedded in `custom_attributes`.
- `media_service.py`: Implements durable tenant-scoped media file persistence, MIME validation, path traversal prevention, public website eligibility toggle, soft deletion with binary purging, and safe assistant media context projection.
- `website_initial_draft.py`: Assembles factual, deterministic initial public website starter drafts from authoritative tenant records (services, schedules, providers, and approved durable media assets) with zero hallucinated copy or synthetic reviews.
- The configuration for these services leverages `app/core/config.py` for API tokens, base URLs, and other necessary integrations parameters.

## Core Workflows & Contracts

### Tenant Provisioning Flow
1. Upon creation of a new business/tenant, `provision_chatwoot_tenant` is called with the `business_name`.
2. The provisioner connects to the Chatwoot Platform API using `CHATWOOT_PLATFORM_ACCESS_TOKEN` (or `CHATWOOT_PLATFORM_API_TOKEN`) and creates a new Chatwoot Account/Tenant.
3. The provisioner creates a webhook for the newly provisioned Chatwoot Account using the Chatwoot API. The webhook uses the `AGENT_WEBHOOK_URL` endpoint to notify the FastAPI booking engine of events (specifically `message_created` and `conversation_status_changed`).
4. A `TenantProvisionResult` contract containing `chatwoot_account_id` and `webhook_id` is returned.

### Agent Turn Execution Flow (Work Package 4)
1. Chatwoot webhook receives an inbound customer message and dispatches the `run_agent_turn` background task.
2. `run_agent_turn` queries the database for `SmsChatwootBinding`, `Tenant`, and `Provider` records via `async_session_scope`.
3. Validates tenant and provider existence, enforcing multi-tenant isolation invariants.
4. Initializes `AgentState` and executes deterministic state machine progression through `process_dialogue_turn`.
5. Enforces provider `max_char_limit` truncation constraint.
6. Dispatches the outbound bot reply to Chatwoot conversation REST API via `send_bot_message`.

### Media Asset Lifecycle & Assistant Projection Flow
1. Media upload via `MediaService.save_upload`: enforces MIME type allowlist, checks forbidden script/executable extensions, streams chunks up to 25MB, writes into isolated `tenant_{tenant_id}/` storage, and creates DB record with `is_deleted=False`.
2. Public website eligibility toggle via `MediaService.update_eligibility`: sets `is_public_website_eligible` flag.
3. Assistant media context projection via `MediaService.get_assistant_media_context`: strictly filters for `is_public_website_eligible=True` and excludes internal/clinical notes to prevent private details from being exposed to assistant prompts or tools.
4. Soft deletion via `MediaService.delete_media`: flags `is_deleted=True` and removes the physical binary file from disk.

### Initial Website Draft Flow
1. Generates deterministic website draft from existing tenant data: active services, opening hours, provider details, and durable public-eligible Media records.
2. Idempotent draft creation (`ensure_initial_website_draft`) ensures private starter creation without overwriting existing live or customized websites.
3. Strict filtering prevents confidential clinical or internal operational notes from being included in public copy or gallery metadata.

## Setup, Configuration & Dependencies
Ensure the following configuration variables are set in your environment or `app/core/config.py`:
- `CHATWOOT_BASE_URL` (default: `http://localhost:4000`)
- `CHATWOOT_PLATFORM_ACCESS_TOKEN` (or `CHATWOOT_PLATFORM_API_TOKEN`)
- `CHATWOOT_WEBHOOK_SECRET`
- `AGENT_WEBHOOK_URL` (default: `http://localhost:8000/api/v1/chatwoot/webhook`)
- `MEDIA_UPLOAD_DIR` (default: `uploads/media`)

These require the `httpx` module for making API calls.

## Data Safety & Isolation
- Each provisioned tenant in Chatwoot runs within its own account ID (`chatwoot_account_id`).
- When setting up webhooks or handling messages, operations strictly enforce tenant boundaries by utilizing the specific `chatwoot_account_id` provided during the provisioning flow.
- In `agent_runner.py`, queries strictly constrain lookups to the bound `tenant_id` and `provider_id`.
- Access tokens are never logged or leaked. The services module respects the strictest data isolation principles and handles configuration secrets securely through `app/core/config.py`.
- In `media_service.py`, filesystem directories are partitioned by tenant (`uploads/media/tenant_{tenant_id}`) with path traversal prevention asserting that resolved destination paths remain within the upload root. Confidential clinical and booking notes are completely stripped from assistant context projections.

## Known Issues, Edge Cases & Outstanding Work
- Network timeouts or platform API degradations will raise `ChatwootProvisionError`, meaning tenant creation should be handled gracefully by calling services (potentially via a retry queue or dead-letter mechanism).
- Future additions may include automatic inbox and user agent creation immediately following tenant provisioning.
- If `CHATWOOT_PLATFORM_ACCESS_TOKEN` is misconfigured, the provisioner will fail immediately before executing requests.

## Verification & Testing Commands
```bash
python -m pytest tests/test_chatwoot_provisioner.py -v
python -m pytest tests/test_contact_sync.py -v
python -m pytest tests/test_agent_runner.py -v
python -m pytest tests/test_media_backend.py -v
python -m pytest tests/test_website_initial_draft_service.py -v
```
