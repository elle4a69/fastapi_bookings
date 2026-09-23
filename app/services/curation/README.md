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
- `pii_scrubber.py`: local PII redaction before candidate retention.
- `app/models/curated_memory.py`: accepted `CuratedMemory` records and isolated
  `KnowledgeProposal` review queue.

Only `CuratedMemory` rows may be responder ground truth. A
`KnowledgeProposal` is evidence for an operator decision and is never
retrievable as factual authority.

## Setup, Configuration & Dependencies

The service uses SQLAlchemy asynchronous sessions and `pgvector`-compatible
embeddings. Curator embeddings are deterministic and local so transcript text
is not sent to an external embedding provider. PostgreSQL may store vectors;
SQLite test runs rank them in process.

The production migration is intentionally pending because the current Alembic
head (`e8f9a0b1c2d3`) is unrelated, untracked work. Do not deploy these model
changes until a clean migration is generated from the accepted schema head and
its upgrade/downgrade is verified.

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
filters before ranking. Retrieval emits structural decision evidence only; it
does not log the query or answer.

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

- Generate and verify an Alembic migration after the unrelated current head is
  committed or removed from the migration graph.
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
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge_curator_safety.py tests/test_track4_pii_scrubber.py -q
```
