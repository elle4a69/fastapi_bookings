# ANTI-GRAVITY MULTI-PHASE DEPLOYMENT BRIEF
**Project Identifier:** `fastapi_bookings_chatwoot_convergence`  
**Target Repositories:** `f:\Projects\fastapi_bookings` (Primary Application) & Chatwoot Docker Stack  
**Target Audience:** Anti-Gravity Master Project Agent (MPA), Module Managers, and Delegated Sub-Agents  
**Operational Directives:** Strict Compliance with `AGENTS.md` (Zero Mocks, Full Real-World Plumbing, Strict Tenant Isolation)

---

## 1. Executive Mission & Strategic Architecture

### 1.1 Objective
Execute the full architectural convergence between **FastAPI Bookings** (Domain Authority & Booking Operations) and **Chatwoot** (Omnichannel Engagement & Human Staff Automation) while activating multi-industry adaptability, multi-location relational scoping, tenant-configurable wording, and comprehensive security hardening.

### 1.2 Separation of Concerns & Boundary Invariants
1. **Source of Truth Invariant**: FastAPI Bookings is the sole authoritative system of record for Tenants, Users, Locations, Providers, Services, Schedules, Real-Time Availability, Holds, Bookings, Audit Logs, and Wording Profiles.
2. **Account Isolation Invariant**: `1 FastAPI Tenant = 1 Chatwoot Account`. Under no circumstances may multiple tenants share a Chatwoot `account_id`. This guarantees complete isolation for Chatwoot automation rules, macros, custom attributes, inboxes, and canned responses across tenants.
3. **No-Fork Invariant**: Chatwoot runs on stock upstream Docker (`chatwoot/chatwoot:latest`). All cross-system synchronization, provisioning, and webhooks must communicate strictly via Chatwoot’s REST / Platform APIs and authenticated webhooks.
4. **Relational Hierarchy Invariant**:
   $$\text{Tenant} \longrightarrow \text{Locations} \longrightarrow \text{Providers} \longrightarrow \text{Services / Products}$$
   Providers are users associated with zero, one, or more locations within a tenant. Multi-location is an attribute of a single tenant, not separate tenants.
5. **Absolute Prohibition of Mocks (AGENTS.md Rule 3)**: Every single phase must be real, fully plumbed, tested end-to-end, and integrated into live database migrations. Zero synthetic `setTimeout` handlers, zero fake state, zero stub endpoints.

---

## 2. Multi-Phase Deployment Roadmap

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Security Hardening & Isolation Defect Remediation                       │
│ (Fix 5 critical security/isolation vulnerabilities identified in codebase)       │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Dynamic Wording & Industry Translations Engine                          │
│ (SimplyBook.me model: customizable terminology per tenant without schema churn)  │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Multi-Location & Provider Relational Topology Refinement                │
│ (Multi-provider, multi-location relational mapping, location-scoped scheduling)  │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: Chatwoot Industry Automation, Custom Attributes & Macro Provisioning    │
│ (Automated sync of industry custom fields, triage automations & staff macros)    │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: Platform Owner Governance, Telemetry & Subdomain Gateway Routing        │
│ (Chatwoot SuperAdmin workflow, SigNoz low-cardinality telemetry, *.localhost)    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase Specifications & Sub-Agent Mandates

---

### PHASE 1: Security Hardening & Isolation Defect Remediation

#### 1. Context & Scope
Five specific data boundary and tenant leakage vulnerabilities were discovered during architectural audits that must be resolved prior to expanding multi-tenant operations.

#### 2. Target Files & Deficiencies
1. `app/api/routers/chatwoot_agentbot.py` (Line ~220):
   * **Vulnerability**: Ingests `payload.account.id` and blindly maps it directly as `tenant_id` when invoking memory curation, risking cross-tenant memory poisoning if Chatwoot account IDs differ from FastAPI tenant IDs.
   * **Remediation**: Resolve the `Tenant` record using `SmsChatwootBinding` or `Tenant.chatwoot_account_id == payload.account.id` to retrieve the authentic internal `tenant.id`.
