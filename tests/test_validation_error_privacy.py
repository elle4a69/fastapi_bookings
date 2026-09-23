"""Privacy and compatibility tests for request-validation failures."""

from __future__ import annotations

import logging

from fastapi import Body, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import limiter, settings, validation_exception_handler
from app.models.tenant import Tenant


MARKER = "SYNTHETIC-VALIDATION-CANARY-7f28c19d"


def _seed_tenant(db_session) -> Tenant:
    tenant = Tenant(
        name="Synthetic Validation Privacy Tenant",
        subdomain="validation-privacy",
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


def _assert_safe_validation_response(response, caplog) -> None:
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Validation failed for the request."
    assert isinstance(body["error"]["request_id"], str)
    assert 1 <= len(body["error"]["details"]) <= 20
    for detail in body["error"]["details"]:
        assert set(detail) == {"loc", "type", "message"}
        assert detail["loc"] in [
            ["body"],
            ["query"],
            ["path"],
            ["header"],
            ["cookie"],
            ["request"],
        ]
        assert detail["type"] in {
            "missing",
            "invalid_json",
            "type_error",
            "choice_error",
            "constraint_error",
            "extra_field",
            "invalid",
        }
        assert detail["message"] == "Invalid request value."
    assert MARKER not in response.text
    assert MARKER not in caplog.text


def test_malformed_json_does_not_reflect_body_or_parser_context(
    client, db_session, caplog, monkeypatch
):
    _seed_tenant(db_session)
    caplog.set_level(logging.WARNING, logger="httpx")
    synthetic_origin = "https://validation-privacy.example.invalid"
    monkeypatch.setattr(settings, "FRONTEND_ORIGINS", synthetic_origin)

    response = client.post(
        "/api/admin/auth",
        content=f'{{"company":"validation-privacy","login":"{MARKER}",'.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Tenant": "validation-privacy",
            "Origin": synthetic_origin,
            "Authorization": f"Bearer {MARKER}",
        },
    )

    _assert_safe_validation_response(response, caplog)
    assert response.json()["error"]["details"] == [
        {
            "loc": ["body"],
            "type": "invalid_json",
            "message": "Invalid request value.",
        }
    ]
    assert response.headers["Access-Control-Allow-Origin"] == synthetic_origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_nested_and_oversize_shaped_bodies_are_bounded_and_private(
    client, db_session, caplog
):
    _seed_tenant(db_session)
    caplog.set_level(logging.WARNING, logger="httpx")
    limiter.reset()

    payloads = [
        {
            "company": {MARKER: {"nested": MARKER}},
            "login": MARKER,
            "password": MARKER,
        },
        [
            {"customer_token": MARKER, "prompt": MARKER, "phone": MARKER}
            for _ in range(500)
        ],
    ]
    for payload in payloads:
        response = client.post(
            "/api/admin/auth",
            json=payload,
            headers={"X-Tenant": "validation-privacy"},
        )
        _assert_safe_validation_response(response, caplog)
        assert len(response.content) < 4096


def test_query_validation_does_not_reflect_query_value(client, db_session, caplog):
    _seed_tenant(db_session)
    caplog.set_level(logging.WARNING, logger="httpx")
    limiter.reset()

    response = client.get(
        "/api/public/availability",
        params={
            "service_id": MARKER,
            "provider_id": "1",
            "date": "2030-01-01T10:00:00Z",
        },
        headers={"X-Tenant": "validation-privacy"},
    )

    _assert_safe_validation_response(response, caplog)
    assert response.json()["error"]["details"] == [
        {
            "loc": ["query"],
            "type": "type_error",
            "message": "Invalid request value.",
        }
    ]


class _DynamicPayload(BaseModel):
    values: dict[int, int]


class _ListItem(BaseModel):
    value: int


def _privacy_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    @test_app.get("/typed-header")
    def typed_header(x_validation_count: int = Header(...)):
        return {"value": x_validation_count}

    @test_app.post("/dynamic-object")
    def dynamic_object(payload: _DynamicPayload):
        return payload

    @test_app.post("/many-errors")
    def many_errors(payload: list[_ListItem] = Body(...)):
        return payload

    return test_app


def test_header_and_dynamic_field_locations_never_reflect_markers(caplog):
    caplog.set_level(logging.WARNING, logger="httpx")
    with TestClient(_privacy_test_app()) as test_client:
        header_response = test_client.get(
            "/typed-header",
            headers={"X-Validation-Count": MARKER},
        )
        dynamic_response = test_client.post(
            "/dynamic-object",
            json={"values": {MARKER: MARKER}},
        )

    _assert_safe_validation_response(header_response, caplog)
    _assert_safe_validation_response(dynamic_response, caplog)
    assert header_response.json()["error"]["details"][0]["loc"] == ["header"]
    assert dynamic_response.json()["error"]["details"][0]["loc"] == ["body"]


def test_many_body_errors_are_deduplicated_bounded_and_deterministic(caplog):
    caplog.set_level(logging.WARNING, logger="httpx")
    payload = [{"value": MARKER} for _ in range(500)]

    with TestClient(_privacy_test_app()) as test_client:
        first = test_client.post("/many-errors", json=payload)
        second = test_client.post("/many-errors", json=payload)

    _assert_safe_validation_response(first, caplog)
    _assert_safe_validation_response(second, caplog)
    assert first.json()["error"]["details"] == second.json()["error"]["details"]
    assert first.json()["error"]["details"] == [
        {
            "loc": ["body"],
            "type": "type_error",
            "message": "Invalid request value.",
        }
    ]


def test_validation_handler_does_not_change_auth_404_or_405_contracts(
    client, db_session
):
    _seed_tenant(db_session)

    unauthenticated = client.get(
        "/api/admin/services",
        headers={"X-Tenant": "validation-privacy"},
    )
    not_found = client.get("/synthetic-validation-route-that-does-not-exist")
    method_not_allowed = client.post("/health")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "UNAUTHORIZED"
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "NOT_FOUND"
    assert method_not_allowed.status_code == 405
    assert method_not_allowed.json()["error"]["code"] == "HTTP_ERROR"
