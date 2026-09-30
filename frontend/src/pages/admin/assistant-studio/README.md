# Assistant Studio UI & API Architecture

## 1. Purpose & Scope

The **Assistant Studio** (`frontend/src/pages/admin/assistant-studio/` and `app/api/routers/assistant_studio.py`) serves as the authoritative, multi-tenant administrative command center for the FastAPI Bookings conversational assistant platform. It consolidates prompt policy management, multi-provider tone control, live runtime simulation, few-shot style curation, autonomous knowledge ingestion, and safety guardrail auditing into a single channel-neutral interface and real backend API.

### STRICT PLATFORM COMPLIANCE (AGENTS.md Rule 3):
- **Mock Implementations Eliminated**: 100% of synthetic `setTimeout` handlers and hardcoded simulated state have been eliminated across all frontend tabs.
- **Real Backend APIs**: Every tab communicates directly with real, authenticated, tenant-scoped endpoints mounted under `/api/admin/assistant-studio`.
- **Database Persistence**: State mutations persist to `Tenant`, `SmsBootcampSettings`, `SmsPromptProfile`, `MessageStyleExample`, `CuratedMemory`, and `KnowledgeProposal` models.

### Unified 8-Section Control Center:
1. **Overview**: Real-time tenant operational statistics (total channel accounts, active conversations, approved curated facts in `CuratedMemory`, approved style examples in `MessageStyleExample`, message volume, and readiness score).
2. **Prompt Composer**: Visual multi-layer editor backed by `GET` and `PUT` `/api/admin/assistant-studio/policy` persisting `tenant_policy` directly to `Tenant.assistant_policy`, provider overlay to `SmsPromptProfile`, and training notes / Style Lab priors to `SmsBootcampSettings`.
3. **Simulator Sandbox**: Real conversational simulation turn backed by `POST /api/admin/assistant-studio/simulate`, executing `RuntimeContext`, `PromptPolicyAssembler`, and `AssistantToolEngine` against live database tables.
4. **Example Library**: Live CRUD operations on `MessageStyleExample` via `GET`, `POST`, `PUT`, `DELETE` `/api/admin/assistant-studio/examples`. Platform seeds (`tenant_id === null`) are locked system-wide with read-only badges and disabled mutation controls. Tenant-owned examples support full edit, active toggle, and deletion.
5. **Knowledge Review & Curator**: Human-in-the-loop review queue backed by `GET /api/admin/assistant-studio/curator/proposals` and `POST /api/admin/assistant-studio/curator/proposals/{id}/curate`. Canonical decision codes (`accepted`, `evidence_only`, `pending_review`, `quarantined`, `rejected`, `superseded`) are visually badged, with clear distinction between durable factual knowledge (promoted to `CuratedMemory`) and procedural style guidance (promoted to `MessageStyleExample`), plus extracted variables inspection.
6. **Import Centre**: Real dataset import via `POST /api/admin/assistant-studio/import` calling `import_approved_style_examples` with cryptographic SHA-256 validation.
7. **Variables & Tools**: Live variable registry resolution (`GET /api/admin/assistant-studio/variables`) and server-enforced tool schemas (`GET /api/admin/assistant-studio/tools`).
8. **Evaluation & Safety**: Live benchmark suite execution via `POST /api/admin/assistant-studio/evaluate` verifying 6 safety, availability, travel radius, and multi-tenant invariants against live models.

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

---

## 3. Backend API Contract & Endpoints

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

## 4. Multi-Tenant Scoping, Epistemic Integrity & Security

1. **Authentication**: All endpoints require a valid administrative JWT via `X-Token` and tenant resolution via `X-Tenant` or hostname.
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

## 5. Verification & Testing Commands

To run backend integration tests:
```bash
.venv\Scripts\python.exe -m pytest -q tests/test_assistant_studio_api.py
```

To run the frontend TypeScript type check:
```bash
cd frontend
.\node_modules\.bin\tsc.cmd -b --noEmit
```

To compile production Vite bundle:
```bash
cd frontend
npm run build
```
