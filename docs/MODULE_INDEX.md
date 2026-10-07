# FastAPI Bookings — Application Module Index

This document provides a master catalog of all modules, directories, domain boundaries, and their active operational status across the **FastAPI Bookings** codebase.

---

## 1. Purpose & Scope

The Module Index acts as an authoritative directory for engineers and autonomous agents to locate functional subsystems, identify file ownership, trace integration points, and inspect technical debt or operational readiness without searching ad-hoc transcripts.

---

## 2. Master Module Inventory Table

| Path | Domain / Responsibility | Primary Files / Entrypoint | Verification Command | Status | Link |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `alembic/` | Database Schema Migrations | `env.py`, `script.py`, `872af49ef6c4_initial_schema.py` | `.\.venv\Scripts\alembic.exe heads` | **Compliant (Rule 10)** | [README.md](alembic/README.md) |
| `app/api/routers/` | HTTP REST API Endpoints | `main.py`, `deps.py`, `auth.py` | `pytest tests/test_security_isolation_remediat...` | **Compliant (Rule 10)** | [README.md](app/api/routers/README.md) |
| `app/core/` | Core Configuration & Telemetry | `config.py`, `capability_validator.py`, `redis.py` | `python -m pytest tests/test_telemetry_pipelin...` | **Compliant (Rule 10)** | [README.md](app/core/README.md) |
| `app/db/` | Database Engine & Sessions | `__init__.py`, `database.py`, `async_session.py` | `.\.venv\Scripts\python.exe -c "import sys; sy...` | **Compliant (Rule 10)** | [README.md](app/db/README.md) |
| `app/models/` | SQLAlchemy ORM Data Models | `__init__.py`, `tenant.py`, `tenant_website.py` | `.\.venv\Scripts\python.exe -m py_compile app/...` | **Compliant (Rule 10)** | [README.md](app/models/README.md) |
| `app/services/assistant/` | Assistant Runtime Services | `__init__.py`, `runtime_context.py`, `runtime_service.py` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](app/services/assistant/README.md) |
| `app/services/auth/` | Application Business Services | `__init__.py`, `google_oidc.py`, `chatwoot_sso.py` | `.\.venv\Scripts\python.exe -m pytest tests/te...` | **Compliant (Rule 10)** | [README.md](app/services/auth/README.md) |
| `app/services/booking/` | Core Booking Engine | `__init__.py`, `operational_window.py`, `availability_service.py` | `py -3.11 -m pytest tests/test_dynamic_itinera...` | **Compliant (Rule 10)** | [README.md](app/services/booking/README.md) |
| `app/services/business_assistant/gpt_live/` | Business Assistant Foundation | `session_config.json`, `runtime.py`, `router.py` | `.\.venv\Scripts\python.exe -m pytest tests/te...` | **Compliant (Rule 10)** | [README.md](app/services/business_assistant/gpt_live/README.md) |
| `app/services/business_assistant/` | Business Assistant Foundation | `business_assistant.py`, `repository.py`, `runtime.py` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](app/services/business_assistant/README.md) |
| `app/services/channel/` | Communication Channel Transports | `conversation.py`, `channel.py`, `__init__.py` | `.\.venv\Scripts\python -m pytest -q tests/tes...` | **Compliant (Rule 10)** | [README.md](app/services/channel/README.md) |
| `app/services/curation/` | Semantic Memory Curation | `knowledge_policy.py`, `memory_curator.py`, `retrieval.py` | `.\.venv\Scripts\python.exe -m py_compile app/...` | **Compliant (Rule 10)** | [README.md](app/services/curation/README.md) |
| `app/services/knowledge/` | Knowledge Subsystems & Graphiti | `__init__.py`, `types.py`, `policy.py` | `python -m pytest tests/test_knowledge_phase1_...` | **Compliant (Rule 10)** | [README.md](app/services/knowledge/README.md) |
| `app/services/localization/` | Dynamic Localization & Terminology | `presets.py`, `tenant_translation.py`, `translations.py` | `python -m pytest tests/test_tenant_translatio...` | **Compliant (Rule 10)** | [README.md](app/services/localization/README.md) |
| `app/services/messaging/` | Chatwoot & Omnichannel Messaging | `chatwoot_handoff.py`, `__init__.py` | `python -m pytest tests/test_chatwoot_agentbot...` | **Compliant (Rule 10)** | [README.md](app/services/messaging/README.md) |
| `app/services/` | Application Business Services | `agent_runner.py`, `chatwoot_provisioner.py`, `contact_sync.py` | `python -m pytest tests/test_chatwoot_provisio...` | **Compliant (Rule 10)** | [README.md](app/services/README.md) |
| `app/services/resident_agent/` | Autonomous Resident Sentinel | `sentinel.py`, `fuzzer.py`, `auditor.py` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](app/services/resident_agent/README.md) |
| `app/services/routing/` | Routing & Geospatial Engine | `travel_service.py`, `geocoding.py`, `distance_calculator.py` | `python -m pytest tests/test_distance_calculat...` | **Compliant (Rule 10)** | [README.md](app/services/routing/README.md) |
| `app/services/scheduling/` | Scheduling & Slot Allocation | `calcom_adapter.py`, `slot_allocation_service.py`, `scheduling_service.py` | `pytest tests/test_concurrency.py -v` | **Compliant (Rule 10)** | [README.md](app/services/scheduling/README.md) |
| `app/services/sms/` | Autonomous SMS Dialogue Engine | `inbound_service.py`, `ai_orchestrator.py`, `booking_facade.py` | `python -m pytest tests/test_sms_chatwoot.py t...` | **Compliant (Rule 10)** | [README.md](app/services/sms/README.md) |
| `docs/audits/` | Documentation & Architecture Catalog | `SYSTEM_AUDIT_REPORT.md` | `python scripts/verify_living_docs.py` | **Compliant (Rule 10)** | [README.md](docs/audits/README.md) |
| `docs/` | Documentation & Architecture Catalog | `ARCHITECTURE.md`, `MODULE_INDEX.md`, `AGENT_BOOT_SNAPSHOT.md` | `python scripts/verify_living_docs.py` | **Compliant (Rule 10)** | [README.md](docs/README.md) |
| `frontend/` | React Frontend SPA | `App.tsx`, `api.ts`, `AuthContext.tsx` | `npm test` | **Compliant (Rule 10)** | [README.md](frontend/README.md) |
| `frontend/src/pages/admin/assistant-studio/` | Frontend Admin Assistant Studio | `index.tsx`, `types.ts`, `assistant_studio.py` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/assistant-studio/README.md) |
| `frontend/src/pages/admin/business-assistant/` | Frontend Admin Business Assistant | `index.tsx`, `conversation.tsx`, `assistant-drawer.tsx` | `npm test` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/business-assistant/README.md) |
| `frontend/src/pages/admin/catalog/` | Frontend Admin Catalog & Services | `services.tsx`, `providers.tsx`, `locations.tsx` | `npm run build` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/catalog/README.md) |
| `frontend/src/pages/admin/finance/` | Frontend Admin Finance & Billing | `invoices.tsx`, `payments.tsx`, `promotions.tsx` | `npm run build` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/finance/README.md) |
| `frontend/src/pages/admin/gpt-live/` | Frontend Administration Views | `index.tsx`, `use-gpt-live.ts`, `protocol.ts` | `npm test -- --test-name-pattern="GPT-Live"` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/gpt-live/README.md) |
| `frontend/src/pages/admin/` | Frontend Administration Views | `navigation.ts`, `relationships-matrix.tsx`, `relationships.tsx` | `npm run build` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/README.md) |
| `frontend/src/pages/admin/schedule/` | Frontend Admin Schedule Calendar | `workdays.tsx`, `exceptions.tsx`, `weekly-schedule-editor.tsx` | `npm run build` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/schedule/README.md) |
| `frontend/src/pages/admin/sms/` | Frontend Admin SMS Workspace | `sms-assistant.tsx`, `assistant-thread-panel.tsx`, `assistant-messages-page.tsx` | `npm run build` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/admin/sms/README.md) |
| `frontend/src/pages/portal/` | Frontend Client Portal | `portal-login.tsx`, `portal-dashboard.tsx`, `client-portal-context.tsx` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/portal/README.md) |
| `frontend/src/pages/public/` | Frontend Public Booking Widget | `website-page.tsx`, `umbrella-directory-page.tsx`, `website.tsx` | `.venv\Scripts\python.exe -m pytest tests/test...` | **Compliant (Rule 10)** | [README.md](frontend/src/pages/public/README.md) |
| `mapbox/` | Mapbox GL Geospatial Discovery Prototype | `MapSearch.tsx`, `apiClient.ts`, `LocationManager.tsx` | `npm run check` | **Compliant (Rule 10)** | [README.md](mapbox/README.md) |
| `scripts/` | Operational Automation & Release Gates | `verify_living_docs.py`, `index_living_docs.py`, `query_docs.py` | `python scripts/verify_living_docs.py` | **Compliant (Rule 10)** | [README.md](scripts/README.md) |
| `tests/` | Automated Test Suites | `conftest.py`, `test_concurrency.py`, `test_sms_foundation.py` | `python -m pytest tests/ --ignore=tests/test_f...` | **Compliant (Rule 10)** | [README.md](tests/README.md) |

