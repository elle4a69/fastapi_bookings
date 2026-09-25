# Operational & Development Scripts

## Purpose & Scope
The `scripts/` directory contains CLI utilities, deterministic seeders, data synchronization scripts, and release gate verification runners for **FastAPI Bookings**.

---

## Architecture & Key Scripts

```
scripts/
├── seed_clean_numbered_data.py    # Deterministic test database seeder (Client 1..5, Provider 1..2, Service 1..5)
├── sync_mock_to_chatwoot.py       # Pushes mock contacts and conversations into local Chatwoot API
├── generate_pwa_icons.py          # Generates high-res PWA png icons and maskable graphics
├── verify_all_release_gates.py    # Unified release gate verification runner (pytest + build checks)
├── verify_production_secrets.py   # Production secrets and security toggles validator (Section 25)
└── README.md                      # Living documentation
```

---

## Usage Instructions

### 1. Deterministic Seeder (`seed_clean_numbered_data.py`)
Populates the local database with clean numbered entities for easy testing:
- **Tenant**: `simplydemo`
- **Providers**: `Provider 1`, `Provider 2`
- **Services**: `Service 1 - Standard Consultation 60m` ($120), `Service 2 - Express Follow-up 30m` ($65), `Service 3 - Premium Assessment 90m` ($180), etc.
- **Clients**: `Client 1 - Alice Walker` (`0411000001`), `Client 2 - Bob Taylor` (`0411000002`), etc.

```bash
# Execute seeder
.venv\Scripts\python.exe scripts/seed_clean_numbered_data.py
```

### 2. Chatwoot Synchronizer (`sync_mock_to_chatwoot.py`)
Syncs seeded conversations into a running Chatwoot instance (`http://localhost:3000`):
```bash
.venv\Scripts\python.exe scripts/sync_mock_to_chatwoot.py
```

### 3. Release Gate Verification (`verify_all_release_gates.py`)
Executes the comprehensive verification gate across backend and frontend:
```bash
.venv\Scripts\python.exe scripts/verify_all_release_gates.py
```

### 4. Production Secrets Validation (`verify_production_secrets.py`)
Audits all security keys, database URLs, and dev OTP bypass toggles for production safety (Section 25) without printing any secret values:
```bash
python scripts/verify_production_secrets.py --env production
```

