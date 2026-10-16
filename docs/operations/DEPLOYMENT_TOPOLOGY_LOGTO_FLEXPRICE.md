# Production Deployment Topology & Capacity Planning: Logto & Flexprice

This document defines the multi-tier production deployment topology, network segmentation, security boundaries, and capacity planning matrices for deploying Logto (Identity & Access Management) and Flexprice (Usage-Based Billing & Metering Engine) alongside the FastAPI Bookings platform.

---

## 1. High-Level Architecture & Multi-Tier Topology

The platform architecture follows an isolated multi-tier topology within a dedicated Virtual Private Cloud (VPC), segregated into public ingress, internal application runtime, and restricted data storage zones.

```
                             [ Internet / Public Clients ]
                                          |
                      +-------------------+-------------------+
                      |      Cloudflare WAF / DDoS Shield     |
                      +-------------------+-------------------+
                                          | TLS 1.3 Termination
                      +-------------------+-------------------+
                      |     External Application Load Balancer|
                      +-------------------+-------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
        v :443                            v :443                            v :443
+-------------------+             +-------------------+             +-------------------+
|  FastAPI Bookings |             |    Logto Core     |             |  Flexprice Server |
|   (Python/Uvicorn)|             |   (Node.js / M2M) |             |     (Go Engine)   |
|   Private Subnet  |             |   Private Subnet  |             |   Private Subnet  |
+---------+---------+             +---------+---------+             +---------+---------+
          |                                 |                                 |
          |  Internal VPC Traffic           |                                 |
          |  (mTLS / Shared VPC Service)    |                                 |
          +-------------------------------->+                                 |
          |  (Signed Internal Webhooks)     |                                 |
          +------------------------------------------------------------------>+
          |                                 |                                 |
          v                                 v                                 v
+-------------------+             +-------------------+             +-------------------+
| PostgreSQL Bookings             |  PostgreSQL Logto |             | PostgreSQL Flexpr.|
| (Patroni HA Cluster)            |  (Dedicated DB)   |             | (Dedicated DB)    |
+-------------------+             +-------------------+             +---------+---------+
          |                                                                   |
          v                                                                   v
+-------------------+                                               +-------------------+
|   Redis (Cache)   |                                               | Kafka / ClickHouse|
| (Sentinel / Valkey)                                               | / Temporal Cluster|
+-------------------+                                               +-------------------+
```

### Subnet Segregation
1. **Public Ingress Tier (Subnet CIDR: `10.0.1.0/24`)**:
   - Cloudflare edge proxies terminate TLS 1.3 and enforce WAF rate limits and DDoS mitigation.
   - External Application Load Balancers (ALBs) route traffic strictly via private IP targets to container workloads.
2. **Application Runtime Tier (Subnet CIDR: `10.0.10.0/22`)**:
   - Container clusters (AWS ECS Fargate / Google Cloud Run / Kubernetes Pods) with no direct public IPs.
   - Egress restricted via NAT Gateways with static egress IPs for external third-party API communication.
3. **Data & Storage Tier (Subnet CIDR: `10.0.20.0/22`)**:
   - Isolated private database subnets with strict security group ingress rules permitting traffic only from specific application container security groups.

---

## 2. Component Specifications

### 2.1 Logto Core (Identity & Access Management)
- **Runtime**: Node.js 20+ LTS container runtime.
- **Role**: OIDC / OAuth 2.0 Provider, Enterprise SSO broker, Organization multi-tenancy, Machine-to-Machine (M2M) token issuance.
- **Ingress Endpoints**:
  - `https://auth.domain.com/oidc`: Public discovery, authorization code flow, JWKS endpoint (`/.well-known/jwks.json`).
  - `https://auth.domain.com/api`: Administrative Management API protected by M2M bearer tokens with RS256/ES384 validation.
- **Dependencies**:
  - PostgreSQL 16+ (Dedicated logical database `logto_db`, separate schema and credentials).

