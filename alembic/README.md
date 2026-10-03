# Database Migrations Architecture & Ledger (`alembic/`)

## 1. Purpose & Scope

The `alembic/` package manages relational schema migrations, version tracking, and schema evolution for **FastAPI Bookings**.

### What it owns:
- **Migration Execution Environment (`env.py`)**: Configures Alembic's online and offline migration contexts, dynamically binds to `settings.DATABASE_URL`, exposes `target_metadata = Base.metadata` for autogeneration, and handles bootstrap stamping for empty databases.
- **Migration Version History (`versions/`)**: Sequential revision scripts applying schema adjustments, column additions, foreign keys, and indexes.
- **Template Configuration (`script.py.mako`)**: Code generation template for new Alembic migration scripts.

### What it deliberately avoids:
- Does not define domain models (defined in `app/models/`).
- Does not manage runtime ORM sessions or connections (managed in `app/db/`).
- Does not execute non-relational graph or cache migrations (e.g. Neo4j Cypher schemas or Redis keyspaces).

---

## 2. Architecture & Key Files

```text
alembic/
├── env.py                # Alembic runtime environment, dynamic connection configuration, empty DB bootstrap
├── script.py.mako        # Migration template script
├── README.md             # This living architectural documentation
└── versions/             # Migration revisions ledger
    ├── 872af49ef6c4_initial_schema.py
    ├── 62202d3e7aa6_add_sms_module.py
    ├── 73a63e930e5b_add_chatwoot_integration.py
    ├── 7a91f2c8d4e0_configurable_booking_forms.py
    ├── a1b2c3d4e5f6_add_knowledge_graph_projections.py
    ├── a1c2e3g4i5k6_add_channel_neutral_and_style_example_tables.py
    ├── b1c2d3e4f5a6_baseline_bridge.py
    ├── b2c3d4e5f6a7_add_learning_event_worker_leasing.py
    ├── b2d3f4h5j6l7_add_tenant_assistant_policy.py
    ├── c4d31b16692d_add_remediation_fields.py
    ├── c5e6f7a8b9c0_add_incall_outcall_and_service_mode_schema.py
    ├── d4f6h8j0l2n4_tenant_scoped_booking_idempotency.py
    ├── d7e8f9a0b1c2_add_generic_outbox_leases.py
    ├── d9a1f4b2e8c1_add_booking_slot_allocations.py
    ├── e1b2c3d4e5f6_audit_and_repair_slot_allocations.py
    ├── e4f5a6b7c8d9_add_bootcamp_settings_fields.py
    ├── e5g7i9k1m3o5_tenant_translations.py
    ├── e8f9a0b1c2d3_add_tenant_modules_and_tier.py
    ├── f2c0b8d9e7a1_add_webhook_delivery_safety.py
    ├── f3a4b5c6d7e8_reconcile_pre_upgrade_schema.py
    ├── f6a7b8c9d0e1_add_itinerary_conflict_fields.py
    ├── f6h8j0l2n4p6_multi_location_and_chatwoot_bindings.py
    ├── g7h9j1k3m5n7_add_business_assistant_foundation.py
    ├── h8j0k2m4n6p8_reconcile_business_assistant_schema.py
    ├── j1k2m3n4p5q6_add_pgvector_extension_and_hnsw_index.py
    ├── k2m3n4p5q6r7_add_sms_bootcamp_message_status.py
    └── m3n4p5q6r7s8_reconcile_missing_domain_tables.py
```

### Empty Database Bootstrap Pattern (`alembic/env.py:59-72`):
Because the repository adopted Alembic after initial core domain tables were already created in legacy FastBook, the oldest revision (`872af49ef6c4`) is an incremental delta rather than a zero-baseline script. To allow clean local and CI environments to bootstrap reliably:
1. `env.py` inspects the target database connection.
2. If `destination == "head"` and no user tables exist (empty database), it executes `target_metadata.create_all(bind=connection)`.
3. It immediately stamps the revision history at the current `head` (`context.get_context().stamp(script, script.get_current_head())`).
4. Pre-existing databases proceed through standard incremental revision chains.

---