---

## 3. Subsystem Domain Breakdowns

### 3.1 Application Business Services

#### [Authentication, Google OIDC & Chatwoot SSO Service](app/services/auth/README.md) (`app/services/auth`)
The `app/services/auth` module acts as the central identity broker and Single Sign-On (SSO) gateway for FastAPI Bookings. It owns: - Cryptographic verification of third-party Identity Provider tokens (Google OAuth2 / OpenID Connect). - Secure user sy...
- **Key Files**: `__init__.py`, `google_oidc.py`, `chatwoot_sso.py`
- **Verification**: `.\.venv\Scripts\python.exe -m pytest tests/test_auth_contract.py -v`
- **Known Debt/Issues**: 2 item(s) logged

#### [Services Module](app/services/README.md) (`app/services`)
This module contains the core business logic and external service integrations for the FastAPI Bookings engine. It serves as the middleware connecting our application's API endpoints to external SaaS providers, managing operations like tenant synchro...
- **Key Files**: `agent_runner.py`, `chatwoot_provisioner.py`, `contact_sync.py`, `config.py`, `availability_service.py`, `booking_form_resolver.py`, `booking_relationship_resolver.py`, `chatwoot.py`, `clicksend.py`, `embed_configuration.py`, `fcm.py`, `geocoding.py`
- **Verification**: `python -m pytest tests/test_chatwoot_provisioner.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.2 Assistant Runtime Services

#### [Assistant Service: Prompt Architecture, Variable Engine & Live Tool Framework](app/services/assistant/README.md) (`app/services/assistant`)
The `app/services/assistant` package delivers the core intelligence, prompt orchestration, variable resolution, and server-enforced tool execution layer for FastAPI Bookings' conversational platform....
- **Key Files**: `__init__.py`, `runtime_context.py`, `runtime_service.py`, `variable_registry.py`, `prompt_policy.py`, `tools.py`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_assistant_tools_and_prompts.py tests/test_bootcamp_style_and_tool_audit.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.3 Automated Test Suites

#### [Test Architecture & Verification Gates](tests/README.md) (`tests`)
The automated test framework owns: - Verification of the core booking lifecycle, discrete 15-minute slot allocations, and double-booking collision prevention. - Cal.com headless scheduling federation and event type synchronization. - Website builder,...
- **Key Files**: `conftest.py`, `test_concurrency.py`, `test_sms_foundation.py`, `test_living_documentation.py`, `test_telemetry_redaction.py`, `test_booking.py`, `test_sms_chatwoot.py`, `test_sms_arrivals.py`, `test_assistant_tools_and_prompts.py`, `test_knowledge_curator_safety.py`, `test_client_portal.py`, `test_fuzzer.py`
- **Verification**: `python -m pytest tests/ --ignore=tests/test_fuzzer.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.4 Autonomous Resident Sentinel

