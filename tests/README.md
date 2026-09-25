# Test Architecture & Verification Gates

## Purpose & Scope
The `tests/` directory contains the automated test suites for **FastAPI Bookings**.

Test coverage spans:
- Core booking lifecycle & double-booking prevention.
- Cal.com headless scheduling federation.
- Website builder, draft saving, and live publishing.
- Numbered mock scenarios & SMS dialogue engine.
- Chatwoot webhook intake & agentbot processing.
- Multi-tier role hierarchy (`owner`, `manager`, `provider`).
- Client self-service portal & dispute resolution center.
- Umbrella directory & geo-radius search.
- Privacy-safe OpenTelemetry telemetry pipeline.

---

## Directory & Test Suite Inventory

| Test File | Domain Covered |
|---|---|
| `test_website_module.py` | Website builder CRUD, publish toggle, AI copy generation, chat intake |
| `test_calcom_adapter.py` | Headless Cal.com API communication, event types, slot sync |
| `test_calcom_router.py` | Cal.com admin endpoints & embed configuration |
| `test_sms_integration.py` | Inbound SMS routing, state machine, outbox queue delivery |
| `test_sms_foundation.py` | SMS account isolation, receipt and outbound idempotency, staff lifecycle/timeline, correction evidence and blocked-contact safety |
| `test_sms_openai.py` | Prompt hierarchy plus review-first and fail-closed AI behavior for dynamic enquiries/provider failures |
| `test_chatwoot_agentbot.py` | Webhook verification, agentbot replies, contact sync |
| `test_tenant_modules.py` | Subscription tiers (`starter`, `growth`, `unlimited`) & add-on quota enforcement |
| `test_role_hierarchy.py` | 3-tier internal RBAC: Owner, Manager, and Provider scoping |
| `test_client_portal.py` | OTP auth, 1-tap reschedule/cancellation, dispute lodging |
| `test_umbrella_directory.py` | Geo-radius Haversine calculations & clinic discovery |
| `test_telemetry_pipeline.py` | OTLP export, structural attributes, error-free fallback |
| `test_telemetry_redaction.py` | 100% PII scrub validation (zero phone numbers or names exported) |
| `test_resident_agent.py` | Deep audit runner and SSE event streams |
| `test_knowledge_curator_safety.py` | Proposal-only curation, dynamic-fact rejection, tenant/provider isolation, governed review and retrieval |
| `test_production_rollout_stages.py` | Controlled Production Rollout verification suite (Stages 1–4): Synthetic provider, single real provider (22), small provider cohort (7, 22, 23, 1), and whole-tenant activation (Tenant 1) |

---

## Execution Commands

```bash
# Run all core release tests
$env:PYTHONPATH='.'; .venv\Scripts\python.exe -m pytest tests/test_website_module.py tests/test_calcom_adapter.py tests/test_calcom_router.py tests/test_sms_integration.py tests/test_telemetry_pipeline.py tests/test_clean_numbered_data_and_scenarios.py tests/test_client_portal.py tests/test_tenant_modules.py tests/test_role_hierarchy.py tests/test_umbrella_directory.py -v

# Run with coverage report
.venv\Scripts\python.exe -m pytest --cov=app tests/

# Run governed knowledge curator and PII regression tests
.venv\Scripts\python.exe -m pytest tests/test_knowledge_curator_safety.py tests/test_track4_pii_scrubber.py -q
```

Knowledge curator tests use an in-memory synthetic database. They do not call
external AI services, send SMS, create real bookings or read `.env`.
