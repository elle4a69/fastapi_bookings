import asyncio
import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_database_client
from app.core.config import settings
from app.main import create_app
from tests.fakes import FakeDatabase


@dataclass
class APIContext:
    client: AsyncClient
    database: FakeDatabase


@pytest_asyncio.fixture
async def api() -> APIContext:
    database = FakeDatabase()
    app = create_app()

    async def override_database():
        yield database

    app.dependency_overrides[get_database_client] = override_database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield APIContext(client=client, database=database)
    app.dependency_overrides.clear()


async def create_short_url(api: APIContext, url: str = "https://example.com") -> str:
    response = await api.client.post(
        "/api/v1/shorten/",
        json={"long_url": url},
    )
    assert response.status_code == 200
    assert "short_url" in response.json()
    return response.json()["short_url"]


@pytest.mark.asyncio
async def test_create_short_url(api: APIContext):
    await create_short_url(api)


@pytest.mark.asyncio
async def test_create_short_url_contains_created_at(api: APIContext):
    unique_url = f"https://example.com/created-at-{uuid.uuid4()}"
    response = await api.client.post(
        "/api/v1/shorten/",
        json={"long_url": unique_url},
    )
    assert response.status_code == 200
    assert isinstance(response.json().get("created_at"), int)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/shorten/batch/",
        "/api/v1/shorten/batch/concurrent/",
    ],
)
async def test_create_short_urls_batch(api: APIContext, path: str):
    response = await api.client.post(
        path,
        json=[
            {"long_url": "https://example.com"},
            {"long_url": "https://example.org"},
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2
    assert data["failure_count"] == 0
    assert [item["index"] for item in data["results"]] == [0, 1]
    assert all(item["status"] == "success" for item in data["results"])
    assert all(isinstance(item["created_at"], int) for item in data["results"])


@pytest.mark.asyncio
async def test_create_short_urls_concurrently_existing_long_url(api: APIContext):
    unique_url = f"https://example.com/existing-{uuid.uuid4()}"
    existing_short_url = await create_short_url(api, unique_url)
    response = await api.client.post(
        "/api/v1/shorten/batch/concurrent/",
        json=[{"long_url": unique_url}],
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["short_url"] == existing_short_url


@pytest.mark.asyncio
async def test_batch_partial_failure_has_stable_safe_contract(api: APIContext):
    failed_url = "https://example.com/unavailable"
    api.database.collection.fail_long_urls.add(failed_url)
    response = await api.client.post(
        "/api/v1/shorten/batch/concurrent/",
        json=[
            {"long_url": "https://example.com/ok"},
            {"long_url": failed_url},
        ],
    )
    assert response.status_code == 207
    data = response.json()
    assert data["success_count"] == 1
    assert data["failure_count"] == 1
    failed = data["results"][1]
    assert failed["status"] == "failed"
    assert failed["error_code"] == "storage_unavailable"
    assert failed["retryable"] is True
    assert "simulated" not in response.text


@pytest.mark.asyncio
async def test_batch_size_is_bounded(api: APIContext, monkeypatch):
    monkeypatch.setattr(settings, "max_batch_size", 2)
    response = await api.client.post(
        "/api/v1/shorten/batch/concurrent/",
        json=[
            {"long_url": "https://example.com/1"},
            {"long_url": "https://example.com/2"},
            {"long_url": "https://example.com/3"},
        ],
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_request_body_size_is_bounded(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_bytes", 64)
    database = FakeDatabase()
    app = create_app()

    async def override_database():
        yield database

    app.dependency_overrides[get_database_client] = override_database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/shorten/",
            json={"long_url": f"https://example.com/{'x' * 100}"},
        )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_chunked_request_body_size_is_bounded(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_bytes", 64)
    database = FakeDatabase()
    app = create_app()

    async def override_database():
        yield database

    async def oversized_chunks():
        yield b'{"long_url":"https://example.com/'
        yield b"x" * 100
        yield b'"}'

    app.dependency_overrides[get_database_client] = override_database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/shorten/",
            content=oversized_chunks(),
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_redirect_to_long_url_with_short_code(api: APIContext):
    short_url = await create_short_url(api)
    short_code = short_url.split("/")[-1]
    response = await api.client.get(f"/api/v1/{short_code}")
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/"


@pytest.mark.asyncio
async def test_delete_short_url_with_short_code(api: APIContext):
    short_url = await create_short_url(api)
    short_code = short_url.split("/")[-1]
    response = await api.client.delete(f"/api/v1/urls/delete/{short_code}")
    assert response.status_code == 200
    assert response.json() == {"detail": "URL deleted successfully."}


@pytest.mark.asyncio
async def test_redirect_to_nonexistent_short_url(api: APIContext):
    response = await api.client.get("/api/v1/nonexistent_short_url")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_short_url(api: APIContext):
    response = await api.client.delete("/api/v1/urls/delete/nonexistent_short_url")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_short_urls_with_empty_list(api: APIContext):
    for path in (
        "/api/v1/shorten/batch/",
        "/api/v1/shorten/batch/concurrent/",
    ):
        response = await api.client.post(path, json=[])
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_short_url_invalid_input(api: APIContext):
    response = await api.client.post(
        "/api/v1/shorten/",
        json={"long_url": "not-a-url"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_create_same_long_url(api: APIContext):
    unique_url = f"https://example.com/concurrent-{uuid.uuid4()}"

    async def create_once():
        response = await api.client.post(
            "/api/v1/shorten/",
            json={"long_url": unique_url},
        )
        assert response.status_code == 200
        return response.json()["short_url"]

    results = await asyncio.gather(*[create_once() for _ in range(5)])
    assert len(set(results)) == 1


@pytest.mark.asyncio
async def test_request_id_is_returned_and_preserved(api: APIContext):
    response = await api.client.get(
        "/health/live",
        headers={"x-request-id": "qa-request-123"},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "qa-request-123"


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced(api: APIContext):
    response = await api.client.get(
        "/health/live",
        headers={"x-request-id": "invalid request id"},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] != "invalid request id"


@pytest.mark.asyncio
async def test_readiness_reports_missing_database(api: APIContext):
    response = await api.client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "dependency": "mongodb",
    }


@pytest.mark.asyncio
async def test_metrics_endpoint_is_exposed(api: APIContext):
    response = await api.client.get("/metrics/")
    assert response.status_code == 200
    assert "url_shortener_http_requests_total" in response.text
