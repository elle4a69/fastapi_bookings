# Data Models & Persistence Architecture (`app/models/`)

## 1. Purpose & Scope

The `app/models/` directory defines the complete SQLAlchemy 2.0 ORM domain schema for **FastAPI Bookings**.

### Primary Domain Entities:
- **Tenancy, Media & Core Identity**: `Tenant` (with `status`, `suspended_at`, `suspension_reason`), `TenantWebsite`, `Media` (tenant durable assets, public website eligibility, private clinical/booking notes), `User` (roles: `owner`, `manager`, `provider`, `platform_owner`; flags: `is_platform_owner`, `is_superuser`), `TenantInvitation` (single-use tokens, status lifecycle), `TenantTranslation`.
- **Catalog & Facilities**: `Service`, `Provider`, `Location`, `Category`, `AddOn`, `Product`, `Package`, `Resource`, `LocationProvider`, `LocationService`.
- **Operations & Scheduling**: `Booking`, `BookingSlotAllocation`, `CalendarNote`, `Client`, `ClientDispute`, `WaitlistEntry`, `BlockedTime`, `ReservedTime`.
- **Messaging & Omnichannel**: `Conversation`, `Message`, `ChannelAccount`, `MessageStyleExample`, `SmsAccount`, `SmsConversation`, `SmsMessage`, `SmsOutboundJob`, `SmsAiJob`, `SmsConversationEvent`, `SmsNote`, `SmsChatwootBinding`, `SmsQuickTool`.
- **Commercial & Financial**: `Invoice`, `InvoiceLine`, `Payment`, `PaymentProcessorConfig`, `TaxRate`, `PromotionCode`, `Tip`.
- **Intelligence, Bootcamp & Epistemic Memory**: `CuratedMemory` (with pgvector embedding), `KnowledgeProposal`, `KnowledgeGraphProjection`, `LearningEvent`, `SmsBootcampSettings`, `SmsBootcampRun`, `SmsBootcampConversation`, `SmsBootcampMessage`, `AuditLog`.
- **Business Assistant**: `BusinessAssistantConversation`, `BusinessAssistantMessage`, `BusinessAssistantToolRun`, `BusinessAssistantMemory`, `BusinessAssistantOnboardingProgress`, `SupportTicketDeduplicationClaim`, `SupportTicketEvent`, `AssistantErrorLog`.
- **Support Tickets**: `SupportTicket`, `SupportTicketMessage`, `SupportTicketAuditEvent` (tenant-scoped support tickets with threaded messages, append-only audit events, triage priority, idempotency, error context, and external codex thread coordination).

---

## 2. Architecture & Key Files

```text
app/models/
├── __init__.py               # Re-exports all models and populates Base.metadata
├── tenant.py                 # Multi-tenant account, tiers ('starter', 'growth', 'unlimited'), status ('active', 'suspended'), suspension reason
├── tenant_website.py         # Single-page website builder configurations and template data
├── media.py                  # Durable media assets, public website eligibility, notes, tenant storage
├── user.py                   # User authentication, hashed passwords, roles, is_platform_owner, is_superuser, nullable tenant_id
├── invitation.py             # TenantInvitation model, single-use tokens, roles, and status lifecycle ('pending', 'accepted', 'revoked', 'expired')
├── provider.py               # Staff practitioners, bios, in-call/out-call travel configuration
├── service.py                # Treatments, durations, pricing, buffer rules, in-call/out-call flags
├── location.py               # Physical clinics and composite mappings (location_providers, location_services)
├── booking.py                # Appointment lifecycle, start/end timestamps, status enum, idempotency
├── booking_slot_allocation.py# Discrete 15-minute slot allocation locking table
├── calendar_note.py          # Calendar annotations, partitioned by tenant_id and provider_id
├── client.py                 # Customer directory, contact details, notes
├── client_dispute.py         # Self-service client disputes and resolutions
├── curated_memory.py         # CuratedMemory (active durable facts with pgvector) and KnowledgeProposal queue
├── knowledge_projection.py   # Outbox projection ledger bridging PostgreSQL to Graphiti/Neo4j
├── learning_event.py         # Unified LearningEvent capturing human-in-the-loop signals & worker leases
├── message_style_example.py  # Approved few-shot dialogue exemplars (intent, client_message, assistant_reply)
├── conversation.py           # Channel-neutral conversations and messages
├── sms_conversation.py       # Legacy SMS thread tracking and Chatwoot sync
├── sms_outbox.py             # Outbound SMS jobs, AI jobs, conversation events, notes
├── sms_bootcamp.py           # Bootcamp runs, simulated conversations, and settings
├── business_assistant.py     # Native business assistant conversations, tool runs, tickets, and onboarding
├── support_ticket.py         # SupportTicket, SupportTicketMessage, SupportTicketAuditEvent (UUID PKs)
├── checkout.py               # Commercial invoicing, lines, payments, and processor configs
└── general_systems.py        # Plugin states and GDPR consent tracking
```

