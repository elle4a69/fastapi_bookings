# Core application services

## Purpose and scope

`app/core` owns shared application configuration, security helpers, state
machines, privacy logging and telemetry primitives. It does not own booking,
SMS, arrival or provider workflows; feature modules consume these primitives.

## Architecture and key files

- `config.py` defines typed process configuration through `Settings` and the
  shared `settings` instance.
- `security.py` owns authentication token and password helpers.
- `state_machine.py` defines booking lifecycle transitions.
- `privacy_logging.py` and `telemetry.py` own allowlisted structural
  observability behavior.

## Setup, configuration and dependencies

Settings are environment-backed Pydantic fields. Secrets must remain in
server-side runtime configuration and must never be printed or returned by an
API. `ARRIVAL_ALERT_PRODUCTION_ENABLED` defaults to `false`. It may be enabled
only after a dedicated leased `arrival.alert` consumer with a final
tenant/booking/expiry/acknowledgement eligibility check is deployed.

## Core workflows and contracts

Callers import the shared `settings` object and fail closed when an optional
production capability is disabled. The arrival alert producer performs no
database work while its gate is disabled.

## Data safety and isolation

Configuration values are process-local. A boolean feature gate is not a tenant
authorization boundary and cannot replace tenant/provider/account validation.
Credentials and customer data must not be added to configuration descriptions,
logs or telemetry.

## Known issues, edge cases and outstanding work

- Arrival alert production must remain disabled until its dedicated consumer
  and final delivery eligibility gate exist.
- This README is new on the arrival branch. Validation-v3 also introduces an
  `app/core/README.md`; integration must merge the two documents deliberately.

## Verification and testing commands

```powershell
$env:OTEL_SDK_DISABLED='true'
.\.venv\Scripts\python.exe -m py_compile app/core/config.py
.\.venv\Scripts\python.exe -m pytest tests/test_sms_arrivals.py -q
ruff check app/core/config.py
```
