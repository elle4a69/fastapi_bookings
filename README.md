# FastAPI Bookings – Front‑End Ready API

This project provides a **self‑contained booking management API** built with FastAPI and SQLAlchemy.  It is designed to make it simple to build a modern admin dashboard and public booking portal without relying on the external SimplyBook API.

## Key Features

* **Self‑contained**: Uses a local SQLite database and seeds demo data on first startup.  No external services are required.
* **Admin and Public API**: Exposes clean REST endpoints under `/api/admin` and `/api/public` for use by front‑end clients.
* **Clean booking API**: Exposes a front-end-ready booking API with admin and public routes. Recurring booking series and automatic waitlist promotion are intentionally excluded from this handoff build.
* **Front‑end bootstrap endpoints**: `/api/public/bootstrap` and `/api/admin/dashboard/bootstrap` return all information needed to initialise a booking flow or admin dashboard in a single request.
* **Booking state machine**: Bookings transition through `pending`, `confirmed`, `cancelled`, `completed`, `no_show` and `rescheduled` states via dedicated endpoints.
* **Success/error envelopes**: All API responses follow a consistent envelope shape with `ok`, `data` and `meta` fields on success and a structured `error` object on failure.
* **OpenAPI schema and TypeScript SDK**: The project exposes a schema at `/openapi.json` which can be used to generate TypeScript clients.  A route manifest at `contracts/route-manifest.json` maps logical operations to concrete endpoints.
* **Bootstrap endpoints**: `/api/public/bootstrap` and `/api/admin/dashboard/bootstrap` aggregate data into a single response to reduce the number of calls needed when a page loads.
* **Pagination and filtering**: List endpoints accept `page` and `page_size` query parameters, along with domain‑specific filters (e.g. `status`, `provider_id`, `date_from` for bookings).
* **Booking state machine**: Bookings transition through `pending`, `confirmed`, `cancelled`, `completed`, `no_show` and `rescheduled` states via dedicated endpoints.
* **Role‑based access**: User roles (`owner`, `admin`, `staff`, `viewer`) are supported; only admins can perform privileged operations such as managing services and providers.
* **Health & readiness**: `/health`, `/ready` and `/version` endpoints provide simple liveness checks.
* **Docker support**: A Dockerfile and docker-compose configuration are included for easy deployment and local development.
* **CORS & environment profiles**: CORS origins can be configured via the `FRONTEND_ORIGINS` environment variable.  The `APP_ENV` variable selects appropriate environment profiles.
* **Contracts and Documentation**: See the `contracts/` directory for machine‑readable API contracts and human‑readable front‑end flow documentation.

## Running Locally

Requirements:

* Python 3.12+
* `pip` for installing dependencies

Install dependencies and run the server:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows use .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  Documentation is available at `/docs` and `/redoc`.  The OpenAPI JSON can be fetched from `/openapi.json`.

## Docker

To build and run via Docker:

```bash
docker build -t fastapi-bookings .
docker run -p 8000:8000 fastapi-bookings
```

Alternatively, use `docker-compose`:

```bash
docker compose up --build
```

## Seeds

On first run the app seeds a demo company, one admin user (`admin` / `admin123`), one provider and one service.  You can customise seeding by editing `app/seed.py`.

## Contracts

Contracts defining request/response shapes live in the `contracts/` directory.  These contracts are useful for generating front‑end clients and ensuring all parties share the same expectations.  See:

* `contracts/frontend/public-booking-flow.md` – step‑by‑step description of the booking flow.
* `contracts/admin-dashboard.contract.json` – machine‑readable contract for the admin dashboard API.
* `contracts/public-booking.contract.json` – machine‑readable contract for the public booking API.
* `contracts/auth.contract.json` – contract covering authentication flows.
* `contracts/booking-flow.contract.json` – contract for booking state transitions.
* `contracts/errors.contract.json` – error envelope specification.


## Front-End Contracts

The front-end contract layer is complete under `contracts/`.

Start with:

* `contracts/FRONTEND_CONTRACT_INDEX.md`
* `contracts/route-manifest.json`
* `contracts/data-models.contract.json`
* `contracts/public-booking.contract.json`
* `contracts/admin-dashboard.contract.json`
* `docs/frontend/FRONTEND_AGENT_BUILD_INSTRUCTIONS.md`

Important behaviour: public bookings are created as `pending` and require admin/provider approval before they are confirmed.

## Testing

Tests live under the `tests/` directory.  Use `pytest` to run the suite:

```bash
pytest -q
```

## Contributing

Feel free to extend the domain models, add more endpoints, or refine the contracts.  Pull requests are welcome.

## Front-End Handoff

Before starting the UI, read:

* `contracts/FRONTEND_CONTRACT_INDEX.md`
* `docs/frontend/FRONTEND_AGENT_BUILD_INSTRUCTIONS.md`
* `contracts/route-manifest.json`
* `contracts/data-models.contract.json`

Public booking requests produce `pending` bookings. The admin/provider must confirm them using:

```text
POST /api/admin/bookings/{booking_id}/confirm
```

The front end should use `/api/public/ui-config` to hide disabled modules and `/api/public/search-availability` for flexible booking entry points.
