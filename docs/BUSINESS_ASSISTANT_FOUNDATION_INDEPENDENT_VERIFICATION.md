# Business Assistant Foundation — Independent Verification

**Reviewed:** 2 October 2026 (Australia/Sydney)  
**Scope:** Foundation persistence, text-only route, support-ticket route, migration graph, and frontend claims  
**Method:** Read-only source review and focused local checks. No application code, configuration, database, worker, or external service was modified.

## Result

The implemented foundation correctly enforces owner and tenant scope on the reviewed conversation and ticket routes, persists its records separately from customer messaging, fails honestly when the text model is unavailable, and contains no worker connector or dispatch path. The migration graph has one head.

Three findings must be resolved before this foundation is treated as concurrency-complete or extended to ticket closure/reopening workflows.

## Findings

### BA-IV-01 — Conversation-create idempotency can return a 500 during a concurrent duplicate request

**Severity:** High  
**Evidence:** `BusinessAssistantConversation` has a scoped unique constraint on `(tenant_id, user_id, creation_request_key)` in `app/models/business_assistant.py`. `BusinessAssistantRepository.create_conversation` first queries for an existing key and then flushes a new row in `app/services/business_assistant/repository.py`. The route commits that result in `app/api/routers/business_assistant.py` without an `IntegrityError` recovery path.

Two concurrent requests with the same valid key can both pass the initial read. One then loses the unique-constraint race at flush or commit and is surfaced as an unhandled server error rather than the original conversation. Existing idempotency coverage is sequential only.

**Required remediation:** Catch the scoped uniqueness conflict at the service or route transaction boundary, roll back, re-read through the same tenant/user scope, and return the original conversation. Add an actual concurrent API test proving one durable conversation and two successful idempotent responses.

### BA-IV-02 — Request keys are not bound to an exact payload

**Severity:** Medium  
**Evidence:** Conversation, text-turn, and ticket records store request keys but no request-payload hash. The text service returns the existing message/reply when a request key already exists (`app/services/business_assistant/service.py`), and ticket creation returns the existing ticket for an existing request key before comparing the new title, description, category, or severity.

A retry with a reused key and changed content silently receives the earlier resource. That is not a safe idempotency contract for user-visible text or tickets, particularly once ticket approval/dispatch exists.

**Required remediation:** Store a canonical payload hash with each idempotent resource. A repeated key with the same hash returns the original result; a changed hash returns a stable conflict without running a model call or creating/altering a ticket. Add negative regression coverage for conversations, text turns, and tickets.

### BA-IV-03 — Ticket deduplication uniqueness is permanent while the repository calls it active-only

**Severity:** Medium, future workflow blocker  
**Evidence:** `SupportTicket` has an unconditional unique constraint on `(tenant_id, user_id, deduplication_key)` in `app/models/business_assistant.py`. `get_active_ticket_by_deduplication_key` in `app/services/business_assistant/repository.py` only considers selected active statuses.

After a future ticket becomes resolved, cancelled, or another non-active status, the repository will find no active duplicate but the database will still reject an identical new ticket. The current interface has no status-changing route, so this is not an immediate duplicate-dispatch path; it is nevertheless incompatible with the stated active-only behaviour.

**Required remediation:** Decide and document the intended rule. Either retain permanent deduplication and remove the active-only claim, or implement a database constraint/index strategy that permits a later ticket after terminal closure while remaining race-safe. Add closure/reopen and concurrent-create tests before adding any status-changing workflow.

## Verified controls

- Conversation and ticket repositories derive tenant/user scope from the authenticated route dependencies and use that scope in list, get, message, and event queries.
- Tested cross-tenant and same-tenant different-user reads return not found or empty scoped lists.
- Text submission persists the user message before a missing-model response and returns 503 without manufacturing an assistant reply.
- The text runtime has one provider request, bounded history/output/timeout configuration, no tool calls, and no hidden response fallback.
- Ticket creation sanitises title and description before persistence and rejects the covered secret, email, phone, and direct customer-ID patterns.
- Ticket creation records `awaiting_engineering` with a public-safe created event only. No reviewed route, service, or frontend component dispatches a coding job.
- The frontend explicitly states that tickets do not trigger work automatically; this is accurate for the reviewed implementation.
- The frontend has no fabricated response, timer, or browser-side worker status for the Business Assistant text/ticket feature.
- Migration revision `g7h9j1k3m5n7` is the sole Alembic head in the local graph. This verification did not run migration upgrade/downgrade against a database because the task prohibited application/environment changes.

## Checks run

```text
.venv\Scripts\python.exe -m pytest tests\test_business_assistant_foundation.py tests\test_business_assistant_api.py tests\test_business_assistant_tickets_api.py -q
14 passed in 7.01s

.venv\Scripts\python.exe -m alembic heads
g7h9j1k3m5n7 (outbox_safety_remediation, webhook_safety_remediation) (head)

frontend\npm run lint
completed with existing unrelated warnings and no errors

frontend\npm run build
passed
```

## Release assessment

The foundation is suitable for continued development only with BA-IV-01 through BA-IV-03 tracked as blocking remediation for the relevant future workflows. It is not suitable for coding-worker dispatch, ticket auto-dispatch, ticket lifecycle expansion, deployment, or external business actions.
