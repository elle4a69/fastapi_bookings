# SaaS Control Plane Operational Runbook (WP5)

This runbook documents operational procedures, incident response drills, disaster recovery routines, and lifecycle workflows for operators managing the FastAPI Bookings platform alongside Logto (Identity) and Flexprice (Billing).

---

## 1. Backup & Restore Procedures

### 1.1 Database Scope & Target Tables
The SaaS Control Plane relies on three relational data stores:
1. **FastAPI Bookings Database (`fastapi_bookings`)**:
   - `tenants`: Primary tenant entity and platform lifecycle state (`active`, `suspended`, `deleted`).
   - `users`: User identity records and tenant associations.
   - `billing_accounts`: Linkage between internal tenant ID and external `flexprice_customer_id`.
   - `subscription_projections`: Local cached read-model for fast entitlement checks.
   - `provider_event_inbox`: Idempotent log of incoming billing webhooks.
   - `platform_grants`: Operator overrides and credit grants.
2. **Logto Database (`logto_db`)**:
   - `organizations`, `organization_roles`, `users`, `user_identities`, `applications`.
3. **Flexprice Database (`flexprice_db`)**:
   - `customers`, `subscriptions`, `plans`, `invoices`, `wallets`, `meter_events`.

### 1.2 Automated Point-in-Time & Snapshot Backups
- **Continuous WAL Archiving**: Managed via AWS Aurora / GCP Cloud SQL / pgBackRest to an encrypted cloud object store (`s3://fb-platform-backups/wal/`).
- **Nightly Logical Dump**: Executed daily at 02:00 UTC via scheduled Kubernetes CronJob:
  ```bash
  # FastAPI Bookings SaaS tables export
  pg_dump -h $DB_HOST -U $DB_USER -d fastapi_bookings \
    --format=custom \
    --table=tenants \
    --table=users \
    --table=billing_accounts \
    --table=subscription_projections \
    --table=provider_event_inbox \
    --table=platform_grants \
    --file=/backups/fastapi_bookings_saas_$(date +%Y%m%d_%H%M%S).dump

  # Logto DB export
  pg_dump -h $LOGTO_DB_HOST -U $LOGTO_DB_USER -d logto_db \
    --format=custom \
    --file=/backups/logto_db_$(date +%Y%m%d_%H%M%S).dump

  # Flexprice DB export
  pg_dump -h $FLEXPRICE_DB_HOST -U $FLEXPRICE_DB_USER -d flexprice_db \
    --format=custom \
    --file=/backups/flexprice_db_$(date +%Y%m%d_%H%M%S).dump
  ```

### 1.3 Point-In-Time Restore Procedure
To restore a damaged or inconsistent control plane state:
1. **Isolate Traffic**: Place FastAPI Bookings in maintenance mode by redirecting ingress to an offline static page.
2. **Restore Logical Databases in Sequence**:
   ```bash
   # Restore Logto DB first
   pg_restore -h $LOGTO_DB_HOST -U $LOGTO_DB_USER -d logto_db --clean /backups/logto_db_TARGET.dump

   # Restore Flexprice DB second
   pg_restore -h $FLEXPRICE_DB_HOST -U $FLEXPRICE_DB_USER -d flexprice_db --clean /backups/flexprice_db_TARGET.dump

   # Restore FastAPI Bookings SaaS tables
   pg_restore -h $DB_HOST -U $DB_USER -d fastapi_bookings --clean /backups/fastapi_bookings_saas_TARGET.dump
   ```
3. **Run SaaS Control Plane Reconciliation**:
   ```bash
   python scripts/reconcile_saas_control_plane.py --all-tenants
   ```
4. **Verify Platform Readiness**:
   ```bash
   curl -f http://127.0.0.1:8000/api/platform/health/readiness
   ```
5. **Reopen Traffic**: Drain maintenance routing and restore normal ingress.

---

## 2. Upgrade & Schema Migration Protocol

To guarantee zero downtime and eliminate deployment lockups:
1. **Pre-Upgrade Checklist**:
   - Check that all migrations in `alembic/versions/` are forward and backward compatible (expand-contract pattern).
   - Verify that no column renames or drop column operations are executed in a single release.
   - Run readiness probe check across all pods:
     `GET /api/platform/health/readiness` must return `"status": "ok"`.
2. **Migration Execution**:
   - Run Alembic migration against the target database before initiating the application container rollout:
     ```bash
     alembic upgrade head
     ```
3. **Application Rolling Rollout**:
   - Perform a rolling update (Kubernetes `maxSurge: 25%`, `maxUnavailable: 0`).
   - Pod readiness probe `/health/ready` ensures new containers do not receive user traffic until database connectivity and cache checks pass.
