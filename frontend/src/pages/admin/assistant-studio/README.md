# Assistant Studio UI & API Architecture

## 1. Purpose & Scope

The **Assistant Studio** (`frontend/src/pages/admin/assistant-studio/` and `app/api/routers/assistant_studio.py`) serves as the authoritative, multi-tenant administrative command center for the FastAPI Bookings conversational assistant platform. It consolidates prompt policy management, multi-provider tone control, live runtime simulation, few-shot style curation, autonomous knowledge ingestion, and safety guardrail auditing into a single channel-neutral interface and real backend API.

### STRICT PLATFORM COMPLIANCE (AGENTS.md Rule 3):
- **Mock Implementations Eliminated**: 100% of synthetic `setTimeout` handlers and hardcoded simulated state have been eliminated across all frontend tabs.
- **Real Backend APIs**: Every tab communicates directly with real, authenticated, tenant-scoped endpoints mounted under `/api/admin/assistant-studio`.
- **Database Persistence**: State mutations persist to `SmsBootcampSettings`, `SmsPromptProfile`, `MessageStyleExample`, `CuratedMemory`, and `KnowledgeProposal` models.

### Unified 8-Section Control Center:
1. **Overview**: Real-time tenant operational statistics (total channel accounts, active conversations, approved curated facts in `CuratedMemory`, approved style examples in `MessageStyleExample`, message volume, and readiness score).
2. **Prompt Composer**: Visual multi-layer editor backed by `GET` and `PUT` `/api/admin/assistant-studio/policy` persisting to `SmsBootcampSettings` and `SmsPromptProfile`.
3. **Simulator Sandbox**: Real conversational simulation turn backed by `POST /api/admin/assistant-studio/simulate`, executing `RuntimeContext`, `PromptPolicyAssembler`, and `AssistantToolEngine` against live database tables.
4. **Example Library**: Live CRUD operations on `MessageStyleExample` via `GET`, `POST`, `PUT`, `DELETE` `/api/admin/assistant-studio/examples`.
5. **Knowledge Review & Curator**: Human-in-the-loop review queue backed by `GET /api/admin/assistant-studio/curator/proposals` and `POST /api/admin/assistant-studio/curator/proposals/{id}/curate`.
6. **Import Centre**: Real dataset import via `POST /api/admin/assistant-studio/import` calling `import_approved_style_examples` with cryptographic SHA-256 validation.
7. **Variables & Tools**: Live variable registry resolution (`GET /api/admin/assistant-studio/variables`) and server-enforced tool schemas (`GET /api/admin/assistant-studio/tools`).
8. **Evaluation & Safety**: Live benchmark suite execution via `POST /api/admin/assistant-studio/evaluate` verifying 6 safety, availability, travel radius, and multi-tenant invariants.

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
        ├── prompt-composer-tab.tsx      # Tab 2: 10-tier hierarchy editor, Style Lab sliders, DB persistence
        ├── simulator-tab.tsx            # Tab 3: Interactive chat simulator with live tool execution
        ├── example-library-tab.tsx      # Tab 4: Real MessageStyleExample CRUD with search & intent filters
        ├── knowledge-curator-tab.tsx    # Tab 5: Live KnowledgeProposal curation into CuratedMemory
        ├── import-centre-tab.tsx        # Tab 6: Cryptographic SHA-256 verified dataset importer
        ├── variables-tools-tab.tsx      # Tab 7: Dynamic variable dictionary & server-enforced tool catalog
        └── evaluation-safety-tab.tsx    # Tab 8: Live guardrail evaluation benchmarks against DB
```

---

## 3. Backend API Contract & Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/assistant-studio/overview` | Live operational statistics & channel account breakdown |
| `GET` | `/api/admin/assistant-studio/policy` | Read 10-tier policy configurations & active style profile |
| `PUT` | `/api/admin/assistant-studio/policy` | Persist provider overlay, training notes, and style profile to DB |
| `POST` | `/api/admin/assistant-studio/simulate` | Execute real simulation turn with live tool loop & prompt assembly |
| `GET` | `/api/admin/assistant-studio/examples` | Query `MessageStyleExample` filtered by tenant, provider, intent |
| `POST` | `/api/admin/assistant-studio/examples` | Create new `MessageStyleExample` with placeholder validation |
| `PUT` | `/api/admin/assistant-studio/examples/{id}` | Update existing style example (toggle active, change text) |
| `DELETE` | `/api/admin/assistant-studio/examples/{id}` | Delete style example from database |
| `GET` | `/api/admin/assistant-studio/curator/proposals` | List pending/reviewed knowledge proposals for tenant |
| `POST` | `/api/admin/assistant-studio/curator/proposals/{id}/curate` | Approve to `CuratedMemory`, quarantine, or reject proposal |
| `POST` | `/api/admin/assistant-studio/import` | Execute SHA-256 verified asset importer into `MessageStyleExample` |
| `GET` | `/api/admin/assistant-studio/variables` | Return registered variables with live resolved values |
| `GET` | `/api/admin/assistant-studio/tools` | Return 5 server-enforced live tool definitions |
| `POST` | `/api/admin/assistant-studio/evaluate` | Execute 6 live safety benchmark scenarios against database |

---

## 4. Multi-Tenant Scoping & Security

1. **Authentication**: All endpoints require a valid administrative JWT via `X-Token` and tenant resolution via `X-Tenant` or hostname.
2. **Server-Side Boundary Enforcement**: All tool calls (`service_lookup`, `quote_travel`, `check_availability`, `provider_lookup`, `address_validation`) enforce `context.tenant_id` and `context.provider_id` server-side; clients and LLMs cannot override or spoof tenant boundaries.
3. **Epistemic Invariant**:
   - `CuratedMemory`: Stores static owner-verified facts only.
   - `MessageStyleExample`: Stores conversational tone and few-shot examples only.
   - Dynamic facts (prices, real-time availability slots, calendar events): Strictly resolved at runtime via live tools, never persisted in static memory tables.

---

## 5. Verification & Testing Commands

To run the backend integration test suite:
```bash
.venv\Scripts\python.exe -m pytest -q tests/test_assistant_studio_api.py
```

To run the frontend TypeScript type check:
```bash
cd frontend
npx tsc --noEmit
```
