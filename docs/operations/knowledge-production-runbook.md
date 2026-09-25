# FastAPI Bookings — Knowledge Graph & Subsystem Production Operations Runbook

**Document Revision:** 1.0.0  
**Target Architecture:** FastAPI Bookings Production Topology (PostgreSQL 16 + pgvector, Redis 7, Neo4j 5 Community, FastAPI, Celery/Autonomous Daemons)  
**Specification References:** Sections 10–15, 24–28, 30–37, 39–42  
**Security Classification:** Highly Confidential — Zero credentials, secrets, or PII logged or exposed.

---

## 1. System Architecture & Topology

The FastAPI Bookings production system deploys a decoupled, fault-tolerant topology designed for strict multi-tenant isolation, data integrity, and operational resilience.

### Service Topology (`docker-compose.prod.yml`)
- **`web`**: Multi-worker ASGI application server (`uvicorn app.main:app --workers 4`), hosting REST APIs, public booking widgets, and diagnostics.
- **`curator-worker`**: Autonomous background worker (`python -m app.services.knowledge.curator_worker`) leasing and converting pending `LearningEvents` into approved curated memories.
- **`projection-worker`**: Autonomous background daemon (`python -m app.services.knowledge.projection_worker`) synchronizing curated knowledge memories into the Neo4j Graphiti temporal graph.
- **`postgres`**: Authoritative relational and vector store (`pgvector/pgvector:pg16`). All tenants, providers, bookings, learning events, curated memories, and audit logs originate here.
- **`redis`**: Ephemeral caching and distributed rate limiting (`redis:7-alpine`). Disposable without permanent data loss.
- **`neo4j`**: Ephemeral/reconstructable temporal knowledge graph engine (`neo4j:5-community`).

### Network Isolation (Section 26)
- All database, cache, and graph engine containers (`postgres`, `redis`, `neo4j`) reside exclusively on the private internal Docker bridge network: `fastapi_bookings_internal`.
- **Zero public host port bindings**: Ports 5432, 6379, 7474, and 7687 are never exposed to the public internet or external host interfaces.
- The `web` service binds to `127.0.0.1:8000` to receive requests strictly through the reverse proxy / TLS termination layer.

---

## 2. Service Management & Worker Operations

### Starting Services
```bash
# Start all production services in detached mode
docker compose -f docker-compose.prod.yml up -d

# Verify all containers are healthy
docker compose -f docker-compose.prod.yml ps
```

### Stopping Services & Graceful Shutdown
All daemons implement signal traps (`SIGTERM`, `SIGINT`) allowing in-flight batches to complete before process exit.
```bash
# Graceful stop with 30s timeout for worker shutdown
docker compose -f docker-compose.prod.yml stop -t 30

# Terminate containers
docker compose -f docker-compose.prod.yml down
```

### Restarting Workers Independently
```bash
# Restart Curator worker
docker compose -f docker-compose.prod.yml restart curator-worker

# Restart Projection worker
docker compose -f docker-compose.prod.yml restart projection-worker
```

### Manual Worker Execution (Diagnostics / Recovery)
Workers can be run manually in one-shot or continuous foreground mode:
```bash
# Foreground execution of curator worker
python -m app.services.knowledge.curator_worker

# Foreground execution of projection worker
python -m app.services.knowledge.projection_worker
```

---

## 3. Health Checks & Diagnostics Endpoints (Section 24)

### Granular Readiness Probe: `/api/v1/diagnostics/readiness`
The platform exposes a consolidated, granular health check verifying every backing dependency:
```bash
curl -s http://127.0.0.1:8000/api/v1/diagnostics/readiness
```

**Response Format:**
```json
{
  "status": "healthy",
  "fastapi": "healthy",
  "postgresql": "healthy",
  "redis": "healthy",
  "neo4j": "healthy",
  "projection_worker": "healthy",
  "curator_worker": "healthy"
}
```