2. `app/api/routers/website.py` (Line ~660):
   * **Vulnerability**: Unauthenticated public chat transcript endpoint leaking session metadata.
   * **Remediation**: Enforce tenant-scoped HMAC session token verification or caller authentication.
3. `app/api/routers/public_timeline.py` (Line ~28):
   * **Vulnerability**: Company-wide workdays query lacks an explicit `tenant_id` filter, allowing workdays from one tenant to appear in another tenant’s timeline.
   * **Remediation**: Bind query strictly to `current_tenant.id`.
4. `app/api/routers/general_systems.py` (Line ~110):
   * **Vulnerability**: Admin GDPR consent query retrieves all records globally across all tenants.
   * **Remediation**: Add explicit `db.query(GdprConsent).filter(GdprConsent.tenant_id == current_tenant.id)` constraint.
5. `app/models/booking.py` (Line ~50):
   * **Vulnerability**: Idempotency key constraint is globally unique across the whole table rather than composite `(tenant_id, idempotency_key)`, allowing one tenant to unintentionally block another tenant’s booking submission with the same UUID/key.
   * **Remediation**: Create Alembic migration modifying the unique constraint to `UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_booking_idempotency")`.

#### 3. Sub-Agent Role & Verification Gate
* **Assigned Sub-Agent**: `Security & Isolation Hardening Specialist`
* **Verification Gate**:
  * Execute: `.venv\Scripts\python.exe -m pytest -q tests/test_security_isolation_remediation.py tests/test_chatwoot_agentbot.py`
  * Assert zero cross-tenant leakage, 100% test pass.

---

### PHASE 2: Dynamic Wording & Industry Translations Engine

#### 1. Context & Scope
Different industries require different operational vocabularies (e.g. Healthcare uses *Patient / Practitioner / Consultation*, Automotive uses *Customer / Technician / Service*, Salons use *Client / Stylist / Appointment*). Hardcoding names or creating parallel database columns clutters models and creates maintenance debt. We implement the **SimplyBook.me Dynamic Translation Model**.

#### 2. Architectural Blueprint
* **Database Model (`app/models/tenant_translation.py`)**:
  * Stores tenant-specific wording dictionary:
    ```python
    class TenantTranslation(Base):
        __tablename__ = "tenant_translations"
        id = Column(Integer, primary_key=True)
        tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
        locale = Column(String(10), default="en", nullable=False)
        terminology = Column(JSON, nullable=False, default={}) 
        # Structure: {"client": "Patient", "provider": "Physiotherapist", "service": "Treatment", "booking": "Consultation", ...}
    ```
* **Pre-Packaged Industry Presets (`app/services/localization/presets.py`)**:
  * `allied_health`: *Patient, Practitioner, Treatment/Consultation, Clinic*
  * `automotive`: *Customer, Specialist/Mechanic, Service/Repair, Workshop/Bay*
  * `wellness_salon`: *Client, Stylist/Therapist, Service, Salon/Studio*
  * `professional_services`: *Client, Consultant, Session, Office*
* **API Endpoints (`app/api/routers/translations.py`)**:
  * `GET /api/public/translations`: Publicly accessible, tenant-scoped wording for the booking portal.
  * `GET /api/admin/translations`: Admin management endpoint.
  * `PUT /api/admin/translations`: Update custom terms or apply an industry preset.
* **Frontend Translation Provider (`frontend/src/context/TranslationContext.tsx`)**:
  * React Context hook `useTranslation()` providing `t("client")`, `t("provider")`, `t("booking")`.
  * Dynamically interpolates headers, table labels, buttons, and booking steps.