### 2.2 Flexprice Engine (Usage-Based Billing & Metering)
- **Runtime**: Go compiled binary runtime.
- **Role**: Billing accounts, credit grants, invoice generation, subscription life-cycle management, and high-throughput meter ingestion.
- **Ingress Endpoints**:
  - Internal VPC Endpoint (`http://flexprice-internal.vpc:8080/api/v1`): Private REST API for provisioning, metering ingestion, and portal session generation.
  - Outbound Webhooks: Dispatches signed HMAC-SHA256 events to `https://api.domain.com/api/v1/platform-billing/webhooks/flexprice`.
- **Dependencies**:
  - PostgreSQL 16+ (Transactional state, customers, subscriptions, invoices, plans).
  - Redis 7+ (Rate limiting, idempotency locks, temporary meter aggregation).
  - Apache Kafka / Redpanda (Optional at scale: Real-time event streaming buffer for usage events).
  - ClickHouse (Optional at scale: Columnar OLAP engine for high-volume raw usage analytics).
  - Temporal (Workflow orchestration for complex multi-step billing cycles, invoicing, and dunning).

---

## 3. Network Segmentation, Security Boundaries & Mutual Trust

### 3.1 Network Policies & Security Groups
- **FastAPI Bookings SG (`sg-fastapi`)**:
  - Egress:
    - Port `5432` to `sg-postgres-bookings`
    - Port `6379` to `sg-redis`
    - Port `443` to `sg-logto` (Internal M2M)
    - Port `8080` / `443` to `sg-flexprice` (Internal API)
- **Logto SG (`sg-logto`)**:
  - Ingress: Port `3001`/`443` allowed only from ALB and `sg-fastapi`.
  - Egress: Port `5432` allowed only to `sg-postgres-logto`.
- **Flexprice SG (`sg-flexprice`)**:
  - Ingress: Port `8080` allowed only from `sg-fastapi`.
  - Egress:
    - Port `5432` to `sg-postgres-flexprice`
    - Port `6379` to `sg-redis`
    - Port `9092` to `sg-kafka` (if enabled)
    - Port `7233` to `sg-temporal` (if enabled)
    - Port `443` to ALB/FastAPI for webhook delivery.

### 3.2 Mutual Authentication & Webhook Cryptographic Integrity
- **Logto API Ingress**:
  - FastAPI authenticates to Logto Management API using client credentials M2M exchange (`POST /api/oidc/token`).
  - Tokens are cached in-memory with automatic refresh prior to expiration (`settings.LOGTO_M2M_APP_ID`, `settings.LOGTO_M2M_APP_SECRET`).
- **Flexprice Webhook Egress & Ingress**:
  - Every outbound webhook sent by Flexprice includes headers:
    - `X-Flexprice-Signature`: `sha256=<hex_digest>`
    - `X-Flexprice-Timestamp`: Unix timestamp (seconds)
    - `X-Flexprice-Event-Id`: Globally unique UUID
  - FastAPI Bookings verifies the signature using constant-time comparison (`hmac.compare_digest`) against `settings.FLEXPRICE_WEBHOOK_SECRET`.
  - Replay protection: Rejects events with timestamps older than 300 seconds (5 minutes) and enforces unique event deduplication via the `provider_event_inbox` table.

---

## 4. Capacity Planning & Sizing Matrices

The following sizing guidelines provide concrete baseline requirements for small, medium, and large production scale tiers.

