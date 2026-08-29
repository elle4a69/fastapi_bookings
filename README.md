# FastAPI Bookings

A multi-tenant, production-grade booking engine, provider scheduling platform, and customer communications backend built with FastAPI, SQLAlchemy, and React.

---

## 🏛️ System Architecture & Capabilities

FastAPI Bookings is the canonical source of truth for tenants, services, provider scheduling, availability calculations, bookings, customer interactions, payment processing, and event dispatching.

### 1. Multi-Tenant Booking & Provider Scheduling
- **Tenant Isolation:** Explicit tenant boundaries across all database queries, catalog items, customers, appointments, and configuration.
- **Provider Schedules & Slot Allocation:** Granular provider working hours, break definitions, buffer times, and concurrency-safe double-booking prevention.
- **Public & Admin Workflows:** Public customer booking flows and authenticated administration portals.

### 2. Fail-Closed Stripe Webhooks & Server-Authoritative Deposits
- **Server-Authoritative Calculation:** Booking amounts, currencies, and deposit policies are strictly calculated on the server from database records—never trusted from client payloads.
- **Fail-Closed Verification:** Strict Stripe cryptographic signature verification (`stripe-signature`) required on all incoming webhooks; unsigned or invalid requests are rejected immediately.
- **Idempotent Event Handling:** Event IDs are uniquely tracked to guarantee exactly-once payment reconciliation, state transitions, and receipt issuance.

### 3. Tenant-Isolated Webhooks with SSRF Prevention
- **Tenant Matching:** Outbound webhooks match domain events strictly by `tenant_id`, preventing cross-tenant information leakage.
- **SSRF Hardening:** Validates target URLs at dispatch time to block private IP ranges (RFC 1918), loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, `fe80::/10`), AWS/GCP metadata endpoints (`169.254.169.254`), and multicast addresses.
- **Cryptographic Signatures:** Outbound webhook payloads are signed using HMAC-SHA256 with timestamp replay protection.

### 4. Concurrency-Safe Atomic Outbox Leasing
- **Transactional Outbox Pattern (`app/services/outbox_worker.py`):** Ensures reliable external event dispatching and notification delivery decoupled from HTTP request transactions.
- **Atomic Leasing:** Workers acquire pending outbox events using database row locking with lease timeouts, ensuring safe horizontal scaling across multiple worker processes without double delivery.
- **Backoff & Dead-Letter Handling:** Exponential backoff with jitter on transient failures, and deterministic isolation/quarantine for poison or unsupported event types.

### 5. Standardized Admin Authentication & Session Security
- **Endpoints:** Admin authentication via `/login` (UI) and `/api/admin/auth/login` (REST API).
- **JWT Standard Claims:** Standardized claims including issuer (`iss`), audience (`aud`), subject (`sub`), tenant ID (`tenant_id`), role (`role`), and explicit expiration (`exp`).
- **Brute-Force Protection:** Rate-limiting middleware on authentication endpoints with IP and tenant context isolation.

### 6. Container Deployment & Health Verification
- **Hardened Containers:** Production Docker images execute as an unprivileged, non-root user (`appuser`).
- **Lifecycle Migrations:** Managed Alembic startup migrations executed before serving live traffic.
- **Deep Health & Readiness:**
  - `GET /health`: Liveness probe for process availability.
  - `GET /ready`: Deep readiness probe verifying database connectivity, required core table schemas, and Alembic migration revision alignment.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL / SQLite.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons.
- **Testing & Tooling:** Pytest, pytest-asyncio, HTTPX.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or later
- Node.js 18+ and npm
- PostgreSQL (or local SQLite for test/development)

### Backend Setup

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the repository root based on `.env.example`:
   ```bash
   DATABASE_URL=sqlite:///./fastapi_bookings.db
   SECRET_KEY=your-secure-random-secret-key
   ENCRYPTION_KEY=your-32-byte-base64-encryption-key
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

4. **Run Database Migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Start the FastAPI Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   API interactive documentation will be available at `http://localhost:8000/docs`.

6. **Start the Background Outbox Worker (Optional / Production):**
   ```bash
   python -m app.services.outbox_worker
   ```

---

### Frontend Setup

1. **Navigate to the frontend directory and install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the Vite development server:**
   ```bash
   npm run dev
   ```
   The UI will be accessible at `http://localhost:5173`.

---

## 🧪 Testing & Verification

Run the comprehensive backend test suite:
```bash
pytest tests/
```

Run frontend build and type checks:
```bash
cd frontend
npm run build
```

---

## 🔒 Security & Privacy Practices

- **Strict Tenant Scope:** No cross-tenant access, data sharing, or unscoped queries are permitted.
- **Privacy-Safe Telemetry & Logs:** PII (names, phone numbers, email addresses, SMS contents, authorization headers, credit card details) is strictly redacted from all structured logs and OpenTelemetry spans.
- **Fail-Closed Operations:** Missing secrets or invalid credentials immediately fail closed rather than falling back to unauthenticated or insecure modes.