#### 3. Sub-Agent Role & Verification Gate
* **Assigned Sub-Agent**: `Translations & Localization Specialist`
* **Verification Gate**:
  * Run backend tests: `pytest tests/test_tenant_translations.py`
  * Frontend build: `cd frontend && tsc -b --noEmit && npm run build`
  * Verify UI reflects custom terms immediately upon tenant switch.

---

### PHASE 3: Multi-Location & Provider Relational Topology Refinement

#### 1. Context & Scope
Clarify and solidify the relationship between Tenants, Locations, Providers, and Services to ensure that business owners with multiple physical clinics/shops manage them within one single tenant.

#### 2. Architectural Blueprint
* **Relational Schema Enforcement**:
  * `tenants` (1) $\longleftrightarrow$ (Many) `locations`
  * `locations` (Many) $\longleftrightarrow$ (Many) `providers` via `provider_locations` association table
  * `providers` (Many) $\longleftrightarrow$ (Many) `services` via `provider_services` association table
* **Location-Aware Availability & Holds**:
  * When fetching slots (`GET /api/public/availability`):
    * If `location_id` is supplied: return slots only where provider is assigned to that location and location is open on that workday.
    * If provider is mobile: verify service area geofence via Mapbox coordinates.
* **Chatwoot Ingress Routing per Provider/Location**:
  * Ensure `SmsChatwootBinding` allows binding:
    1. Tenant Default Inbox (General front desk)
    2. Provider-Dedicated Inbox (Direct practitioner line)
    3. Location-Dedicated Inbox (Location-specific front desk)

#### 3. Sub-Agent Role & Verification Gate
* **Assigned Sub-Agent**: `Multi-Location Relational Specialist`
* **Verification Gate**:
  * Alembic migration for composite indexes.
  * Test: `pytest tests/test_multi_location_availability.py tests/test_sms_chatwoot.py`

---

### PHASE 4: Chatwoot Industry Automation, Custom Attributes & Macro Provisioning

#### 1. Context & Scope
Fully exploit Chatwoot’s native engine without modifying Chatwoot source code. When a tenant is provisioned or changes its industry profile, automatically configure Chatwoot custom attributes, triage automations, and canned macros via Chatwoot’s Platform REST API.

#### 2. Architectural Blueprint
* **Automated Custom Attribute Provisioning (`app/services/sms/chatwoot_industry_service.py`)**:
  * Automatically creates Chatwoot `custom_attribute_definitions` scoped to `account_id`:
    * For Healthcare: `gp_referral_number`, `health_fund`, `injury_type`.
    * For Automotive: `vehicle_vin`, `vehicle_rego`, `service_mileage`.
    * For General/Salon: `preferred_practitioner`, `hair_length`, `patch_test_date`.
* **Chatwoot Webhook Event Flow**:
  * When a customer sends a message:
    1. Chatwoot runs its native **Automation Rules** (e.g. detect keywords like *"emergency"*, *"quote"*, *"reschedule"* $\rightarrow$ apply label, set priority, assign team).
    2. Chatwoot fires `message_created` webhook to FastAPI Bookings.
    3. FastAPI `AssistantRuntimeService` reads Chatwoot conversation attributes and labels:
       * If labeled `#human-intervention-required` or assigned to a human agent, AI pauses immediately.
       * If unassigned, AI executes turn with industry-specific prompt and tool execution.
* **Macro & Canned Response Provisioning**:
  * Push industry-standard canned responses into Chatwoot (e.g., "Post-Care Instructions", "Directions & Parking Information", "Late Arrival Policy").

#### 3. Sub-Agent Role & Verification Gate
* **Assigned Sub-Agent**: `Chatwoot Automation & Ecosystem Specialist`
* **Verification Gate**:
  * Test: `pytest tests/test_chatwoot_industry_service.py tests/test_chatwoot_provisioning.py`
  * Live verification: Query Chatwoot on port 4000 to verify `custom_attribute_definitions` and `canned_responses` are created on the target account.

---

### PHASE 5: Platform Owner Governance, Telemetry & Subdomain Gateway Routing