#### [Resident Autonomous Agent & Code Sentinel](app/services/resident_agent/README.md) (`app/services/resident_agent`)
The `app/services/resident_agent/` module provides persistent, autonomous codebase supervision, deep subsystem audits, telemetry health sentinels, and transaction integrity fuzzers for **FastAPI Bookings**....
- **Key Files**: `sentinel.py`, `fuzzer.py`, `auditor.py`, `events.py`, `alert_dispatcher.py`, `code_auditor.py`, `engine.py`, `event_broker.py`, `executor.py`, `remediation_planner.py`, `sentinel_scheduler.py`, `skill_library.py`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_resident_agent.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.5 Autonomous SMS Dialogue Engine

#### [SMS Assistant & Autonomous Dialogue Engine](app/services/sms/README.md) (`app/services/sms`)
The SMS Assistant module owns: - Inbound carrier webhook intake with cryptographic signature verification and idempotent receipt logging. - Decommissioned legacy direct carrier routes (including ClickSend / `clicksend` / `click_send`) returning `HTTP...
- **Key Files**: `inbound_service.py`, `ai_orchestrator.py`, `booking_facade.py`, `outbound_service.py`, `operations_service.py`, `outbox_worker.py`, `chatwoot_service.py`, `chatwoot_provisioning_service.py`, `chatwoot_industry_service.py`, `arrival_service.py`, `prompt_builder.py`, `curator_service.py`
- **Verification**: `python -m pytest tests/test_sms_chatwoot.py tests/test_sms_arrivals.py tests/test_sms_bootcamp.py tests/test_sms_webhooks.py -v`
- **Known Debt/Issues**: 10 item(s) logged

### 3.6 Business Assistant Foundation

#### [GPT-Live Business Assistant](app/services/business_assistant/gpt_live/README.md) (`app/services/business_assistant/gpt_live`)
This isolated module creates authenticated GPT-Live WebRTC sessions for an existing Business Assistant conversation. It owns the server-side OpenAI request boundary and the immutable handoff configuration. It deliberately does not expose API keys, pr...
- **Key Files**: `session_config.json`, `runtime.py`, `router.py`
- **Verification**: `.\.venv\Scripts\python.exe -m pytest tests/test_gpt_live.py -q`
- **Known Debt/Issues**: 1 item(s) logged

#### [Business Assistant Foundation](app/services/business_assistant/README.md) (`app/services/business_assistant`)
This package owns tenant- and user-scoped persistence operations, bounded text generation, and server-authorised tool execution for internal Business Assistant conversations. It supports conversational onboarding, live product help, tenant settings d...
- **Key Files**: `business_assistant.py`, `repository.py`, `runtime.py`, `service.py`, `confirmation.py`, `tickets.py`, `idempotency.py`, `product_context.py`, `tool_registry.py`, `website_sanitiser.py`, `realtime.py`, `coding_worker.py`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_business_assistant_foundation.py tests/test_business_assistant_api.py tests/test_business_assistant_tickets_api.py tests/test_business_assistant_idempotency.py tests/test_business_assistant_onboarding_api.py tests/test_business_assistant_realtime_api.py tests/test_business_assistant_tool_registry.py tests/test_business_assistant_coding_worker.py tests/test_business_assistant_realtime_voice.py tests/test_business_assistant_website_builder.py tests/test_business_assistant_hardening_and_rollout.py -q`
- **Known Debt/Issues**: 1 item(s) logged

