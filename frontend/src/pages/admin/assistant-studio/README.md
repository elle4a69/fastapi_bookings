# Assistant Studio UI & API Architecture

The **Assistant Studio** (`frontend/src/pages/admin/assistant-studio/` and `app/api/routers/assistant_studio.py`) serves as the authoritative, multi-tenant administrative command center for the FastAPI Bookings conversational assistant platform. It consolidates prompt policy management, multi-provider tone control, live runtime simulation, few-shot style curation, autonomous knowledge ingestion, and safety guardrail auditing into a single channel-neutral interface and real backend API.

---

## 1. Purpose & Scope

The Assistant Studio owns:
- **Zero-Mock Platform Compliance (AGENTS.md Rule 3)**: Eliminates synthetic `setTimeout` handlers and hardcoded simulated state; every control communicates with real backend APIs mounted under `/api/admin/assistant-studio`.
- **Database Persistence**: State mutations persist directly to `Tenant`, `SmsBootcampSettings`, `SmsPromptProfile`, `MessageStyleExample`, `CuratedMemory`, and `KnowledgeProposal` database tables.
- **Unified 8-Section Control Center**:
  1. *Overview*: Real-time tenant operational statistics (total channel accounts, active conversations, approved curated facts in `CuratedMemory`, approved style examples in `MessageStyleExample`, message volume, and readiness score).
  2. *Prompt Composer*: Visual multi-layer editor backed by `GET` and `PUT` `/api/admin/assistant-studio/policy` persisting `tenant_policy` directly to `Tenant.assistant_policy`, provider overlay to `SmsPromptProfile`, and training notes / Style Lab priors to `SmsBootcampSettings`.
  3. *Simulator Sandbox*: Conversational simulation turns backed by `POST /api/admin/assistant-studio/simulate`, executing `RuntimeContext`, `PromptPolicyAssembler`, and `AssistantToolEngine` against live database tables.
  4. *Example Library*: Live CRUD operations on `MessageStyleExample` via `GET`, `POST`, `PUT`, `DELETE` `/api/admin/assistant-studio/examples`. Platform seeds (`tenant_id === null`) are locked system-wide with read-only badges and disabled mutation controls. Tenant-owned examples support full edit, active toggle, and deletion.
  5. *Knowledge Review & Curator*: Human-in-the-loop review queue backed by `GET /api/admin/assistant-studio/curator/proposals` and `POST /api/admin/assistant-studio/curator/proposals/{id}/curate`.
  6. *Import Centre*: Dataset import via `POST /api/admin/assistant-studio/import` calling `import_approved_style_examples` with cryptographic SHA-256 validation.
  7. *Variables & Tools*: Live variable registry resolution (`GET /api/admin/assistant-studio/variables`) and server-enforced tool schemas (`GET /api/admin/assistant-studio/tools`).
  8. *Evaluation & Safety*: Live benchmark suite execution via `POST /api/admin/assistant-studio/evaluate` verifying 6 safety, availability, travel radius, and multi-tenant invariants.

This module deliberately avoids direct SQL execution by LLM models, exposure of raw tenant credentials in client responses, or treating client-side browser state as authoritative ground truth.

---

## 2. Architecture & Key Files

```
├── app/api/routers/assistant_studio.py # Real authenticated API router
├── app/main.py                         # Mounts router under /api/admin/assistant-studio
├── tests/test_assistant_studio_api.py  # Comprehensive integration test suite
└── frontend/src/pages/admin/assistant-studio/
    ├── index.tsx                         # Master shell: Provider Selector, Channel Pills, 8-Tab Navigation
    ├── types.ts                         # Strongly typed TypeScript interfaces matching backend models
    ├── README.md                        # Living module architecture documentation
    └── tabs/
        ├── overview-tab.tsx             # Tab 1: Live database stats & channel orchestration
        ├── prompt-composer-tab.tsx      # Tab 2: 10-tier hierarchy editor, Style Lab sliders, persistent Tenant Policy
        ├── simulator-tab.tsx            # Tab 3: Interactive chat simulator with live tool execution & prompt assembly
        ├── example-library-tab.tsx      # Tab 4: MessageStyleExample CRUD, platform seed read-only lockdown, edit modal
        ├── knowledge-curator-tab.tsx    # Tab 5: Truthful KnowledgeProposal curation (canonical badges, destination routing)
        ├── import-centre-tab.tsx        # Tab 6: Cryptographic SHA-256 verified dataset importer
        ├── variables-tools-tab.tsx      # Tab 7: Dynamic variable dictionary & server-enforced tool catalog
        └── evaluation-safety-tab.tsx    # Tab 8: Live guardrail evaluation benchmarks against DB
```