#### 1. Context & Scope
Provide the Platform Owner with unified governance across all tenant instances, Chatwoot super-administration, and privacy-safe platform observability.

#### 2. Architectural Blueprint
* **Platform SuperAdmin Navigation & Chatwoot Handshake**:
  * Platform Owner logs in as SuperAdmin in FastAPI Bookings.
  * In Admin UI, provide direct deep-link to Chatwoot SuperAdmin console (`http://localhost:4000/super_admin`) or directly into the tenant’s Chatwoot account (`http://localhost:4000/app/accounts/{chatwoot_account_id}`).
  * Keep Chatwoot legacy default inboxes out of active production flows.
* **Subdomain & RFC 6761 Localhost Gateway**:
  * Support `tenant.localhost:7070` and `tenant.localhost:8000` for native local development without modifying `C:\Windows\System32\drivers\etc\hosts`.
  * Fallback cleanly to `X-Tenant` header for API clients, background workers, and automated test runners.
* **SigNoz & Mapbox Owner-Only Isolation**:
  * SigNoz telemetry and Mapbox configuration dashboards remain strictly restricted to the Platform Owner.
  * Ensure tenant traces in SigNoz contain only low-cardinality structural tags (`tenant_id`, `route`, `status_code`) and zero PII (no phone numbers, names, or prompt texts).

#### 3. Sub-Agent Role & Verification Gate
* **Assigned Sub-Agent**: `Platform Governance & Gateway Specialist`
* **Verification Gate**:
  * Test: `pytest tests/test_tenant_resolution.py tests/test_telemetry_privacy.py`
  * E2E curl against `simplydemo.localhost:8000` verifying 200 OK resolution.

---

## 4. Anti-Gravity Sub-Agent Task Allocation Matrix

| Phase | Sub-Agent Role | Primary Task | Required Verification Gate |
| :--- | :--- | :--- | :--- |
| **Phase 1** | `Security Hardening Specialist` | Fix 5 isolation vulnerabilities in AgentBot, Website, Timeline, GDPR, and Booking Idempotency. | `pytest tests/test_security_isolation_remediation.py` |
| **Phase 1-Audit** | `Independent Security Auditor` | Exhaustive multi-tenant penetration and isolation verification. | Zero regression, audit sign-off. |
| **Phase 2** | `Translations & Localization Specialist` | Implement `TenantTranslation` model, industry presets, REST APIs, and React `TranslationContext`. | `pytest tests/test_tenant_translations.py && npm run build` |
| **Phase 3** | `Multi-Location Relational Specialist` | Refine Location/Provider mappings, location availability constraints, and Chatwoot inbox scoping. | `pytest tests/test_multi_location_availability.py` |
| **Phase 4** | `Chatwoot Automation Specialist` | Provision Chatwoot custom attributes, canned macros, and webhook triage per industry preset. | `pytest tests/test_chatwoot_industry_service.py` |
| **Phase 5** | `Platform Governance Specialist` | Implement SuperAdmin tenant switching links, `*.localhost` routing, and SigNoz privacy guards. | `pytest tests/test_tenant_resolution.py` |
| **Release** | `Git Release & Operations Specialist` | Strict staged review against task allowlists, conventional commit, and upstream push. | Clean git working tree, 0 untracked spills. |

---

## 5. Execution Protocol for Anti-Gravity Orchestrator

1. **Sequential Execution**: Phases must be executed in order (Phase 1 must pass the Independent Security Audit before Phase 2 begins).
2. **Independent Audit Gate**: After each build phase, a dedicated Independent Auditor subagent must be spawned to challenge the deliverables against `AGENTS.md` before proceeding.
3. **Living Documentation Requirement**: Each sub-agent must update the relevant module `README.md` (`app/services/localization/README.md`, `app/services/sms/README.md`, etc.) before reporting completion.
4. **Git Hygiene**: No blanket `git add -A`. Stage only explicit paths matching the phase allowlist.
