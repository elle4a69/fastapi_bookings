# Postman API Sweep Tooling

## 1. Purpose & Scope

This module generates and runs authenticated Newman/Postman sweeps against a local FastAPI Bookings instance. Local sweep launchers and generated request URLs target the canonical backend at `http://127.0.0.1:7060` by default. The tooling does not own application routes or production deployment configuration.

## 2. Architecture & Key Files

- `FastAPI-Bookings-Local.postman_collection.json`: source collection.
- `prepare_authenticated_sweep.py`: creates synthetic local tenant/user credentials and produces the authenticated collection.
- `FastAPI-Bookings-Local-Authenticated.postman_collection.json`: generated authenticated sweep collection.
- `SimplyDemo-Local.postman_environment.json`: local environment, including the port-7060 base URL.
- `run-sweep-delayed.ps1` and `run-authenticated-sweep-delayed.ps1`: delayed Newman launchers.
- `launch-and-save-authenticated-sweep.ps1`: starts the backend when required and stores timestamped reports.
- `reports/`: generated run output; historical reports are not runtime configuration.

## 3. Setup, Configuration & Dependencies

Install the package dependencies from this directory with `npm install`. Python launchers use the repository virtual environment and application database configuration. Override the default backend URL for an intentional nonstandard run with `POSTMAN_BASE_URL`; otherwise use `http://127.0.0.1:7060`.

## 4. Core Workflows & Contracts

1. Start FastAPI Bookings on port `7060`, or use the authenticated launcher to start it.
2. Generate the authenticated collection with `python tools/postman-sweep/prepare_authenticated_sweep.py`.
3. Run Newman against the generated collection and local environment.
4. Review the generated JSON/HTML summary under `reports/`.

Collections must exercise real authenticated APIs. They must not add fake-success routes, create live external-provider actions, or treat generated reports as source configuration.

## 5. Data Safety & Isolation

Use synthetic, labelled local records only. Never place production credentials, customer data, SMS bodies, phone numbers, or authorization tokens in committed collections or reports. Cleanup scripts must remain tenant-scoped, and live SMS, payment, and external booking actions are outside the sweep's scope.

## 6. Known Issues, Edge Cases & Outstanding Work

- Generated authenticated collections contain expanded request URLs, so regenerate them after changing the canonical local backend port.
- Existing files under `reports/` may refer to ports used by historical runs; they are immutable evidence, not current launch instructions.
- Sweep success depends on the configured local database and required supporting services being healthy.

## 7. Verification & Testing Commands

```powershell
python -m pytest tests/test_backend_port_configuration.py -v
python tools/postman-sweep/prepare_authenticated_sweep.py
npx newman run tools/postman-sweep/FastAPI-Bookings-Local-Authenticated.postman_collection.json -e tools/postman-sweep/SimplyDemo-Local.postman_environment.json
```
