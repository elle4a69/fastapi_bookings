# Core Configuration, Security, Redis & Telemetry

## Purpose & Scope
The `app/core/` package encapsulates cross-cutting concerns for the application:
- Environment settings and secrets loading via Pydantic (`config.py`).
- Cryptographic password hashing, JWT access token generation, and role checks (`security.py`).
- Centralized, resilient Redis connection pooling, key namespacing, and health checks (`redis.py`).
- Finite state machines for appointment lifecycle transitions (`state_machine.py`).
- OpenTelemetry instrumentation, OTLP exporters, and PII redaction filters (`telemetry.py`).

---

## Architecture & Key Files

```
app/core/
├── config.py            # Global Settings (DATABASE_URL, REDIS_URL, SECRET_KEY, OPENAI_API_KEY, CALCOM_BASE_URL)
├── redis.py             # Sync & Async Redis connection pools, 'fb:' key formatting, ping healthcheck & fallback
├── security.py          # Passlib Argon2/Bcrypt hashing, JWT encode/decode routines
├── state_machine.py     # BookingStatus state machine (pending -> confirmed -> completed / cancelled)
└── telemetry.py         # OpenTelemetry TracerProvider, MeterProvider, and privacy span processor
```

---

## Setup, Configuration & Dependencies
Key environment variables in `.env`:
- `DATABASE_URL`: PostgreSQL connection string (cut over to dedicated instance on port 5433).
- `REDIS_URL`: Redis connection URL (default: `redis://127.0.0.1:6380/0`).
- `SECRET_KEY`: High-entropy key for JWT signature validation.
- `OPENAI_API_KEY`: API key for GPT-4o autonomous dialogue agent.
- `CALCOM_API_KEY`: Optional Cal.com API key for headless scheduling federation.
- `OTEL_EXPORTER_OTLP_ENDPOINT`: SigNoz or OpenTelemetry collector endpoint (e.g. `http://localhost:4318`).

---

## Redis Integration & Key Namespacing
- **Key Prefixing**: All Redis keys are strictly formatted via `format_key()` with the prefix `fb:` or `fb:{tenant_id}:...` ensuring strict multi-tenant isolation.
- **Connection Pools**: Thread-safe sync (`get_redis_client()`) and async (`get_async_redis_client()`) connection pools lazily initialized with reconnect handling and bounded connection counts.
- **Health Checks**: Synchronous `ping()` and asynchronous `async_ping()` methods for liveness/readiness probes.
- **Resilient Fallback**: Graceful local in-memory fallback mechanisms protect callers during transient Redis unavailability.

---

## Data Safety & Privacy
- **Redaction by Design**: `telemetry.py` strips all customer identities, phone numbers, emails, addresses, and query-string tokens from traces and logs before exporting.
- **Low-Cardinality Attributes Only**: Spans record structural data like HTTP method, route template, status code, and tenant hash.
- **Hashed Identifiers in Caches**: OTP cache keys hash phone numbers (`fb:otp:{tenant_id}:{sha256(phone)}`) so cleartext customer numbers are never stored in cache keys.

---

## Verification Commands
```bash
# Run security, telemetry, and client portal tests
.venv\Scripts\python.exe -m pytest tests/test_telemetry_pipeline.py tests/test_telemetry_redaction.py tests/test_client_portal.py -v
```