- **HTTP 200**: All core systems operational (`status: "healthy"`).
- **HTTP 503**: Primary database unreachable or degraded (`status: "degraded"`).

### Additional Probes
- `/ready`: Lightweight Kubernetes/Docker database connectivity check (`SELECT 1`).
- `/health`: Fast liveness check for reverse proxy health monitoring.
- `/api/admin/diagnostics/telemetry/status`: Observability exporter status check.

---

## 4. PostgreSQL Backup & Restoration Procedures (Sections 11, 12)

PostgreSQL is the single source of truth. Backups must be performed regularly and validated periodically via restore drills.

### Logical Backup Procedure (Section 11)
Execute a consistent logical database backup using `pg_dump`. Credentials are drawn from environment configuration and never passed on command-line arguments.

```bash
# Set timestamp variable
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="backups/fastapi_bookings_backup_${TIMESTAMP}.sql"

# Execute pg_dump from within the isolated database container
docker exec fastapi_bookings_postgres_prod pg_dump -U postgres --clean --if-exists -f /tmp/backup.sql fastapi_bookings

# Copy backup to host repository
docker cp fastapi_bookings_postgres_prod:/tmp/backup.sql "${BACKUP_FILE}"
docker exec fastapi_bookings_postgres_prod rm /tmp/backup.sql

# Log backup metadata (Timestamp, Database, Size, Version)
echo "Backup saved to: ${BACKUP_FILE}"
ls -lh "${BACKUP_FILE}"
```

### Restoration Verification Drill (Section 12)
Restore drills must verify schema alignment and exact row counts without modifying or disturbing the production database:

1. **Create Disposable Verification Database**:
   ```bash
   docker exec fastapi_bookings_postgres_prod psql -U postgres -c "CREATE DATABASE fastapi_bookings_restore_verify;"
   ```

2. **Restore Logical Dump**:
   ```bash
   docker cp "${BACKUP_FILE}" fastapi_bookings_postgres_prod:/tmp/restore.sql
   docker exec fastapi_bookings_postgres_prod psql -U postgres -d fastapi_bookings_restore_verify -f /tmp/restore.sql -q
   docker exec fastapi_bookings_postgres_prod rm /tmp/restore.sql
   ```

3. **Verify Alembic Migration State**:
   ```bash
   docker exec fastapi_bookings_postgres_prod psql -U postgres -d fastapi_bookings_restore_verify -c "SELECT version_num FROM alembic_version;"
   ```
   *Expected Head:* Must match current production revision head (e.g. `b2c3d4e5f6a7`).

4. **Verify Representative Model Row Parity**:
   ```sql
   SELECT 'tenants' AS model, COUNT(*) FROM tenants
   UNION ALL SELECT 'providers', COUNT(*) FROM providers
   UNION ALL SELECT 'clients', COUNT(*) FROM clients
   UNION ALL SELECT 'bookings', COUNT(*) FROM bookings
   UNION ALL SELECT 'conversations', COUNT(*) FROM sms_conversations
   UNION ALL SELECT 'messages', COUNT(*) FROM sms_messages
   UNION ALL SELECT 'learning_events', COUNT(*) FROM learning_events
   UNION ALL SELECT 'curated_memories', COUNT(*) FROM curated_memories
   UNION ALL SELECT 'knowledge_graph_projections', COUNT(*) FROM knowledge_graph_projections
   UNION ALL SELECT 'sms_bootcamp_settings', COUNT(*) FROM sms_bootcamp_settings;
   ```
   *Verification:* Ensure row counts match pre-backup source counts 1:1.

5. **Clean Up Verification Database**:
   ```bash
   docker exec fastapi_bookings_postgres_prod psql -U postgres -c "DROP DATABASE fastapi_bookings_restore_verify;"
   ```

---

## 5. Disposable Infrastructure Recovery