4. **Emergency Rollback**:
   - If error rates increase or `/api/platform/health/readiness` fails:
     ```bash
     kubectl rollout undo deployment/fastapi-bookings
     ```

---

## 3. Provider Outage Drills & Fail-Closed Semantics

### 3.1 Scenario A: Identity Provider (Logto) Unreachable
- **Behavior**:
  - Existing active sessions validated via cached JWKS keys remain functional until JWT expiry (15-60 min).
  - New token issuance or uninvited external logins fail immediately with HTTP 403/503.
  - No fallback allows unverified bearer tokens or spoofed claims.
- **Recovery Drill**:
  1. Verify Logto container status: `docker ps` or `kubectl get pods -l app=logto`.
  2. Inspect Logto connection pool metrics.
  3. Validate JWKS cache status in FastAPI Bookings.

### 3.2 Scenario B: Billing Provider (Flexprice) Unreachable
- **Behavior**:
  - The local `SubscriptionProjection` serves as the authoritative cached read-model for all entitlement and quota checks.
  - Existing paid features continue operating normally; valid subscriptions are **NOT** revoked due to a billing network glitch.
  - Customer billing portal redirect (`POST /api/platform-billing/portal-session`) fails closed with HTTP 503 instead of issuing unsecured URLs.
  - Outgoing metered usage events are buffered locally with an exponential backoff retry.
- **Recovery Drill**:
  1. Check Flexprice container logs and database connectivity.
  2. Once Flexprice is restored, run the reconciliation script to inspect drift:
     ```bash
     python scripts/reconcile_saas_control_plane.py --all-tenants
     ```

### 3.3 Past-Due Subscription & Grace Period Handling
- When a subscription enters `past_due`:
  - An informational banner is returned in `GET /api/platform-billing/subscription/overview` with `past_due_banner: true`.
  - A 7-day grace period is granted to allow customer payment method correction.
  - If payment is not resolved within 7 days, the status transitions to `unpaid` or `canceled`, initiating tenant module lockouts.

---

## 4. Tenant Lifecycle Workflows

### 4.1 Tenant Provisioning
1. Platform Owner issues an invitation:
   `POST /api/platform/invitations`
2. Tenant registers through Logto SSO; Logto organization is idempotently linked to the internal `Tenant` record.
3. Flexprice customer is initialized with external ID `tenant_{id}`.

### 4.2 Tenant Suspension
1. Operator invokes suspension:
   `POST /api/platform/tenants/{tenant_id}/suspend`
2. The `Tenant.status` is set to `"suspended"`.
3. All subsequent authenticated requests for that tenant are immediately rejected with HTTP 403 Forbidden (`TENANT_SUSPENDED`).
4. Active webhook event processing for this tenant is paused.

### 4.3 Tenant Data Export
- Authorized platform operators or tenant owners can export tenant data:
  ```bash
  python -m app.cli.export_tenant --tenant-id <ID> --output-format json --out-file /tmp/tenant_export.json
  ```
- Complies with data sovereignty and GDPR Article 20 requirements.

### 4.4 Tenant Deletion (Soft vs Hard)
- **Soft Deletion**: `status = "deleted"`. Tenant records are preserved for 30 days retention window to protect historical audit logs.
- **Hard Deletion (GDPR Right to Be Forgotten)**:
  - Requires two-person rule approval in Platform Admin.
  - Anonymizes PII, purges audit metadata older than compliance requirements, and unlinks billing customer IDs.

---

## 5. Incident Response Protocols

### 5.1 Webhook Signature Failure & Tampering Alert
- **Symptom**: Sentry / SigNoz alert triggers on `Invalid webhook signature`.
- **Immediate Actions**:
  1. Inspect `provider_event_inbox` table:
     ```sql
     SELECT id, event_id, event_type, processing_status, error_detail, created_at
     FROM provider_event_inbox
     WHERE processing_status = 'failed'
     ORDER BY id DESC LIMIT 20;
     ```
  2. Verify if `FLEXPRICE_WEBHOOK_SECRET` matches the secret registered in Flexprice console.
  3. Validate source IP against the allowlist of internal VPC NAT addresses.

### 5.2 Replay Attack & Timestamp Skew
- **Mechanism**: Events with `X-Flexprice-Timestamp` older than 300 seconds are rejected with HTTP 400.
- **Action**: Check NTP synchronization on application and Flexprice hosts (`chrony` or `systemd-timesyncd`).

### 5.3 Webhook Dead-Letter Replay Procedure
To replay failed inbox events after resolving an outage or bug:
```bash
python scripts/reconcile_saas_control_plane.py --replay-failed --limit 50
```
This reprocesses pending or failed events through the idempotency filter and projection updater.