## 3. Setup, Configuration & Dependencies

### Configuration Binding
- Connection URL is loaded dynamically from `app.core.config.settings.DATABASE_URL` inside [`alembic/env.py`](file:///f:/Projects/fastapi_bookings/alembic/env.py#L21):
  ```python
  config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
  ```
- Target metadata is imported from [`app.db.database.Base`](file:///f:/Projects/fastapi_bookings/app/db/database.py#L45) with full model registration via `import app.models`.

---

## 4. Core Workflows & Contracts

### 4.1 Applying Migrations
```powershell
# Upgrade to current head
.\.venv\Scripts\alembic.exe upgrade head

# Inspect current revision status
.\.venv\Scripts\alembic.exe current

# View heads in revision tree
.\.venv\Scripts\alembic.exe heads
```

### 4.2 Creating New Migrations
```powershell
# Autogenerate migration candidate from models diff
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe_schema_change"
```

### 4.3 Safe Reversible DDL Contract
All migrations must implement both `upgrade()` and `downgrade()` functions. When modifying column nullability or introducing foreign keys, backfills must be executed inside the transaction before tightening nullability constraints (see pattern in [`f3a4b5c6d7e8_reconcile_pre_upgrade_schema.py`](file:///f:/Projects/fastapi_bookings/alembic/versions/f3a4b5c6d7e8_reconcile_pre_upgrade_schema.py)).

---

## 5. Data Safety & Isolation

- **Transactional Migrations**: Migrations run inside explicit transactions (`with context.begin_transaction():`), ensuring automatic rollback upon syntax or constraint errors.
- **Tenant ID Integrity**: Reconciliations systematically backfill and enforce `tenant_id` foreign keys with `ondelete="CASCADE"`.
- **Dialect Parity Handling**: Where SQLite and PostgreSQL syntax diverge (such as partial index constraints), revisions use dialect checks (`if bind.dialect.name == "sqlite":` or `sqlite_where` / `postgresql_where`).

---

## 6. Known Issues, Edge Cases & Outstanding Work

1. **Reconciled Domain Models (Work Package 5 Completed)**:
   - Domain tables `tenant_websites` ([app/models/tenant_website.py](file:///f:/Projects/fastapi_bookings/app/models/tenant_website.py#L96)), `client_disputes` ([app/models/client_dispute.py](file:///f:/Projects/fastapi_bookings/app/models/client_dispute.py#L30)), `sms_quick_tools` ([app/models/sms_quick_tool.py](file:///f:/Projects/fastapi_bookings/app/models/sms_quick_tool.py#L13)), and `gdpr_consents` ([app/models/general_systems.py](file:///f:/Projects/fastapi_bookings/app/models/general_systems.py#L35)) are now fully reconciled into the linear migration ledger via revision `m3n4p5q6r7s8_reconcile_missing_domain_tables.py`.
   - The migration uses idempotent `inspect(op.get_bind()).get_table_names()` guards to safely apply across both fresh databases and databases where `create_all()` was previously executed, and implements clean downgrade drops.
   - Single linear head is confirmed at `m3n4p5q6r7s8`.
2. **pgvector Extension & HNSW Indexing (Reconciled)**:
   - Migration `j1k2m3n4p5q6` (`j1k2m3n4p5q6_add_pgvector_extension_and_hnsw_index.py`) adds `CREATE EXTENSION IF NOT EXISTS vector;` and establishes HNSW cosine index `ix_curated_memories_embedding_hnsw` on `curated_memories.embedding`.
3. **Partial Index DDL Divergence**:
   - In revision `3ffd6b0bbcaf`, PostgreSQL partial indexes require explicit cast syntax (`postgresql_where=sa.text("status != 'CANCELLED'::bookingstatus")`), while SQLite requires untyped string comparisons (`sqlite_where=sa.text("status != 'cancelled'")`).

---

## 7. Verification & Testing Commands

```powershell
# Check current revision against head
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe current

# Verify schema history integrity
.\.venv\Scripts\alembic.exe check

# Verify parity between PostgreSQL ports
.\.venv\Scripts\python.exe scripts/verify_db_parity.py
```