| Metric / Dimension | Tier 1: Starter (Up to 100 Tenants / 10k Active Users) | Tier 2: Growth (Up to 1,000 Tenants / 250k Active Users) | Tier 3: Enterprise (10,000+ Tenants / 2M+ Active Users) |
| :--- | :--- | :--- | :--- |
| **FastAPI Bookings App** | 2 x (2 vCPU, 4 GB RAM) | 4 x (4 vCPU, 8 GB RAM) | 8-16 x (8 vCPU, 16 GB RAM) |
| **Logto Core Containers** | 2 x (1 vCPU, 2 GB RAM) | 3 x (2 vCPU, 4 GB RAM) | 6 x (4 vCPU, 8 GB RAM) |
| **Flexprice Core Engine** | 2 x (1 vCPU, 2 GB RAM) | 4 x (2 vCPU, 4 GB RAM) | 8 x (4 vCPU, 8 GB RAM) |
| **PostgreSQL (Bookings)** | 2 vCPU, 8 GB RAM, 100 GB SSD (1,000 IOPS) | 4 vCPU, 16 GB RAM, 500 GB SSD (3,000 IOPS) | 16 vCPU, 64 GB RAM, 2 TB NVMe (10,000+ IOPS) + 2 Read Replicas |
| **PostgreSQL (Logto DB)** | 2 vCPU, 4 GB RAM, 50 GB SSD | 2 vCPU, 8 GB RAM, 100 GB SSD | 4 vCPU, 16 GB RAM, 500 GB SSD (Multi-AZ HA) |
| **PostgreSQL (Flexprice)**| 2 vCPU, 4 GB RAM, 50 GB SSD | 4 vCPU, 16 GB RAM, 250 GB SSD | 8 vCPU, 32 GB RAM, 1 TB SSD (Multi-AZ HA) |
| **Redis Cache / Locks**   | 1 Node (1.5 GB RAM, Cluster Mode disabled) | 3 Nodes Sentinel (6 GB RAM) | Redis Cluster / Valkey (6+ Nodes, 24 GB RAM) |
| **Event Pipeline (Kafka)**| Not required (Direct HTTP batching) | Redpanda / Kafka (3 nodes, 2 vCPU, 4 GB) | Kafka Cluster (3-5 nodes, 4 vCPU, 16 GB, SSD) |
| **Analytics (ClickHouse)**| Not required (Postgres aggregates) | 1 Node (4 vCPU, 16 GB RAM, 500 GB SSD) | 3-Node Cluster (8 vCPU, 32 GB RAM, 2 TB NVMe) |

### Database Connection Pool Allocations
To prevent connection exhaustion across container autoscaling:
- **FastAPI Pool**: `pool_size=20`, `max_overflow=10`, `pool_timeout=30`, `pool_recycle=1800` (per instance).
- **Logto Pool**: `DB_POOL_MIN=2`, `DB_POOL_MAX=20` (per instance).
- **Flexprice Pool**: `max_open_conns=25`, `max_idle_conns=10`, `conn_max_lifetime=15m`.
- **PgBouncer Connection Pooling**: Mandatory at Tier 2 and Tier 3 in transaction pooling mode (`pool_mode = transaction`, `max_client_conn = 5000`, `default_pool_size = 50`).

---

## 5. High Availability, Failover & Disaster Recovery

### Recovery Targets
- **Recovery Point Objective (RPO)**: < 1 minute (Synchronous replication within region; continuous WAL archiving to S3/GCS).
- **Recovery Time Objective (RTO)**: < 5 minutes (Automated Multi-AZ Patroni / Cloud SQL failover).

### Backup Policies
1. **Automated Snapshots**: Daily full volume snapshot retained for 30 days.
2. **Continuous WAL Streaming**: Point-in-Time Recovery (PITR) enabled up to 7 days.
3. **Cross-Region Replication**: Asynchronous read replica in secondary region for disaster failover.

---

## 6. Observability, Telemetry & Release Quality Gates

- **OpenTelemetry & SigNoz**: All FastAPI Bookings, Logto, and Flexprice services export traces and metrics using OTLP gRPC (`4317`) / HTTP (`4318`) to the centralized SigNoz collector.
- **Readiness Probes**:
  - Load balancers poll `/api/platform/health/readiness` every 10 seconds.
  - Fail closed: If any critical dependency (PostgreSQL, Redis, or essential auth/billing API) is unreachable or reports degraded status, the probe fails (HTTP 503), taking the unhealthy node out of rotation without service disruption.
- **Zero Secret Exposure Guarantee**: All health check endpoints must strictly return status enums (`ok`, `degraded`, `down`) and anonymized service tags, never revealing connection strings, passwords, or token fragments.
