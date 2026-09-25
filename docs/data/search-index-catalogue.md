# Search & Index Catalogue: FastAPI Bookings

Generated: 2026-09-25  
Repository: `f:\Projects\fastapi_bookings`  
Database Engine: PostgreSQL 16 (`pgvector 0.8.4`) / SQLite Dialect Compatible  

---

## 1. SQL Indexes (B-Tree, Partial, Composite)

### 1.1 Temporal & Knowledge Scope
- **`ix_curated_memory_retrieval_scope`**:
  * **Table:** `curated_memories`
  * **Columns:** `(tenant_id, provider_id, status, effective_from, effective_until)`
  * **Implementation:** Composite B-tree index supporting temporal knowledge validity lookups.
  * **Scalability:** $O(\log N)$ retrieval; essential for filtering active durable memories.
  * **Production Usage:** Active in `CuratedMemory` queries.

### 1.2 Slot Allocation & Concurrency
- **`uq_active_bookings`**:
  * **Table:** `bookings`
  * **Columns:** `(provider_id, start_time)`
  * **Implementation:** Partial unique index where `status != 'CANCELLED'`.
  * **Scalability:** Prevents double-booking at the database engine level with zero table locking.
  * **Production Usage:** Active.
- **`ix_slot_alloc_tenant_prov_start`**:
  * **Table:** `booking_slot_allocations`
  * **Columns:** `(tenant_id, provider_id, slot_start)`
  * **Implementation:** Composite unique index guaranteeing atomic first-submit-wins slot allocation.
  * **Production Usage:** Active.

### 1.3 Transactional Outbox Queues
- **`ix_outbox_events_dispatch_due` & `ix_outbox_events_expired_lease`**:
  * **Table:** `outbox_events`
  * **Columns:** `(next_attempt_at, created_at, id)` where `status IN ('PENDING', 'RETRY')` and `(lease_expires_at, id)` where `status = 'PROCESSING'`.
  * **Implementation:** High-performance partial indexes for transactional outbox queue workers.
  * **Scalability:** Enables high-frequency polling with `FOR UPDATE SKIP LOCKED`.
  * **Production Usage:** Active in generic outbox worker.

### 1.4 Learning Events
- **`ix_learning_events_tenant_status` & `ix_learning_events_tenant_source_type`**:
  * **Table:** `learning_events`
  * **Columns:** `(tenant_id, status, created_at)` and `(tenant_id, source, event_type)`.
  * **Implementation:** Composite indexes for batch ingestion and curator processing.
  * **Production Usage:** Active in learning event queue lookups.

---

## 2. LIKE / ILIKE Text Searches

### 2.1 Conversations & Client Search
- **Endpoint:** `app/api/routers/sms_conversations.py` (Lines 108–113)
- **Table / Columns:** `sms_conversations.customer_address ILIKE :term` OR `clients.name ILIKE :term`
- **Implementation:** Parameterized `ILIKE %term%`.
- **Scalability:** Linear scan $O(N)$ across tenant rows. Adequate for operational loads (< 50,000 conversations). Recommend `pg_trgm` GIN index if conversation histories exceed 100k rows.
- **Production Usage:** Active in SMS operator conversation filter.

### 2.2 Discovery Map Category Search
- **Endpoint:** `app/api/routers/discovery.py` (Line 176)
- **Table / Columns:** `categories.name ILIKE :term`
- **Implementation:** Indexed predicate over category table.
- **Scalability:** Negligible overhead (< 1ms).
- **Production Usage:** Active.

---

## 3. Phone Lookup (E.164 Inbound Routing)

- **Endpoint:** `app/api/routers/sms_conversations.py` & `app/services/sms/inbound_service.py`
- **Table / Columns:** `clients.phone == sender` & `sms_conversations.customer_address == sender`
- **Index Backing:** `ix_clients_phone` and `uq_sms_account_customer(sms_account_id, customer_address)`.
- **Scalability:** Sub-millisecond indexed hash/B-Tree lookup.
- **Production Usage:** Active on inbound SMS webhooks.

---

## 4. Vector Column & Cosine Similarity (`pgvector`)

- **Table:** `curated_memories`
- **Column:** `embedding Vector(1536)`
- **Current Status (Spec 83):** Retained for schema migration safety, zero-downtime rollback capability, and backward compatibility.
- **Implementation:** `CuratedMemory.embedding.cosine_distance(query_vector)` ordered ascending, limited to top $k=3$.
- **Index Support:** Currently sequential distance scans when invoked.
- **Fallback:** Falls back to verified confidence and recency sorting when pgvector extension is absent (e.g. SQLite tests).
- **Production Usage:** Live learned-context retrieval has cut over to Graphiti and `KnowledgeGateway` (Phase 11 & 13). Direct pgvector similarity is retired from live SMS generation, preserved exclusively for legacy simulation and safety fallback.

---

## 5. Python `difflib.SequenceMatcher`

- **Draft Difference & Word Attribution:**
  * **Files:** `app/models/learning_event.py` (Lines 29–57) & `app/api/routers/sms_conversations.py`
  * **Implementation:** Word-level sequence matching returning ratio, added words, and removed words.
