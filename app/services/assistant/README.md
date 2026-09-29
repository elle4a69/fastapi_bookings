# Assistant Service: Prompt Architecture, Variable Engine & Live Tool Framework

## 1. Purpose & Scope

The `app/services/assistant` package delivers the core intelligence, prompt orchestration, variable resolution, and server-enforced tool execution layer for FastAPI Bookings' conversational platform.

### What it Owns:
- **Typed Runtime Context (`runtime_context.py`)**: Strongly typed data structures representing normalized channel-neutral conversation turns, tenant/provider scoping, client profiles, operating locations, and live tool execution telemetry.
- **Central Variable Registry (`variable_registry.py`)**: Secure, tenant-isolated interpolation of runtime, database, and system variables (`{{business_name}}`, `{{provider_name}}`, `{{location_name}}`, `{{location_address}}`, `{{channel}}`, `{{current_date}}`, `{{current_time}}`, `{{booking_link}}`) into prompt templates with graceful failure modes for unknown variables.
- **10-Tier Precedence Hierarchy Engine (`prompt_policy.py`)**: Strict assembly order enforcing platform safety and empirical tool ground truth above provider styles, curated memories, or untrusted customer inputs.
- **Shared Base Assistant Policy (`Default Agent Policy v1`)**: Canonical five-phase guided booking dialogue (Greeting & Discovery -> Location & Fulfillment -> Slot Exploration -> Reservation -> Escalation).
- **Server-Enforced Live Tool Framework (`tools.py`)**: Allowlist execution engine for 5 read-only live tools (`check_availability`, `quote_travel`, `service_lookup`, `provider_lookup`, `address_validation`) that forcibly binds tenant and provider scoping server-side, preventing LLM parameter spoofing or cross-tenant data leakage.

### What it Deliberately Avoids:
- Direct mutation of bookings or payments without prior verification or operator confirmation.
- Direct raw SQL execution by LLM models.
- Exposure of `tenant_id` or `provider_id` parameters in OpenAI/LLM tool definitions.
- Relying on static memory or customer claims when authoritative live tool endpoints exist.

---

## 2. Architecture & Key Files

```
app/services/assistant/
├── __init__.py               # Public exports of context, variables, policy, and tool engine
├── runtime_context.py        # RuntimeContext, ClientInfo, LocationInfo, NormalizedTurn, ToolExecution
├── variable_registry.py      # VariableDefinition, VariableRegistry, default standard resolvers
├── prompt_policy.py          # 10-Tier Precedence Hierarchy, Default Agent Policy v1, Style Lab trait priors
├── tools.py                  # Server-enforced live tool implementations & AssistantToolEngine
└── README.md                 # Living module architecture documentation
```

### The 10-Tier Precedence Hierarchy

Prompts are assembled in strict descending order of authority:

| Tier | Layer Name | Description & Invariant |
|---|---|---|
| **Tier 1** | **Immutable Platform Safety & Privacy** | Highest authority. Non-negotiable rules against prompt leakage, jailbreaking, PII disclosure, hallucinating prices/slots, or pretending to be human. Cannot be overridden by tenant or provider. |
| **Tier 2** | **Authoritative Live Tool Truth** | Real-time tool outputs (`check_availability`, `quote_travel`, etc.) supersede memory, conversation history, and customer claims. |
| **Tier 3** | **Tenant / Business Policy** | Business-specific cancellation windows, deposit policies, and operating hours. |
| **Tier 4** | **Shared Base Assistant Policy** | Default Agent Policy v1: guided booking protocol and clarification workflows. |
| **Tier 5** | **Provider Prompt Overlay** | Provider-specific voice, bio, custom instructions, and specialties. Bound by Tier 1 & Tier 2. |
| **Tier 6** | **Style Lab Profile** | Stylistic prior traits (warmth, directness, wit, sarcasm, patience, brevity) with automatic situational modulation during customer distress. |
| **Tier 7** | **Approved Factual Knowledge** | Durable facts from `CuratedMemory` (status='active', conflict_state='clear'). |
| **Tier 8** | **Approved Procedural / Style Examples** | Few-shot demonstration pairs (`MessageStyleExample`). |
| **Tier 9** | **Current Conversation State** | Active intent, tentative slot selections, identified client details. |
| **Tier 10** | **Recent Message History (Sliding Window)** | Recent customer and assistant turns demarcated by explicit injection-defense system boundaries. |

