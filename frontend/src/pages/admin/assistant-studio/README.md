# Assistant Studio UI Architecture

## 1. Purpose & Scope

The **Assistant Studio** (`frontend/src/pages/admin/assistant-studio/`) serves as the unified administrative command center for the FastAPI Bookings conversational assistant platform. It consolidates prompt policy management, multi-provider tone control, live runtime previewing, few-shot style curation, autonomous knowledge ingestion, and safety guardrail auditing into a single channel-neutral interface.

### What it Owns:
- **Unified 8-Section Control Center**:
  1. **Overview**: Real-time engine status, active transport routes (SMS, WhatsApp, Webchat, Simulated), provider readiness score, throughput metrics, and safety telemetry.
  2. **Prompt Composer**: Visual multi-layer editor reflecting the 10-tier hierarchy, Tier 1 immutable platform safety lock, tenant cancellation policies, provider overlays, and interactive Style Lab sliders with real-time distress suppression warnings.
  3. **Runtime Preview & Simulator**: Live split-view sandbox featuring an interactive chat on the left and an Inspection Panel on the right (assembled prompts breakdown, executed live tools, resolved variables, and active priors).
  4. **Example Library**: Searchable and filterable table/cards of `MessageStyleExample` entries with scope toggling, intent filtering, and hash fingerprint verification.
  5. **Knowledge Review & Curator**: Curation queue for learned `KnowledgeProposal` entries with provider isolation badges, one-click accept/quarantine/reject, and explicit warning triggers for dynamic dates or prices.
  6. **Import Centre**: Cryptographically verified importer for `approved_intent_examples.jsonl` displaying SHA-256 fingerprint verification (`F0C80D93EAB23D7772B7454C81F38027D23D1C6D6E88D4F1EF1314E5B54303A6`), dry-run options, and execution reports.
  7. **Variables & Tools**: Interactive variable dictionary (`{{business_name}}`, `{{provider_name}}`, etc.) and Live Tool Catalog for the 5 server-enforced live tools (`check_availability`, `quote_travel`, `service_lookup`, `provider_lookup`, `address_validation`).
  8. **Evaluation & Safety**: Automated benchmark evaluation suite running test scenarios across edge cases (out-call travel bounds, multi-day availability checking, prompt injection resistance, emotion modulation).
- **Multi-Provider & Channel Neutrality**: Seamless switching between Tenant-Wide Default and individual provider overlays across SMS, WhatsApp, Webchat, and Simulated channels.

### What it Deliberately Avoids:
- Direct mutation of production financial transactions or live SMS dispatch to real customers without operator confirmation.
- Exposing raw database IDs or allowing LLM models to forge `tenant_id` or `provider_id` parameters.
- Mixing static factual knowledge (`CuratedMemory`) with procedural conversational examples (`MessageStyleExample`).
- Client-side bypass of Tier 1 platform safety invariants.

---

## 2. Architecture & Key Files

```
frontend/src/pages/admin/assistant-studio/
├── index.tsx                         # Master shell: Provider Selector, Channel Pills, 8-Tab Navigation
├── types.ts                         # Strongly typed TypeScript interfaces for tabs, priors, tools, and proposals
├── README.md                        # Living module architecture and operation documentation
└── tabs/
    ├── overview-tab.tsx             # Tab 1: Engine status, channel orchestration, throughput, readiness
    ├── prompt-composer-tab.tsx      # Tab 2: 10-tier hierarchy editor, Style Lab sliders, situational warning
    ├── simulator-tab.tsx            # Tab 3: Interactive chat simulator with multi-tab inspection panel
    ├── example-library-tab.tsx      # Tab 4: Searchable MessageStyleExample cards with intent & scope filters
    ├── knowledge-curator-tab.tsx    # Tab 5: KnowledgeProposal review queue with dynamic date/price warnings
    ├── import-centre-tab.tsx        # Tab 6: Cryptographic SHA-256 verified approved dataset importer
    ├── variables-tools-tab.tsx      # Tab 7: Interpolation variable dictionary & server-enforced tool catalog
    └── evaluation-safety-tab.tsx    # Tab 8: Guardrail evaluation benchmarks and edge-case test suite
```

