# Operational & Development Scripts (`scripts/`)

The `scripts/` directory contains CLI automation tools, deterministic database seeders, living documentation verifiers, production secrets validators, and unified release gate runners for **FastAPI Bookings**.

---

## 1. Purpose & Scope

The operational scripts suite owns:
- **Deterministic Test Seeding** (`seed_clean_numbered_data.py`): Populates consistent, numbered entities (Client 1..5, Provider 1..2, Service 1..5) for automated test suites and manual validation.
- **Living Documentation Engine** (`index_living_docs.py`, `verify_living_docs.py`, `query_docs.py`): Rule 10 living documentation indexing, SQLite FTS5 search generation, compliance linter, and fast agent orientation tooling.
- **Production Security Auditing** (`verify_production_secrets.py`): Validates cryptographic secrets, production database URLs, and dev OTP bypass toggles without disclosing secret values.
- **Unified Release Gate Verification** (`verify_all_release_gates.py`): Multi-stage release verification executing syntax checks, backend unit tests, concurrency suites, API fuzzing, and frontend bundle validation.
- **External Integration Syncing** (`sync_mock_to_chatwoot.py`): Idempotent seeding and synchronization of contacts, inboxes, and conversations with local or staging Chatwoot instances.
- **Asset Generation** (`generate_pwa_icons.py`): Automated generation of high-resolution PWA icons and maskable web app graphics.

These scripts deliberately avoid mutating production databases without explicit environment confirmation flags, printing raw credentials or tokens to stdout, or introducing non-deterministic fixture data.

---

## 2. Architecture & Key Files

```
scripts/
├── seed_clean_numbered_data.py    # Deterministic test database seeder (Client 1..5, Provider 1..2, Service 1..5)
├── index_living_docs.py           # Living Documentation Indexer & Agent Knowledge Manifest (Rule 10)
├── verify_living_docs.py          # Living Documentation compliance release gate verifier
├── query_docs.py                  # CLI tool for FTS5 documentation search and agent boot snapshots
├── sync_mock_to_chatwoot.py       # Pushes mock contacts and conversations into local Chatwoot API
├── generate_pwa_icons.py          # Generates high-res PWA png icons and maskable graphics
├── verify_all_release_gates.py    # Unified release gate verification runner (pytest + build checks)
├── verify_production_secrets.py   # Production secrets and security toggles validator (Section 25)
└── README.md                      # Living documentation
```

### Key Files:
- [verify_living_docs.py](file:///f:/Projects/fastapi_bookings/scripts/verify_living_docs.py): CI release gate validating that all module READMEs satisfy the 7 mandatory Rule 10 sections without empty placeholder stubs.
- [index_living_docs.py](file:///f:/Projects/fastapi_bookings/scripts/index_living_docs.py): Scans module READMEs, extracts metadata and test commands, and builds `docs/module_manifest.json`, `docs/MODULE_INDEX.md`, and `docs/module_docs.db`.
- [query_docs.py](file:///f:/Projects/fastapi_bookings/scripts/query_docs.py): Rapid CLI interface for agents to look up module architecture, verification commands, and system boot snapshots.
- [seed_clean_numbered_data.py](file:///f:/Projects/fastapi_bookings/scripts/seed_clean_numbered_data.py): Deterministic seeder establishing baseline entities (`simplydemo` tenant, providers, locations, services, and customers).
- [verify_production_secrets.py](file:///f:/Projects/fastapi_bookings/scripts/verify_production_secrets.py): Validates production environment readiness and blocks deployment of insecure defaults.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **Python**: Version 3.11+
- **Environment**: Python packages from `requirements.txt` (SQLAlchemy 2.0, Pydantic v2, Pytest, Pillow for icon generation).
- **Virtual Environment**: Executed using `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` (Unix).

### Key Environment Settings
- `DATABASE_URL`: Target database connection string (defaults to SQLite `fastapi_bookings.db`).
- `APP_ENV`: Execution environment (`development`, `staging`, `production`).
- `CHATWOOT_BASE_URL` & `CHATWOOT_API_ACCESS_TOKEN`: Required for Chatwoot sync script.

---

## 4. Core Workflows & Contracts

### 4.1 Living Documentation Pipeline (Rule 10)
```text
Module READMEs (app/, frontend/, docs/, scripts/, tests/)
       │
       ▼
scripts/verify_living_docs.py (Release Gate: Enforces 7 sections & 0 stubs)
       │
       ▼
scripts/index_living_docs.py (Generates manifest.json, MODULE_INDEX.md, module_docs.db)
       │
       ▼
scripts/query_docs.py (Fast CLI orientation: --boot-snapshot, --test-command, --search)
```

### 4.2 Deterministic Seeding Workflow
1. Invoking `seed_clean_numbered_data.py` truncates or resets test data for the `simplydemo` tenant.
2. Creates:
   - Primary tenant (`simplydemo`).
   - 2 Service Providers (`Provider 1`, `Provider 2`) with configured weekly shift schedules.
   - 5 Services with standard pricing tiers ($65–$180) and duration increments (30m–90m).
   - 5 Synthetic Clients (`0411000001` - `0411000005`).
   - Sample bookings with pre-allocated discrete 15-minute slot reservations.

### 4.3 Production Secrets Validation
- Evaluates `.env` or system environment variables against production security rules:
  - Ensures `SECRET_KEY` is not using default development secrets.
  - Ensures `DATABASE_URL` references a production PostgreSQL instance rather than local SQLite.
  - Verifies `DEV_OTP_BYPASS` is disabled (`false`).

---

## 5. Data Safety & Isolation

- **Non-Destructive Defaults**: Utility scripts default to local development environments (`fastapi_bookings.db`) and refuse to wipe databases without explicit confirmation when `APP_ENV=production`.
- **Zero Secret Exposure**: `verify_production_secrets.py` masks all inspected secrets (e.g. `sk_live_***`) in console outputs and logs to prevent credential leakage in CI/CD pipeline transcripts.
- **Synthetic Test Identities**: Seeders generate synthetic phone numbers reserved for documentation/testing (`0411000001`–`0411000005`) to prevent accidental SMS dispatch to real customers.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **SQLite Lock Contention**: Running heavy seeders or migration scripts concurrently with active backend dev servers can trigger temporary SQLite locks; shut down the dev server before major seed runs.
- **Chatwoot Offline Resilience**: `sync_mock_to_chatwoot.py` will fail with connection errors if the local Chatwoot Docker instance is not running on port 3000.
- **Cross-Platform Path Separators**: Scripts normalize Windows backslashes (`\`) to standard forward slashes (`/`) for consistent Markdown and JSON index generation.

---

## 7. Verification & Testing Commands

To verify script functionality, documentation indexing, and gate runners:

```powershell
# 1. Run living documentation compliance linter
python scripts/verify_living_docs.py

# 2. Re-index living documentation catalog
python scripts/index_living_docs.py

# 3. Test living documentation test suite
python -m pytest tests/test_living_documentation.py -v

# 4. Verify production secrets in test mode
python scripts/verify_production_secrets.py --env development
```