### Redis Cache Recovery (Section 14)
Redis is strictly an ephemeral acceleration and distributed synchronization layer:
- **Stored Data**: Retrieval cache keys (`fb:knowledge:retrieval:*`), temporary session locks, rate limit counters.
- **Recovery Strategy**:
  1. Restart or wipe Redis instance at will (`docker compose -f docker-compose.prod.yml restart redis`).
  2. Cache misses automatically trigger authoritative read-through to PostgreSQL and Neo4j.
  3. No operational data loss occurs on complete Redis failure or cache flushing (`redis-cli flushall`).

### Neo4j Graph Recovery & Reconstruction (Section 13)
Neo4j Graphiti is a projection of curated knowledge. PostgreSQL remains the absolute authority:
- **Stored Data**: Temporal knowledge subgraphs partitioned by `tenant:{tenant_id}:shared` and `tenant:{tenant_id}:provider:{provider_id}`.
- **Recovery Strategy**:
  1. If Neo4j volume is corrupted or lost, spin up a clean Neo4j instance.
  2. The application's fallback retrieval immediately falls back to PostgreSQL relational/vector knowledge retrieval (`GRAPH_KNOWLEDGE_ENABLED=false` or dynamic fallback).
  3. Execute full deterministic graph reconstruction using the Rebuild Tool.

---

## 6. Graph Rebuild & Backfill Procedure (Sections 10, 56–61)

The CLI tool `app.tools.rebuild_knowledge_graph` rebuilds graph projections from authoritative PostgreSQL records with strict tenant isolation and zero credential leakage.

### Dry-Run Audit
Always preview candidate projections before running live persistence:
```bash
# System-wide dry run audit
python -m app.tools.rebuild_knowledge_graph --dry-run

# Scoped dry run for specific tenant and provider
python -m app.tools.rebuild_knowledge_graph --tenant-id 1 --provider-id 10 --dry-run
```

### Full Rebuild Execution
```bash
# Rebuild all eligible approved memories into projections
python -m app.tools.rebuild_knowledge_graph

# Rebuild single provider's knowledge partition
python -m app.tools.rebuild_knowledge_graph --tenant-id 1 --provider-id 10
```

### Parity Verification
Verify that all approved memories in PostgreSQL are projected:
```bash
python -m app.tools.rebuild_knowledge_graph --verify
```

---

## 7. Worker Crash Recovery & Stale Lease Reclamation (Section 15)

The autonomous workers (`curator-worker` and `projection-worker`) use lease-based concurrency locks to guarantee exactly-once execution across horizontal worker instances.

### How Worker Leasing Works
1. When a worker claims an item (`LearningEvent` or `KnowledgeGraphProjection`), it atomically assigns:
   - `lease_owner = <worker_uuid>`
   - `lease_expires_at = now() + interval (2 minutes)`
   - `status = "processing"`
2. If the worker process crashes, is killed, or suffers an OOM event mid-batch:
   - The lease naturally expires after 120 seconds.
   - On the next poll cycle, any active worker queries `WHERE status = 'processing' AND lease_expires_at < now()`.
   - The stale item is claimed by a healthy worker, increments `attempt_count`, and continues processing.
3. **No manual intervention is required** for transient crashes.

---

## 8. Dead-Letter Inspection & Replay Procedure (Section 39)

When an item fails processing across 5 consecutive attempts (`attempt_count >= max_retries`), it transitions to `dead_letter` (projections) or `failed` (learning events).

### Inspecting Dead-Letter Items
Inspect failed projections directly in PostgreSQL without exposing PII:
```sql
SELECT id, tenant_id, entity_id, attempt_count, last_error, updated_at
FROM knowledge_graph_projections
WHERE status = 'dead_letter'
ORDER BY updated_at DESC
LIMIT 50;
```

### Root Cause Analysis Categories
- **Neo4j Connectivity/Auth Timeout**: Temporary cluster unreachability.
- **Malformed Entity Payload**: Upstream serialization anomaly.
- **Ontological Validation Rejection**: Unrecognized relationship predicate.