### Key Models & Vector Attributes:
- [`CuratedMemory`](file:///f:/Projects/fastapi_bookings/app/models/curated_memory.py#L36):
  * `embedding = Column(Vector(1536), nullable=True)`: 1536-dimensional embedding using `pgvector.sqlalchemy.Vector`.
  * Status constraint: `ck_curated_memories_status` (`active`, `quarantined`, `superseded`).
  * Kind constraint: `ck_curated_memories_kind` (`durable_fact`, `response_guidance`, `style_example`).
  * Index: `ix_curated_memory_retrieval_scope` on `(tenant_id, provider_id, status, effective_from, effective_until)`.
  * HNSW Cosine Index: `ix_curated_memories_embedding_hnsw` on `embedding` using `hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)` (migration `j1k2m3n4p5q6`).
- [`BookingSlotAllocation`](file:///f:/Projects/fastapi_bookings/app/models/booking_slot_allocation.py#L17):
  * `UniqueConstraint("provider_id", "slot_time", name="uq_provider_slot_allocation")`: Discrete 15-minute slot allocation locking table.
- [`KnowledgeGraphProjection`](file:///f:/Projects/fastapi_bookings/app/models/knowledge_projection.py#L35):
  * Outbox ledger tracking synchronization status (`pending`, `processing`, `projected`, `retry`, `dead_letter`) to Graphiti.
- [`SmsBootcampMessage`](file:///f:/Projects/fastapi_bookings/app/models/sms_bootcamp.py#L77):
  * `status = Column(String(32), nullable=False, default="pending", server_default="pending")`: Real database column backed by linear migration `k2m3n4p5q6r7`, superseding previous property hack.
- [`SupportTicket`](file:///f:/Projects/fastapi_bookings/app/models/support_ticket.py#L32):
  * Primary keys: 36-character standard UUID (`id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))`).
  * Tenancy & Creator Scoping: Partitioned by `tenant_id` (`ForeignKey('tenants.id', ondelete='CASCADE')`) and `created_by_user_id` (`ForeignKey('users.id', ondelete='CASCADE')`).
  * Idempotency & Triage: Unique constraint on `('tenant_id', 'idempotency_key')`, triage priority (`normal`, `high`, `urgent`), and compound index on `('tenant_id', 'status')`.
  * External CCC Thread Reference: `codex_thread_id` (String(64)) reference to external Codex thread without hard cross-database foreign key.
  * Child Tables: `support_ticket_messages` (with sender type and tenant/internal visibility) and `support_ticket_audit_events` (immutable lifecycle audit logging), both featuring cascading deletion from `support_tickets`.

---

## 3. Setup, Configuration & Dependencies

- **SQLAlchemy 2.0**: Declarative ORM base defined in [`app/db/database.py`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L45).
- **pgvector**: `from pgvector.sqlalchemy import Vector` provides vector column type binding for PostgreSQL.
- **Alembic Migrations**: Linear version history rooted through `j1k2m3n4p5q6`, `k2m3n4p5q6r7`, `m3n4p5q6r7s8` to head `a2b3c4d5e6f8` (`a2b3c4d5e6f8_wp0_platform_ownership_and_tenant_lifecycle.py`).
- **Metadata Discovery**: Importing `app.models` in [`app/models/__init__.py`](file:///f:/Projects/fastapi_bookings/app/models/__init__.py#L1) guarantees that all models register onto `Base.metadata`.

---

## 4. Core Workflows & Contracts

### 4.1 Tenancy & Relationship Topology
- Every model referencing a tenant has an explicit `tenant_id` foreign key:
  ```python
  tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
  ```
- Cross-tenant relationships between locations, providers, and services are rejected by application-level validation and composite constraints.

### 4.2 In-Call / Out-Call Domain Schema
- **Tenant**: `allow_in_call` (bool), `allow_out_call` (bool), `travel_charge_origin` (`ALWAYS_FROM_BASE` | `ACTUAL_ORIGIN`).
- **Provider**: `allow_in_call`, `allow_out_call`, `in_call_address`, `out_call_radius_km`, `base_outcall_surcharge`, `per_km_fee`, `travel_fee_mode`, `fixed_travel_fee`, `travel_distance_tiers`, `turnaround_buffer_mins`.
- **Service**: `allow_in_call`, `allow_out_call`, `outcall_price`, `outcall_buffer_before`, `outcall_buffer_after`.
- **Booking**: `service_mode` (`in_call` | `out_call`), travel snapshot fields (`client_suburb`, `client_postcode`, `service_address`, `chargeable_travel_distance_km`, `chargeable_travel_fee`).

---

## 5. Data Safety & Isolation

1. **Mandatory Multi-Tenant Partitioning**: All queries, mutations, jobs, proposals, and events must explicitly filter on `tenant_id`.
2. **Pessimistic & Atomic Double-Booking Prevention**: Discrete 15-minute slot allocations (`booking_slot_allocations`) enforce atomic unique constraints per provider and timestamp.
3. **Tenant-Scoped Booking Idempotency**: `bookings` enforces `UniqueConstraint('tenant_id', 'idempotency_key', name='uq_tenant_booking_idempotency')`.
4. **GDPR Consent Partitioning**: `gdpr_consents` is explicitly partitioned by `tenant_id` (`ForeignKey('tenants.id', ondelete='CASCADE')`).
5. **Bootcamp Settings Scoping**: `sms_bootcamp_settings` enforces `UniqueConstraint('tenant_id', 'provider_id', name='uq_sms_bootcamp_settings_tenant_provider')`.
6. **Bootcamp Message Status Invariant**: `sms_bootcamp_messages.status` enforces `nullable=False`, `default="pending"`, and `server_default="pending"`, ensuring structural integrity across simulations and migrations.
7. **Cryptographic Token Cipher Isolation (IDOR-08)**: `SmsChatwootBinding` and `SmsAccount` derive Fernet cryptographic ciphers strictly from `settings.SECRET_KEY` (never from `PUBLIC_API_KEY`), ensuring sensitive carrier credentials and Chatwoot access tokens cannot be decrypted using public widget credentials.
8. **Support Ticket Idempotency & Creator Scoping**: `support_tickets` enforces `UniqueConstraint('tenant_id', 'idempotency_key', name='uq_support_tickets_tenant_idempotency')` and indexes `('tenant_id', 'status')`. All ticket audit records and messages are cascade-deleted when the parent ticket is purged.
9. **Media Asset Partitioning & Context Isolation**: `media_items` strictly partitions by `tenant_id` (`ForeignKey('tenants.id', ondelete='CASCADE')`). Physical storage paths are scoped to `tenant_{tenant_id}`. Ingestion into Business Assistant context (`MediaService.get_assistant_media_context`) strictly filters on `is_public_website_eligible=True` and completely strips the confidential `notes` field to prevent sensitive clinical or staff notes from leaking into AI or public surfaces.
10. **Platform Ownership, Tenant Suspension & Cryptographic Invitations (WP0)**: `users.is_platform_owner` and `users.is_superuser` decouple global control-plane rights from tenant `role='owner'`. `users.tenant_id` is nullable for cross-tenant operators. `tenants.status` (`active` | `suspended`), `tenants.suspended_at`, and `tenants.suspension_reason` enforce absolute data-plane suspension containment. Single-use `tenant_invitations` enforce token uniqueness, expiration (7-day lifecycle), and explicit email-matching onboarding.

---

## 6. Known Issues, Edge Cases & Outstanding Work

1. **Domain Model Schema Reconciliation (Work Package 5 Completed)**:
   - Previously unmigrated models (`TenantWebsite` in `tenant_websites`, `ClientDispute` in `client_disputes`, `SmsQuickTool` in `sms_quick_tools`, and `GdprConsent` in `gdpr_consents`) are now fully reconciled into the linear Alembic ledger via migration `m3n4p5q6r7s8_reconcile_missing_domain_tables.py`.
   - The migration uses idempotent `inspect(op.get_bind()).get_table_names()` guards ensuring clean execution on fresh databases as well as databases bootstrapped with `create_all()`.
   - `SmsBootcampMessage.status` is migrated via linear Alembic migration `k2m3n4p5q6r7`.
2. **Support Ticket Persistence Infrastructure**:
   - Migration `10251fbf7103_create_support_ticket_tables.py` establishes real database tables for `support_tickets`, `support_ticket_messages`, and `support_ticket_audit_events`.
   - 36-char UUID primary keys are generated client-side by default with PostgreSQL string persistence.
3. **pgvector HNSW Vector Indexing**:
   - `CuratedMemory.embedding` is defined as `Column(Vector(1536), nullable=True)`.
   - Migration `j1k2m3n4p5q6` adds the PostgreSQL HNSW index `ix_curated_memories_embedding_hnsw` on `curated_memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`. Full sequential scans are eliminated for vector similarity queries on PostgreSQL.
4. **SQLite Dialect Incompatibilities**:
   - SQLite does not support `Vector(1536)` vector arithmetic or distance operators (`<=>`, `<->`). When running under SQLite (unit testing), cosine distance is simulated in Python.
   - Partial index definitions diverge between dialects (`sqlite_where` vs `postgresql_where`) in [`app/models/booking.py`](file:///f:/Projects/fastapi_bookings/app/models/booking.py#L34).

---

## 7. Verification & Testing Commands

```powershell
# Verify Python syntax and compilation of all model files
.\.venv\Scripts\python.exe -m py_compile app/models/*.py

# Verify single linear Alembic head
python -m alembic heads

# Verify schema and row parity between primary and test databases
.\.venv\Scripts\python.exe scripts/verify_db_parity.py

# Run media backend tests
.\.venv\Scripts\python.exe -m pytest tests/test_media_backend.py -v

# Run support ticket models verification suite
.\.venv\Scripts\python.exe -m pytest tests/test_support_ticket_models.py -v

# Run model constraint and vector audit test suite
.\.venv\Scripts\python.exe -m pytest tests/test_track1_vector_audit.py tests/test_concurrency.py -v

# Run SMS bootcamp tests
python -m pytest tests/test_sms_bootcamp.py -v
```

## 8. Chatwoot ⇄ FastAPI Booking Engine Synchronization (WP1)
- **Client**: Added \chatwoot_contact_id\ (unique) for routing ingress messages to specific clients. Added explicitly named geo/address fields: \street_address\, \suburb\, \latitude\, \longitude\.
- **Provider**: Added \chatwoot_inbox_id\ (unique) and \system_persona\ & \max_char_limit\ to support direct ingress routing and agent profiling.
- **ProviderKnowledge**: New schema representing facts about a provider (identified via \	enant_id\ and \act_key\). Includes \idx_active_knowledge\ to allow fast filtering of active facts (\superseded_at IS NULL\).

