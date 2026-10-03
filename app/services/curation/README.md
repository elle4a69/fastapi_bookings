# Knowledge Curation

## Purpose & Scope

`app/services/curation/` governs reusable tenant knowledge for the FastAPI
Bookings responder. It owns privacy scrubbing, durable-versus-dynamic
classification, proposal generation, operator review and safe retrieval.

It does not own live availability, prices, dates/times, booking state, links,
customer data or payment details. Those facts must come from the authoritative
FastAPI Bookings domain at response time. Assistant UI is not a dependency.

## Architecture & Key Files

- `knowledge_policy.py`: deterministic dynamic-fact rejection, authority
  ranking and effective-date/conflict policy.
- `memory_curator.py`: proposal-first transcript curation, issue detection,
  trusted-ingestion gate and accept/reject/dismiss/resolve controls.
- `retrieval.py`: tenant/provider-scoped hybrid lexical/vector ranking after
  hard governance filters.
- `pii_scrubber.py`: local PII redaction before candidate retention; supports
  `preserve_names` to protect authorized business and practitioner names from false-positive scrubbing.
- `app/models/curated_memory.py`: accepted `CuratedMemory` records and isolated
  `KnowledgeProposal` review queue.

Only `CuratedMemory` rows may be responder ground truth. A
`KnowledgeProposal` is evidence for an operator decision and is never
retrievable as factual authority.

## Setup, Configuration & Dependencies

The service uses SQLAlchemy asynchronous sessions and `pgvector`-compatible
embeddings. The embedding pipeline generates 1536-dimensional semantic vectors
in the shared latent space (`OPENAI_EMBEDDING_MODEL`, defaulting to
`text-embedding-3-small`) after local PII scrubbing. For test and offline
environments without network connectivity or API credentials, it gracefully
falls back to deterministic unit vectors.

PostgreSQL stores 1536-dimensional vectors using the native `vector` extension
indexed via an approximate nearest neighbor HNSW cosine distance index
(`ix_curated_memories_embedding_hnsw`, `m = 16, ef_construction = 64`) created in
migration `j1k2m3n4p5q6`. SQLite test runners execute hybrid ranking with in-memory
fallback.

## Core Workflows & Contracts

### Conversation curation

1. Extract adjacent customer/assistant Q&A candidates.
2. Scrub PII locally.
3. Classify dynamic facts with deterministic rules.
4. Reject dynamic candidates without retaining their raw query/answer.
5. Create pending add/duplicate/conflict/gap proposals for safe candidates.
6. Never mutate durable knowledge from a conversation.

### Operator review

`review_proposal()` requires an owner/admin role and a tenant-scoped proposal.
It supports accept, reject, dismiss and resolve. Conflict and supersession
acceptance requires an explicit resolution flag. Accepted replacements retain
the previous record as `superseded`; they are not deleted.

### Curator autonomy

`CuratorPolicy` defaults to `proposal_only`. Non-destructive housekeeping and
trusted ingestion are separate opt-ins. Direct trusted ingestion additionally
requires owner/admin role, a confidence threshold of at least 0.90, a durable
candidate and no conflict/replacement candidate.

### Retrieval

`retrieve_durable_knowledge()` applies tenant, provider, active status,
approved authority, confidence, effective date, knowledge kind and conflict
filters before ranking. When running against PostgreSQL with pre-computed query
embeddings, candidate ordering is executed directly in PostgreSQL via native
pgvector cosine distance (`CuratedMemory.embedding.cosine_distance(query_embedding).asc()`)
utilizing the HNSW index. On SQLite or when no embedding is supplied, it falls
back seamlessly to Python-level cosine distance and lexical token matching.
Retrieval emits structural decision evidence only; it does not log the query or answer.

## Data Safety & Isolation

- Every query and mutation includes `tenant_id`; provider-scoped retrieval may
  also use tenant-wide records but never another provider's records.
- Pending/rejected proposals are not responder knowledge.
- Dynamic facts are fail-closed to live lookup or human review.
- Audit metadata is allowlisted and excludes message text, prompts, customer
  identity and knowledge content.
- Supersession is durable and reviewable; destructive auto-delete is forbidden.
- Unknown authority values, active conflicts, future/expired records and
  quarantined records are excluded from retrieval.

## Known Issues, Edge Cases & Outstanding Work

- Alembic migration `j1k2m3n4p5q6_add_pgvector_extension_and_hnsw_index.py` creates
  the PostgreSQL `vector` extension and the HNSW cosine index `ix_curated_memories_embedding_hnsw`.
- Mount owner/admin curator HTTP endpoints and build the admin workspace in a
  separate task; shared router/main files are intentionally not changed here.
- Replace the existing direct `answer-info-request` persistence path in
  `sms_conversations.py` with the governed proposal/review service.
- Route the production prompt assembler through `retrieve_durable_knowledge()`;
  its current legacy retrieval path does not enforce these governance fields.
- Calibrate deterministic dynamic-fact rules with labelled synthetic data;
  false positives must remain reviewable rather than bypassed.

## Verification & Testing Commands

```powershell
.\.venv\Scripts\python.exe -m py_compile app/models/curated_memory.py app/schemas/curated_memory.py app/services/curation/knowledge_policy.py app/services/curation/retrieval.py app/services/curation/memory_curator.py
python -m pytest tests/test_knowledge_phase7_phase8_retrieval.py tests/test_knowledge_curator_api.py -v
```