### 3.7 Chatwoot & Omnichannel Messaging

#### [Chatwoot Messaging & Human Handoff Service](app/services/messaging/README.md) (`app/services/messaging`)
The `app/services/messaging` package owns: - Headless asynchronous API calls to external Chatwoot instances for human escalation (`handoff_to_human`). - Direct outbound bot message delivery into active Chatwoot conversation threads (`send_bot_message...
- **Key Files**: `chatwoot_handoff.py`, `__init__.py`
- **Verification**: `python -m pytest tests/test_chatwoot_agentbot.py -k "handoff" -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.8 Communication Channel Transports

#### [Channel-Neutral Messaging Module](app/services/channel/README.md) (`app/services/channel`)
The **Channel-Neutral Messaging Module** introduces an omnichannel domain model and service foundation for FastAPI Bookings. It decouples the core booking and messaging infrastructure from SMS-specific transports, enabling first-class support for mul...
- **Key Files**: `conversation.py`, `channel.py`, `__init__.py`, `channel_service.py`, `compatibility_facade.py`, `conversations.py`
- **Verification**: `.\.venv\Scripts\python -m pytest -q tests/test_channel_neutral_foundation.py tests/test_channel_neutral.py tests/test_channel_neutral_auditor_edge_cases.py`
- **Known Debt/Issues**: 2 item(s) logged

### 3.9 Core Booking Engine

#### [Booking Domain Service & Dynamic Itinerary Engine](app/services/booking/README.md) (`app/services/booking`)
The `app.services.booking` module is the authoritative domain engine for: - **5-Segment Operational Window Engine**: Calculating exact operational boundaries for in-call and out-call appointments:   `[Inbound Operational Travel] -> [Pre-Buffer] -> [C...
- **Key Files**: `__init__.py`, `operational_window.py`, `availability_service.py`, `slot_allocation_service.py`, `itinerary_service.py`
- **Verification**: `py -3.11 -m pytest tests/test_dynamic_itinerary_phase4.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.10 Core Configuration & Telemetry

#### [Core Configuration, Security, Redis & Telemetry](app/core/README.md) (`app/core`)
The `app/core/` package encapsulates cross-cutting concerns for the application: - Environment settings and secrets loading via Pydantic (`config.py`). - Cryptographic password hashing, JWT access token generation, and role checks (`security.py`). - ...
- **Key Files**: `config.py`, `capability_validator.py`, `redis.py`, `security.py`, `state_machine.py`, `telemetry.py`, `pagination.py`
- **Verification**: `python -m pytest tests/test_telemetry_pipeline.py -v`
- **Known Debt/Issues**: 4 item(s) logged

### 3.11 Database Engine & Sessions

#### [Database Management & Connection Subsystem](app/db/README.md) (`app/db`)
The `app/db/` module is the authoritative connection management, session lifecycle, and engine configuration layer for **FastAPI Bookings**....
- **Key Files**: `__init__.py`, `database.py`, `async_session.py`, `seed.py`, `seed_map_data.py`
- **Verification**: `.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); from app.db.database import engine; print(engine.connect().execute(__import__('sqlalchemy').text('SELECT 1')).scalar())"`
- **Known Debt/Issues**: 4 item(s) logged

### 3.12 Database Schema Migrations

#### [Database Migrations Architecture & Ledger](alembic/README.md) (`alembic`)
The `alembic/` package manages relational schema migrations, version tracking, and schema evolution for **FastAPI Bookings**....
- **Key Files**: `env.py`, `script.py`, `872af49ef6c4_initial_schema.py`, `62202d3e7aa6_add_sms_module.py`, `73a63e930e5b_add_chatwoot_integration.py`, `7a91f2c8d4e0_configurable_booking_forms.py`, `a1b2c3d4e5f6_add_knowledge_graph_projections.py`, `a1c2e3g4i5k6_add_channel_neutral_and_style_example_tables.py`, `b1c2d3e4f5a6_baseline_bridge.py`, `b2c3d4e5f6a7_add_learning_event_worker_leasing.py`, `b2d3f4h5j6l7_add_tenant_assistant_policy.py`, `c4d31b16692d_add_remediation_fields.py`
- **Verification**: `.\.venv\Scripts\alembic.exe heads`
- **Known Debt/Issues**: 8 item(s) logged

### 3.13 Documentation & Architecture Catalog

#### [Platform Audits, Security Reviews & Diagnostic Ledgers](docs/audits/README.md) (`docs/audits`)
The Audits module provides forensic investigations, architectural gap assessments, and verified remediation blueprints across all core systems of the FastAPI Bookings platform....
- **Key Files**: `SYSTEM_AUDIT_REPORT.md`
- **Verification**: `python scripts/verify_living_docs.py`
- **Known Debt/Issues**: 10 item(s) logged

#### [FastAPI Bookings — Central Documentation Index](docs/README.md) (`docs`)
This documentation suite serves as the single source of truth for the system architecture, component contracts, operational guides, and testing protocols. ...
- **Key Files**: `ARCHITECTURE.md`, `MODULE_INDEX.md`, `AGENT_BOOT_SNAPSHOT.md`, `module_manifest.json`, `main.py`, `config.py`
- **Verification**: `python scripts/verify_living_docs.py`
- **Known Debt/Issues**: 3 item(s) logged

### 3.14 Dynamic Localization & Terminology

#### [Dynamic Wording & Industry Translations Engine](app/services/localization/README.md) (`app/services/localization`)
The Localization and Translation Engine owns: - Multi-industry vocabulary adaptability across Allied Health, Automotive, Salons/Wellness, and Professional Services. - Three-tier cascading terminology resolution: System Defaults -> Industry Preset -> ...
- **Key Files**: `presets.py`, `tenant_translation.py`, `translations.py`, `TranslationContext.tsx`, `__init__.py`, `translation.py`
- **Verification**: `python -m pytest tests/test_tenant_translations.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.15 Frontend Admin Assistant Studio

#### [Assistant Studio UI & API Architecture](frontend/src/pages/admin/assistant-studio/README.md) (`frontend/src/pages/admin/assistant-studio`)
The Assistant Studio owns: - **Zero-Mock Platform Compliance (AGENTS.md Rule 3)**: Eliminates synthetic `setTimeout` handlers and hardcoded simulated state; every control communicates with real backend APIs mounted under `/api/admin/assistant-studio`...
- **Key Files**: `index.tsx`, `types.ts`, `assistant_studio.py`, `prompt-composer-tab.tsx`, `knowledge-curator-tab.tsx`, `main.py`, `test_assistant_studio_api.py`, `overview-tab.tsx`, `simulator-tab.tsx`, `example-library-tab.tsx`, `import-centre-tab.tsx`, `variables-tools-tab.tsx`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_assistant_studio_api.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.16 Frontend Admin Business Assistant

#### [Business Assistant Frontend](frontend/src/pages/admin/business-assistant/README.md) (`frontend/src/pages/admin/business-assistant`)
This module delivers both a full-page Business Assistant management view and a persistent, application-wide floating drawer accessible across all authenticated admin routes....
- **Key Files**: `index.tsx`, `conversation.tsx`, `assistant-drawer.tsx`, `business-assistant-context.tsx`, `context-boundary.ts`, `use-gpt-live.ts`, `caption-timeline.tsx`, `ticket-status.tsx`, `use-realtime-voice.ts`, `drawer.tsx`, `assistant-context.tsx`, `boundary.ts`
- **Verification**: `npm test`
- **Known Debt/Issues**: 3 item(s) logged

### 3.17 Frontend Admin Catalog & Services

#### [Service Catalog & Capacity Management](frontend/src/pages/admin/catalog/README.md) (`frontend/src/pages/admin/catalog`)
The catalog module owns: - **Services Management** (`services.tsx`): Treatment catalog, duration settings (15m–180m), base prices, deposit requirements, buffer times, and provider eligibility. - **Locations & Branches** (`locations.tsx`): Physical cl...
- **Key Files**: `services.tsx`, `providers.tsx`, `locations.tsx`, `scheduling.tsx`, `packages.tsx`, `add-ons.tsx`, `products.tsx`, `categories.tsx`
- **Verification**: `npm run build`
- **Known Debt/Issues**: 3 item(s) logged

### 3.18 Frontend Admin Finance & Billing

#### [Admin Finance & Billing Operations](frontend/src/pages/admin/finance/README.md) (`frontend/src/pages/admin/finance`)
The `frontend/src/pages/admin/finance/` directory implements financial administration for **FastAPI Bookings**. It encompasses accounts receivable, payment transaction processing, jurisdictional tax calculations, discount campaigns, and payment gatew...
- **Key Files**: `invoices.tsx`, `payments.tsx`, `promotions.tsx`, `tax-rates.tsx`, `processors.tsx`, `rates.tsx`
- **Verification**: `npm run build`
- **Known Debt/Issues**: 2 item(s) logged

### 3.19 Frontend Admin SMS Workspace

#### [SMS Assistant Control Center](frontend/src/pages/admin/sms/README.md) (`frontend/src/pages/admin/sms`)
The `frontend/src/pages/admin/sms/` directory provides the command and operations center for the conversational SMS AI agent in **FastAPI Bookings**. It gives operational staff real-time visibility and intervention authority over inbound and outbound...
- **Key Files**: `sms-assistant.tsx`, `assistant-thread-panel.tsx`, `assistant-messages-page.tsx`, `inbox.tsx`, `quick-tools-sheet.tsx`, `arrivals-tab.tsx`, `triage-tab.tsx`, `assistant-bootcamp-page.tsx`, `bootcamp-tab.tsx`, `bootcamp-settings-tab.tsx`, `settings.tsx`, `simulator.tsx`
- **Verification**: `npm run build`
- **Known Debt/Issues**: 7 item(s) logged

### 3.20 Frontend Admin Schedule Calendar

#### [Admin Schedule Module](frontend/src/pages/admin/schedule/README.md) (`frontend/src/pages/admin/schedule`)
The Admin Schedule module owns: - Weekly recurring working hours template configuration per provider (`weekly_schedule`). - Date-specific special day overrides (`ProviderSpecialDay` via `/api/admin/providers/{id}/special-days` and `/api/admin/schedul...
- **Key Files**: `workdays.tsx`, `exceptions.tsx`, `weekly-schedule-editor.tsx`
- **Verification**: `npm run build`
- **Known Debt/Issues**: 3 item(s) logged

### 3.21 Frontend Administration Views

#### [GPT-Live Admin Page](frontend/src/pages/admin/gpt-live/README.md) (`frontend/src/pages/admin/gpt-live`)
This module starts and closes the native GPT-Live Business Assistant voice experience. Its shared browser WebRTC hook and caption renderer are used by the direct admin page and the Business Assistant drawer/full-page voice controls. It does not hold ...
- **Key Files**: `index.tsx`, `use-gpt-live.ts`, `protocol.ts`, `caption-timeline.tsx`, `gpt-live.ts`, `timeline.tsx`
- **Verification**: `npm test -- --test-name-pattern="GPT-Live"`
- **Known Debt/Issues**: 1 item(s) logged

#### [Admin Management Portal & App Store](frontend/src/pages/admin/README.md) (`frontend/src/pages/admin`)
The `frontend/src/pages/admin/` directory implements the staff and administrative console for **FastAPI Bookings**. It serves business owners, operators, dispatchers, and practitioners. Key responsibilities include:...
- **Key Files**: `navigation.ts`, `relationships-matrix.tsx`, `relationships.tsx`, `relationships-tree.tsx`, `tenant-modules-context.tsx`, `modules.tsx`, `admin-layout.tsx`, `add-ons.tsx`, `categories.tsx`, `locations.tsx`, `packages.tsx`, `products.tsx`
- **Verification**: `npm run build`
- **Known Debt/Issues**: 2 item(s) logged

### 3.22 Frontend Client Portal

#### [Client Self-Service Portal & Dispute Center](frontend/src/pages/portal/README.md) (`frontend/src/pages/portal`)
The Client Self-Service Portal owns: - Fast OTP phone or email authentication for friction-free customer access without passwords. - Viewing upcoming and historical appointments with real-time status. - 1-tap appointment reschedule and cancellation a...
- **Key Files**: `portal-login.tsx`, `portal-dashboard.tsx`, `client-portal-context.tsx`, `client_portal.py`, `login.tsx`, `dashboard.tsx`, `portal-context.tsx`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_client_portal.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.23 Frontend Public Booking Widget

#### [Public Surface: Single-Page Website & Umbrella Directory](frontend/src/pages/public/README.md) (`frontend/src/pages/public`)
The public module owns: 1. **Public Single-Page Website** (`/site` or `/site/:subdomain`): A responsive, branded website generated by the business owner via the Website Builder. 2. **Embedded Booking Engine**: Directly embedded within `/site` or `/bo...
- **Key Files**: `website-page.tsx`, `umbrella-directory-page.tsx`, `website.tsx`, `page.tsx`, `directory-page.tsx`
- **Verification**: `.venv\Scripts\python.exe -m pytest tests/test_website_module.py tests/test_umbrella_directory.py -v`
- **Known Debt/Issues**: 3 item(s) logged

### 3.24 HTTP REST API Endpoints

#### [HTTP REST API Layer](app/api/routers/README.md) (`app/api/routers`)
The API router module owns: - HTTP ingress, routing, path parameter validation, and JSON serialization. - Public intake endpoints for the frontend booking widget and client portal. - Authenticated administration endpoints for owners, managers, and se...
- **Key Files**: `main.py`, `deps.py`, `auth.py`, `bookings.py`, `availability.py`, `public_bookings.py`, `client_portal.py`, `sms_conversations.py`, `sms_webhooks.py`, `sms_chatwoot.py`, `tenants.py`, `chatwoot_agentbot.py`
- **Verification**: `pytest tests/test_security_isolation_remediation.py -v`
- **Known Debt/Issues**: 10 item(s) logged

### 3.25 Knowledge Subsystems & Graphiti

#### [Knowledge Architecture & Graphiti Subsystem](app/services/knowledge/README.md) (`app/services/knowledge`)
The **Knowledge Subsystem** provides a multi-tenant, provider-isolated graph and cache layer built atop [Graphiti](https://github.com/getzep/graphiti) and Neo4j. It serves as the long-term epistemic memory for business rules, durable facts, style gui...
- **Key Files**: `__init__.py`, `types.py`, `policy.py`, `classifier.py`, `cache.py`, `retrieval.py`, `graphiti_client.py`, `gateway.py`, `curator.py`, `curator_worker.py`, `projection_service.py`, `projection_worker.py`
- **Verification**: `python -m pytest tests/test_knowledge_phase1_gateway.py -v`
- **Known Debt/Issues**: 10 item(s) logged

### 3.26 Mapbox GL Geospatial Discovery Prototype

#### [Mapbox Discovery & Visualization Client](mapbox/README.md) (`mapbox`)
The `mapbox/` directory contains a dedicated, standalone React/Vite single-page web client (`fastapi-bookings-front-end-mapbox`) built to visualize multi-tenant booking discovery on an interactive Mapbox-GL map....
- **Key Files**: `MapSearch.tsx`, `apiClient.ts`, `LocationManager.tsx`, `package.js`, `package-lock.js`, `tsconfig.js`, `App.tsx`, `types.ts`, `BookingWizard.tsx`, `Dashboard.tsx`, `ClientProfile.tsx`, `adminService.ts`
- **Verification**: `npm run check`
- **Known Debt/Issues**: 10 item(s) logged

### 3.27 Operational Automation & Release Gates

#### [Operational & Development Scripts](scripts/README.md) (`scripts`)
The operational scripts suite owns: - **Deterministic Test Seeding** (`seed_clean_numbered_data.py`): Populates consistent, numbered entities (Client 1..5, Provider 1..2, Service 1..5) for automated test suites and manual validation. - **Living Docum...
- **Key Files**: `verify_living_docs.py`, `index_living_docs.py`, `query_docs.py`, `seed_clean_numbered_data.py`, `verify_production_secrets.py`, `module_manifest.json`, `MODULE_INDEX.md`, `sync_mock_to_chatwoot.py`, `generate_pwa_icons.py`, `verify_all_release_gates.py`, `import_assistant_ui_data.py`, `seed_demo_structured_catalog.py`
- **Verification**: `python scripts/verify_living_docs.py`
- **Known Debt/Issues**: 3 item(s) logged

### 3.28 React Frontend SPA

#### [FastAPI Bookings — Frontend Application & PWA](frontend/README.md) (`frontend`)
The frontend provides the complete client and administrative interface across multiple operational surfaces: 1. **Admin Workspace** (`/admin`, `/admin/dashboard`, `/admin/calendar`, `/admin/bookings`, etc.): Comprehensive staff and management control...
- **Key Files**: `App.tsx`, `api.ts`, `AuthContext.tsx`, `TranslationContext.tsx`, `TenantModulesContext.tsx`, `address-autocomplete.tsx`, `main.tsx`, `package.js`, `autocomplete.tsx`
- **Verification**: `npm test`
- **Known Debt/Issues**: 3 item(s) logged

### 3.29 Routing & Geospatial Engine

#### [Routing & Geospatial Services](app/services/routing/README.md) (`app/services/routing`)
The **Routing & Geospatial Services** subsystem provides decoupled dual-route calculations, geographic coordinate resolution, and address standardization for FastAPI Bookings: - **Commercial Travel Calculation (Chargeable Travel)**: Determines what t...
- **Key Files**: `travel_service.py`, `geocoding.py`, `distance_calculator.py`, `travel.py`, `__init__.py`, `distance.py`, `discovery.py`, `locations.py`
- **Verification**: `python -m pytest tests/test_distance_calculator.py -v`
- **Known Debt/Issues**: 10 item(s) logged

### 3.30 SQLAlchemy ORM Data Models

#### [Data Models & Persistence Architecture](app/models/README.md) (`app/models`)
The `app/models/` directory defines the complete SQLAlchemy 2.0 ORM domain schema for **FastAPI Bookings**....
- **Key Files**: `__init__.py`, `tenant.py`, `tenant_website.py`, `user.py`, `provider.py`, `service.py`, `location.py`, `booking.py`, `booking_slot_allocation.py`, `calendar_note.py`, `client.py`, `client_dispute.py`
- **Verification**: `.\.venv\Scripts\python.exe -m py_compile app/models/*.py`
- **Known Debt/Issues**: 10 item(s) logged

### 3.31 Scheduling & Slot Allocation

#### [Scheduling Engine & Cal.com Adapter](app/services/scheduling/README.md) (`app/services/scheduling`)
The Scheduling Engine owns: - Computation of available appointment windows based on provider working hours, shift schedules, custom breaks, and blackout dates. - Service buffer calculation (minimum buffer before and after appointments). - Discrete 15...
- **Key Files**: `calcom_adapter.py`, `slot_allocation_service.py`, `scheduling_service.py`, `booking_slot_allocation.py`
- **Verification**: `pytest tests/test_concurrency.py -v`
- **Known Debt/Issues**: 2 item(s) logged

### 3.32 Semantic Memory Curation

#### [Knowledge Curation](app/services/curation/README.md) (`app/services/curation`)
`app/services/curation/` governs reusable tenant knowledge for the FastAPI Bookings responder. It owns privacy scrubbing, durable-versus-dynamic classification, proposal generation, operator review and safe retrieval....
- **Key Files**: `knowledge_policy.py`, `memory_curator.py`, `retrieval.py`, `pii_scrubber.py`, `curated_memory.py`
- **Verification**: `.\.venv\Scripts\python.exe -m py_compile app/models/curated_memory.py app/schemas/curated_memory.py app/services/curation/knowledge_policy.py app/services/curation/retrieval.py app/services/curation/memory_curator.py`
- **Known Debt/Issues**: 5 item(s) logged

---

## 4. Documentation Maintenance Protocol (Rule 10)

Whenever code is modified, agents and developers MUST update the corresponding module `README.md` to keep this index fresh.

- **Re-index entire repository**:
  ```powershell
  python scripts/index_living_docs.py
  ```
- **Query module details or verification commands**:
  ```powershell
  python scripts/query_docs.py --search "arrival"
  python scripts/query_docs.py --test-command "sms"
  python scripts/query_docs.py --known-issues
  ```
- **Verify compliance (Release Gate)**:
  ```powershell
  python scripts/verify_living_docs.py
  ```

*Catalog generated automatically on 2026-10-07 12:13:32Z by `scripts/index_living_docs.py`.*