### Key Files:
- [index.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/assistant-studio/index.tsx): Main layout coordinating active provider and channel selection with sub-tab routing.
- [types.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/assistant-studio/types.ts): TypeScript type definitions matching Pydantic response models.
- [app/api/routers/assistant_studio.py](file:///f:/Projects/fastapi_bookings/app/api/routers/assistant_studio.py): Backend FastAPI router providing all administrative and simulation endpoints.
- [tabs/prompt-composer-tab.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/assistant-studio/tabs/prompt-composer-tab.tsx): 10-tier prompt hierarchy visualizer and Style Lab controls.
- [tabs/knowledge-curator-tab.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/assistant-studio/tabs/knowledge-curator-tab.tsx): 4-screen epistemic knowledge curation interface.

---

## 3. Setup, Configuration & Dependencies

### Dependencies & Requirements
- **Frontend**: React 18, TypeScript, Tailwind CSS, Lucide React icons, Radix UI primitives.
- **Backend**: FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, and `app/services/assistant` runtime engine.
- **Environment**: Requires active database connectivity (`DATABASE_URL`) and configured OpenAI API key (`OPENAI_API_KEY`) for live simulation turns.
- **Authentication**: All endpoints require a valid administrative JWT via `X-Token` (or `Authorization: Bearer`) and tenant scoping header (`X-Tenant`).

---

## 4. Core Workflows & Contracts

### Backend API Contract & Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/assistant-studio/overview` | Live operational statistics & channel account breakdown |
| `GET` | `/api/admin/assistant-studio/policy` | Read 10-tier policy configurations, `tenant_policy`, & active style profile |
| `PUT` | `/api/admin/assistant-studio/policy` | Persist `tenant_policy` to `Tenant`, provider overlay to `SmsPromptProfile`, and style profile to `SmsBootcampSettings` |
| `POST` | `/api/admin/assistant-studio/simulate` | Execute real simulation turn with live tool loop & prompt assembly |
| `GET` | `/api/admin/assistant-studio/examples` | Query `MessageStyleExample` filtered by tenant, provider, intent |
| `POST` | `/api/admin/assistant-studio/examples` | Create new `MessageStyleExample` with safety and variable placeholder validation |
| `PUT` | `/api/admin/assistant-studio/examples/{id}` | Update existing style example (forbids mutating platform seeds `tenant_id === null`) |
| `DELETE` | `/api/admin/assistant-studio/examples/{id}` | Delete style example from database (forbids deleting platform seeds `tenant_id === null`) |
| `GET` | `/api/admin/assistant-studio/curator/proposals` | List pending/reviewed knowledge proposals for tenant |
| `POST` | `/api/admin/assistant-studio/curator/proposals/{id}/curate` | Promote factual proposals to `CuratedMemory`, procedural style to `MessageStyleExample`, or quarantine/reject |
| `POST` | `/api/admin/assistant-studio/import` | Execute SHA-256 verified asset importer into `MessageStyleExample` |
| `GET` | `/api/admin/assistant-studio/variables` | Return registered variables with live resolved values |
| `GET` | `/api/admin/assistant-studio/tools` | Return 5 server-enforced live tool definitions |
| `POST` | `/api/admin/assistant-studio/evaluate` | Execute 6 live safety benchmark scenarios against database |

---

## 5. Data Safety & Isolation

1. **Authentication & Multi-Tenant Scoping**: All endpoints require a valid administrative JWT via `X-Token` and tenant resolution via `X-Tenant` or hostname. Cross-tenant reads or writes return `404 Not Found` or `403 Forbidden`.
2. **Server-Side Boundary Enforcement**: All tool calls (`service_lookup`, `quote_travel`, `check_availability`, `provider_lookup`, `address_validation`) enforce `context.tenant_id` and `context.provider_id` server-side; clients and LLMs cannot override or spoof tenant boundaries.
3. **Epistemic Invariant**:
   - `CuratedMemory`: Stores static owner-verified facts only (Tier 7).
   - `MessageStyleExample`: Stores conversational tone and few-shot examples only (Tier 8).
   - Dynamic facts (prices, real-time availability slots, calendar events): Strictly resolved at runtime via live tools, never persisted in static memory tables.
4. **Knowledge Proposal Destination Routing**:
   - Curation of style proposals (`knowledge_kind === 'style_example'` or `category === 'style'`) promotes records to `MessageStyleExample`, never polluting `CuratedMemory`.
   - Curation of factual proposals screens candidate facts through safety and injection classifiers before durable insertion into `CuratedMemory`.
5. **Platform Seed Enforceability**:
   - Platform seed examples (`tenant_id === null`) are global priors.
   - Frontend locks down mutations with visible read-only badges and disabled controls.
   - Backend enforces HTTP 403 Forbidden if a tenant attempts to mutate or delete a platform seed.
6. **Privacy-Safe Tool Audit**: Simulator telemetry shows only structural audit fields (tool name, status, timestamp, argument/result key names, and server-bound scope labels). Tool arguments and result bodies—including prices, slots, addresses, and customer data—are intentionally not returned to the browser or written to Bootcamp message metadata.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Long-Running Simulation Turns**: When simulating multi-step turns with external OpenAI API calls, slow networks may cause the request to take 3–5 seconds; the UI maintains an active loading spinner to prevent double-submissions.
- **Platform Seed Customization**: Tenants currently cannot directly clone a platform seed into a tenant-specific override with a single button; cloning currently requires manual creation in the Example Library.
- **Future Work**: Integration of live audio/voice streaming simulation directly within the sandbox tab.

---

## 7. Verification & Testing Commands

To run backend integration tests:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_assistant_studio_api.py -v
```

To run the frontend TypeScript type check:
```powershell
npx tsc --noEmit
```

To compile production Vite bundle:
```powershell
npm run build
```
