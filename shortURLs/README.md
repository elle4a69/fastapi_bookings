# URL Shortener Service

FastAPI URL shortener backed by MongoDB. The service exposes bounded single and
batch creation, redirect, deletion, health, and Prometheus metrics endpoints.

## Run locally

```sh
docker compose up -d --build
```

The API is available at `http://localhost:8002`.

- API docs: `/docs`
- Liveness: `/health/live`
- Readiness: `/health/ready`
- Metrics: `/metrics/`

## API

- `POST /api/v1/shorten/`
- `POST /api/v1/shorten/batch/`
- `POST /api/v1/shorten/batch/concurrent/`
- `GET /api/v1/{short_code}`
- `DELETE /api/v1/urls/delete/{short_code}`

Both batch endpoints return the same ordered response envelope:

```json
{
  "results": [
    {
      "index": 0,
      "long_url": "https://example.com/",
      "status": "success",
      "short_url": "http://short.url/abc",
      "created_at": 123,
      "error_code": null,
      "retryable": false
    }
  ],
  "success_count": 1,
  "failure_count": 0
}
```

All-success batches return HTTP `200`. Partial failures return HTTP `207` with
safe per-item error codes; database exception text is never returned to clients.

## Capacity controls

The following environment variables provide bounded, configurable behavior:

- `MAX_BATCH_SIZE` defaults to `100`.
- `BATCH_MAX_CONCURRENCY` defaults to `10`.
- `MAX_REQUEST_BODY_BYTES` defaults to `524288`.

The application limits protect each process. A production ingress should still
enforce its own request-body, connection, and tenant-rate limits.

## Logging and observability

`structlog` produces structured logs and binds a validated `X-Request-ID` to
each request. Set `LOG_JSON=true` in production and use `LOG_LEVEL` to control
verbosity. Prometheus request and batch-item metrics are exposed at `/metrics/`.

Distributed tracing is intentionally not included yet. Request IDs provide
correlation without adding an OpenTelemetry collector to this single service.

## MongoDB migration

The service uses PyMongo Async. Before deploying the unique `short_code` index
to an existing database:

```sh
python -m app.utils.data_cleanup --export dup_report.json
python -m app.utils.data_cleanup --apply --rebuild-indexes --export dup_report.json
```

The first command is read-only. The second command:

1. merges duplicate `long_url` records;
2. synchronizes `short_code` from `short_url`;
3. reassigns duplicate codes while updating both fields together;
4. validates all invariants;
5. replaces a legacy non-unique `short_code` index only after validation passes.

Back up the database before applying the migration.

## Tests

```sh
docker compose exec web pytest -q
```

API tests use HTTPX `ASGITransport` and an isolated in-memory fake database.
They do not require a live HTTP server and cannot write into the configured
MongoDB instance.