### Integrated Application Routes:
- `/admin/assistant-studio`: Default overview landing
- `/admin/assistant-studio/:tab`: Direct deep-linking to any of the 8 studio sections

---

## 3. Setup, Configuration & Dependencies

- **React 19 & React Router 7**: Declarative routing and state persistence across tab switches.
- **Tailwind CSS v4 & Radix UI**: High-density dashboard aesthetics, responsive badges, cards, and modal dialogs.
- **Lucide Icons**: Semantic iconography for safety locks, tools, telemetry, and transports.
- **Backend API Endpoints**:
  - `GET /api/admin/providers`: Dynamic population of provider scoping selector.
  - `GET /api/conversations`: Channel-neutral conversation retrieval.
  - `GET /api/sms/curator/memories`: Curated factual memory store.
  - `GET /api/sms/curator/quarantined`: Proposals quarantined due to dynamic date/price risks.

---

## 4. Core Workflows & Contracts

### 1. 10-Tier Hierarchy Prompt Assembly
1. **Tier 1 (Immutable Platform Safety)**: Non-negotiable platform rules against jailbreaking, PII disclosure, or hallucination.
2. **Tier 2 (Authoritative Live Tool Truth)**: Real-time tool outputs supersede all conversational claims and static memory.
3. **Tier 3 (Tenant Business Policy)**: Cancellation windows and deposit requirements.
4. **Tier 4 (Shared Base Assistant Policy)**: `Default Agent Policy v1` canonical 5-phase guided dialogue.
5. **Tier 5 (Provider Prompt Overlay)**: Provider-specific tone, specialties, and bio.
6. **Tier 6 (Style Lab Priors)**: Numerical traits (Warmth, Wit, Sarcasm, Directness, Chattiness, Patience) with automatic distress damping.
7. **Tier 7 (Curated Facts)**: Verified facts from `CuratedMemory`.
8. **Tier 8 (Few-Shot Style Examples)**: Up to 3 relevant pairs from `MessageStyleExample`.
9. **Tier 9 (Current Conversation State)**: Intent and reservation draft context.
10. **Tier 10 (Sliding Message History)**: Message turns enclosed in untrusted customer boundaries.

### 2. Live Tool Server-Enforced Binding
When tools (`check_availability`, `quote_travel`, `service_lookup`, `provider_lookup`, `address_validation`) execute:
- Any `tenant_id` or `provider_id` parameters sent from the client or LLM are forcefully stripped.
- The server injects authoritative scoping from the authenticated session context, preventing cross-tenant or cross-provider data leakage.

### 3. Epistemic Separation Invariant
- **CuratedMemory**: Stores static facts ONLY (clinic address, parking instructions, practitioner credentials).
- **MessageStyleExample**: Stores conversational tone and procedural flow ONLY (greetings, polite declines).
- **Dynamic Data (Slots, Live Quotes)**: NEVER stored in either table; computed on-the-fly via Tier 2 tools.

---

## 5. Data Safety & Isolation

- **Tenant Scoping**: All queries and proposals are strictly partitioned by `tenant_id`.
- **Provider Boundaries**: Provider overlays and proposals carry explicit provider ID tags; staff cannot view or modify other providers' private overlays without administrative privileges.
- **Anti-Hallucination Guardrails**: Real-time warnings flag proposals containing dynamic operational keywords (`tomorrow at 3pm`, `discount $99`), recommending immediate rejection to prevent stale availability claims.
- **Situational Modulation**: When customer distress is detected, sarcasm is clamped to 0/5 and patience is boosted to 5/5.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Streaming Token Inspection**: Real-time SSE token streaming can be integrated directly with the Simulator inspection panel for live token-by-token layer analysis.
- **Dynamic Schema Tool Visualizer**: Future enhancement to allow drag-and-drop registration of custom tenant-defined live tools.

---

## 7. Verification & Testing Commands

To verify TypeScript compilation and build cleanliness:

```bash
cd frontend
npx tsc --noEmit
npm run build
```