### Replay Procedure
Once the root cause is resolved (e.g. network restored or schema adjusted), reset dead-letter items to `pending`:
```sql
-- Replay dead-letter projections for a specific tenant
UPDATE knowledge_graph_projections
SET status = 'pending',
    attempt_count = 0,
    last_error = NULL,
    lease_owner = NULL,
    lease_expires_at = NULL,
    next_retry_at = NOW()
WHERE status = 'dead_letter' AND tenant_id = 1;
```
The `projection-worker` will immediately claim and re-process the batch.

---

## 9. Rollback Conditions & Immediate Actions (Sections 32, 33)

### Rollback Trigger Thresholds
Initiate emergency fallback immediately if any of the following occur during deployment or canary rollout:
1. Retrieval error rate > 1.0% over a 5-minute rolling window.
2. End-to-end knowledge retrieval p95 latency exceeds 200ms.
3. Cross-tenant or cross-provider data leakage detected.
4. Neo4j write queue backlog exceeds 500 unprojected events.

### Rollback Action: Zero-DDL Feature Flag Fallback (Section 33)
**NEVER run destructive database rollbacks** (`alembic downgrade`) in production. Schema additions are strictly backward-compatible.

To instantly disable graph knowledge retrieval and revert 100% of traffic to the proven PostgreSQL relational/vector fallback:
```bash
# In production environment (.env or orchestrator config)
GRAPH_KNOWLEDGE_ENABLED=false
GRAPH_SHADOW_READ=false
GRAPH_SHADOW_WRITE=false
```
Reload or restart web services:
```bash
docker compose -f docker-compose.prod.yml restart web
```
- **Instant Effect**: All customer queries immediately bypass Neo4j and resolve from standard PostgreSQL tables.
- **Zero Downtime**: Bookings, SMS workflows, and customer appointments continue without interruption.

---

## 10. Observability, Monitoring & Alerts (Sections 34, 35)

### OpenTelemetry / SigNoz Metrics & Traces
The application instruments all critical paths with structured telemetry:
- `knowledge.curator.process_batch`: Number of events processed, duration, error counts.
- `knowledge.projection.process_batch`: Number of projections synced, duration.
- `knowledge.retrieval`: Total retrieval duration, cache hit ratio, fallback events.

### Recommended Alert Conditions
| Alert Name | Condition | Severity | Notification Channel | Remediation |
|------------|-----------|----------|----------------------|-------------|
| **PostgreSQL Unreachable** | `readiness.postgresql == unhealthy` | P1 - CRITICAL | PagerDuty / Ops Call | Check container health, disk space, and connection pool |
| **Worker Crash Loop** | Worker restarts > 3 in 10 mins | P1 - CRITICAL | Slack / Ops On-Call | Inspect worker container logs for unhandled exceptions |
| **Dead-Letter Spurt** | > 10 dead-letter projections / hour | P2 - HIGH | Slack #alerts | Run dead-letter inspection query, inspect `last_error` |
| **Neo4j Degradation** | `readiness.neo4j == unhealthy` | P2 - HIGH | Slack #alerts | Verify Neo4j memory limits, check fallback activation |
| **Cache Miss Anomaly** | Cache hit ratio < 20% over 1 hour | P3 - MEDIUM | Slack #ops | Check Redis connectivity and key TTL configurations |

---

## 11. Common Failure Symptoms & Remediation Guide

### 1. Connection Pool Exhaustion (`QueuePool limit of size 10 overflow 20 reached`)
- **Symptom**: HTTP 500s or hanging API requests.
- **Cause**: Slow unindexed queries or worker sessions not closing properly.
- **Action**: Verify `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` settings. Ensure all workers use context managers (`with SessionLocal() as db:`).

### 2. Worker Starvation / Processing Stalled
- **Symptom**: `LearningEvent` queue growing, status remains `pending`.
- **Cause**: Worker daemon died without restarting, or all workers holding expired leases.
- **Action**: Check `docker compose -f docker-compose.prod.yml ps`. Restart workers if down.