---

## 3. Setup, Configuration & Dependencies

- **Database Models**: Integrates with `Tenant`, `Provider`, `Location`, `Service`, and `CuratedMemory`.
- **Domain Services**:
  - `app/services/booking/availability_service.py` (5-segment operational window availability calculation).
  - `app/services/routing/travel_service.py` (dual-route chargeable and operational transit calculations).
  - `app/services/routing/geocoding.py` (local Australian postcode DB and centroid resolution).
- **Python / Dependencies**:
  - Pydantic v2 for typed validation and serialization.
  - SQLAlchemy 2.0 ORM sessions.
  - Python standard library `zoneinfo` for location-aware date/time formatting.

---

## 4. Core Workflows & Contracts

### 1. Variable Resolution & Prompt Assembly
```python
from app.services.assistant import (
    RuntimeContext,
    LocationInfo,
    assemble_assistant_prompt,
)

context = RuntimeContext(
    tenant_id=1,
    provider_id=101,
    channel_type="sms",
    location=LocationInfo(id=201, name="CBD Clinic", timezone="Australia/Sydney"),
)
context.add_turn(role="user", content="What times can I book tomorrow?")

assembled = assemble_assistant_prompt(
    context=context,
    tenant_policy="Cancellations require 24 hours notice.",
    db=db_session,
)

# assembled.system_prompt contains Tiers 1-9
# assembled.messages contains [{"role": "system", ...}, {"role": "user", ...}]
```

### 2. Server-Enforced Tool Execution
```python
from app.services.assistant import AssistantToolEngine

engine = AssistantToolEngine()

# Model emits tool call with arguments
tool_call_args = {
    "service_id": 301,
    "start_date": "2026-10-01",
    "end_date": "2026-10-01",
    # Any attempt by the model to supply tenant_id or provider_id is stripped
    "tenant_id": 999,
}

result = engine.execute_tool(
    tool_name="check_availability",
    arguments=tool_call_args,
    context=context,
    db=db_session,
)
```

---

## 5. Data Safety & Isolation

1. **Server-Enforced Scoping**:
   - In `AssistantToolEngine.execute_tool`, any `tenant_id`, `tenant`, `provider_id`, or `provider` keys in the arguments dictionary are stripped immediately.
   - Authoritative scoping is bound directly from `RuntimeContext.tenant_id` and `RuntimeContext.provider_id`.
2. **Fail-Closed Cross-Tenant Queries**:
   - If an LLM attempts to look up a service ID or location ID belonging to a different tenant, the database filter enforces `tenant_id == context.tenant_id`, causing the lookup to return not found / unauthorized.
3. **Prompt Injection Defense**:
   - Tier 10 message history turns are wrapped in explicit boundary markers instructing the model that external customer turns are untrusted and must never override system directives.
4. **Situational Modulation**:
   - If customer distress or frustration keywords are detected in recent turns, `sarcasm` is forced to `0/5` and `patience` is boosted to `4+/5`.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Multi-day Availability Pagination**: `check_availability` currently limits range lookups to a maximum of 7 calendar days per invocation to prevent long-running computations.
- **Async Tool Execution in Sync Callers**: `quote_travel_tool` provides a synchronous wrapper running in a ThreadPoolExecutor when called within active running event loops.
- **Future Extension**: Integration of vector similarity search for CuratedMemory entries within Tier 7 retrieval.

---

## 7. Verification & Testing Commands

To run the complete test suite for assistant tools, variables, and prompt assembly:

```bash
.venv\Scripts\python.exe -m pytest tests/test_assistant_tools_and_prompts.py -v
```