- **Lexical Deduplication:**
  * **File:** `app/services/sms/curator_service.py` (Lines 180–185)
  * `difflib.SequenceMatcher(None, cand_norm, norm_q).ratio() >= 0.85`
- **Scalability:** In-memory execution over candidate strings; negligible CPU overhead (< 0.1ms per event).
- **Production Usage:** Active on draft reviews and autonomous curation.

---

## 6. Manual Keyword & Regex Matching

- **Safety Boundaries & Prohibited Innuendo:**
  * **File:** `app/engine/dialogue_graph.py` (Lines 35–52)
  * **Implementation:** `PROHIBITED_SEXUAL_PATTERNS` regex compiled with `re.IGNORECASE`.
- **Human Escalation Patterns:**
  * **File:** `app/engine/dialogue_graph.py` (Lines 55–68)
  * **Implementation:** `HUMAN_HANDOFF_PATTERNS` compiled regex.
- **Curator Behavioural Classification:**
  * **File:** `app/services/sms/curator_service.py` (Lines 37–77)
  * **Implementation:** `BEHAVIOURAL_KEYWORDS` set and `AVAILABILITY_PATTERNS` regex for deterministic safety enforcement.

---

## 7. Client Lookup & Relationship Resolver

- **Files:** `app/services/booking_relationship_resolver.py` & `app/api/routers/relationship_management.py`
- **Tables:** `clients`, `bookings`, `providers`
- **Implementation:** Scoped retrieval ensuring strict tenant boundary isolation across `Client`, `Booking`, and `Provider`.
- **Production Usage:** Active in staff and customer portals.

---

## 8. Graphiti Learned-Context Knowledge Graph & Search (Specs 26, 46, 54, 65, 85)

- **Engine:** Neo4j Community / Graphiti Knowledge Graph
- **Scope & Group Partitioning:**
  * Graph groups partitioned strictly by multi-tenant and provider boundaries:
    - Provider-specific facts: `tenant:{id}:provider:{id}`
    - Tenant-shared facts: `tenant:{id}:shared`
  * Providers in the same tenant query both `tenant:{id}:provider:{id}` and `tenant:{id}:shared`.
  * Provider B cannot retrieve private facts from Provider A's graph group.
- **Ontology & Edge Schema:**
  * **Entity Concepts:** `BusinessPolicy`, `ServiceOffering`, `Preference`, `BoundaryConstraint`, `ProviderGuidance`, `CommunicationStyle`
  * **Edge Relationships:** `GOVERNS`, `OFFERS`, `PREFERS`, `RESTRICTS`, `APPLIES_TO`, `EXEMPLIFIES`, `SUPERSEDES`
- **Retrieval Architecture:**
  * Multi-channel bounded retrieval:
    - Channel 1 (Facts): Durable facts, business policy, preferences (bounded to $\le 5$ items).
    - Channel 2 (Behaviour): Tone and behavioural guidance rules (bounded to $\le 3$ items).
    - Channel 3 (Examples): Style examples and phrasing models (bounded to $\le 2$ items).
  * Safe Fallback: Seamless fallback to PostgreSQL `CuratedMemory` when Neo4j is offline or unreachable.

---

## 9. Redis Retrieval Cache & Dual Epoch Invalidation (Specs 49, 86)

- **Cache Key Schema:**
  `fb:tenant:{tenant_id}:provider:{provider_id}:knowledge:{tenant_epoch}:{provider_epoch}:{query_hash}`
- **TTL:** 300 seconds (5 minutes).
- **Dual Epoch Invalidation:**
  * Tenant-level mutations (e.g. shared knowledge backfill/policy changes) increment `fb:tenant:{tenant_id}:epoch`.
  * Provider-level mutations (e.g. provider answers, draft edits, preference supersession) increment `fb:tenant:{tenant_id}:provider:{provider_id}:epoch`.
  * Instantaneous $O(1)$ cache busting across all cached queries for that scope without expensive key pattern scans.
- **Loss Tolerance:**
  * Complete Redis flush or outage automatically falls through to live Graphiti / PostgreSQL retrieval without application degradation.

---

## 10. Legacy Knowledge Retrieval Retirement Status (Phase 11, 12, 13, Spec 27, 46)

- **Legacy Reads (Phase 13):**
  * Raw unbounded loading of `SmsKnowledgeEntry`, `shared_knowledge`, and `provider_knowledge` tables has been discontinued in live message orchestration when `GRAPH_KNOWLEDGE_ENABLED=True`.
  * Live prompt construction is exclusively powered by `knowledge_gateway.retrieve(...)` -> `UnifiedPromptBuilder.with_retrieval_result(...)`.
- **Legacy Writes (Phase 12):**
  * Duplicate writes to `SmsKnowledgeEntry` on staff info request answers and bootcamp responses have been retired.
  * The primary, authoritative write path is `LearningEvent` -> `UnifiedCurator` -> `CuratedMemory` -> `KnowledgeGraphProjection`.
  * Historical `SmsKnowledgeEntry` table and records are preserved intact for immutable audit compliance and backfill provenance.