### 3. Neo4j Authentication or Out-of-Memory Failure
- **Symptom**: `Neo4j connectivity check failed: AuthError` or `ServiceUnavailable`.
- **Cause**: Invalid password configured in `NEO4J_PASSWORD` or JVM heap exhausted.
- **Action**: Run `python scripts/verify_production_secrets.py`. Inspect Neo4j heap configurations in `docker-compose.prod.yml`.

---

## 12. Pre-Deployment Checklist (Section 42)

Before any release or cutover to production, the Release Engineer must sign off on the following:

- [ ] **1. Secrets Validation**:
  ```bash
  python scripts/verify_production_secrets.py --env production
  ```
  *Requirement:* Exit code 0, all secrets marked `SECURE`, zero `MISSING` or `INSECURE`.
- [ ] **2. Test Suite & Release Gates**:
  ```bash
  python scripts/verify_all_release_gates.py
  ```
  *Requirement:* All 8 test and verification gates passing.
- [ ] **3. Fresh Database Backup**:
  Logical backup taken and verified per Section 4 above.
- [ ] **4. Alembic Migration Alignment**:
  ```bash
  python -m alembic current
  ```
  *Requirement:* Current revision matches migration head.
- [ ] **5. Readiness Endpoint Verified**:
  ```bash
  curl -s http://127.0.0.1:8000/api/v1/diagnostics/readiness
  ```
  *Requirement:* Returns `200 OK` with `"status": "healthy"`.

---

## 13. Phased Canary Rollout Plan (Sections 30, 31)

To protect live customer bookings and maintain uninterrupted availability, rollout follows 5 controlled canary stages:

### Stage 1: Internal Synthetic Test Provider
- **Scope**: Internal synthetic provider (`provider_id=999`).
- **Configuration**:
  ```bash
  GRAPH_KNOWLEDGE_ENABLED=true
  GRAPH_SHADOW_WRITE=true
  GRAPH_SHADOW_READ=true
  GRAPH_CANARY_PROVIDER_IDS=[999]
  ```
- **Soak Time**: 2 hours.
- **Exit Criteria**: 100% successful synthetic bookings, zero dead-letter events.

### Stage 2: Single Live Friendly Provider
- **Scope**: 1 opted-in low-volume provider.
- **Configuration**:
  ```bash
  GRAPH_CANARY_PROVIDER_IDS=[999, 101]
  ```
- **Soak Time**: 24 hours.
- **Exit Criteria**: Zero customer complaints, zero AI hallucinations, p95 latency < 150ms.

### Stage 3: Small Provider Cohort
- **Scope**: 3–5 representative providers across distinct service categories.
- **Configuration**:
  ```bash
  GRAPH_CANARY_PROVIDER_IDS=[999, 101, 102, 103, 104]
  ```
- **Soak Time**: 48 hours.
- **Exit Criteria**: Retrieval error rate < 0.1%, consistent multi-tenant boundary checks.

### Stage 4: Single Complete Tenant
- **Scope**: Full tenant (`tenant_id=1`), encompassing all associated providers.
- **Configuration**:
  ```bash
  GRAPH_CANARY_TENANT_IDS=[1]
  ```
- **Soak Time**: 48 hours.
- **Exit Criteria**: Full catalog retrieval accuracy, zero cross-tenant contamination in shadow comparison logs.

### Stage 5: General Availability (Full Rollout)
- **Scope**: All tenants and providers.
- **Configuration**:
  ```bash
  GRAPH_KNOWLEDGE_ENABLED=true
  GRAPH_SHADOW_WRITE=true
  GRAPH_SHADOW_READ=false
  GRAPH_CANARY_PROVIDER_IDS=[]
  GRAPH_CANARY_TENANT_IDS=[]
  ```
- **Post-Rollout Monitoring**: Continuous 72-hour automated telemetry monitoring.
