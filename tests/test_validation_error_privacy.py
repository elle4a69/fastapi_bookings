"""Privacy and compatibility tests for request-validation failures."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import Body, Cookie, FastAPI, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.requests import Request

from app.main import (
    VALIDATION_ERROR_DETAIL_LIMIT,
    VALIDATION_ERROR_SCAN_LIMIT,
    limiter,
    settings,
    validation_exception_handler,
)
from app.models.tenant import Tenant


MARKER = "SYNTHETIC-VALIDATION-CANARY-7f28c19d"
REQUEST_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


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
    request_id = body["error"]["request_id"]
    assert REQUEST_ID_PATTERN.fullmatch(request_id)
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-trace-id"] == request_id
    assert 1 <= len(body["error"]["details"]) <= VALIDATION_ERROR_DETAIL_LIMIT
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


def _capture_info(caplog) -> None:
    caplog.set_level(logging.INFO)


def test_malformed_json_does_not_reflect_body_or_parser_context(
    client, db_session, caplog, monkeypatch
):
    _seed_tenant(db_session)
    _capture_info(caplog)
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
    _capture_info(caplog)
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


def test_query_validation_uses_structural_access_logs_only(
    client, db_session, caplog
):
    _seed_tenant(db_session)
    _capture_info(caplog)
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
    access_records = [
        record
        for record in caplog.records
        if record.name == "app.access" or record.name.lower().startswith("httpx")
    ]
    assert access_records
    assert all("?" not in record.getMessage() for record in access_records)
    assert all(MARKER not in repr(record.__dict__) for record in access_records)
    app_record = next(record for record in access_records if record.name == "app.access")
    client_record = next(
        record for record in access_records if record.name.lower().startswith("httpx")
    )
    assert app_record.http_method == "GET"
    assert app_record.http_route == "/api/public/availability"
    assert app_record.http_status == 422
    assert app_record.request_id == response.json()["error"]["request_id"]
    assert client_record.getMessage() == "http_client_access"
    assert client_record.http_method == "GET"
    assert client_record.http_route == "<external>"
    assert client_record.http_status == 422


class _DynamicPayload(BaseModel):
    values: dict[int, int]


class _ListItem(BaseModel):
    value: int


class _MixedPayload(BaseModel):
    choice: int | list[int]


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

    @test_app.post("/mixed-sources")
    def mixed_sources(
        payload: _MixedPayload,
        count: int = Query(...),
        x_validation_count: int = Header(...),
        validation_cookie: int = Cookie(...),
    ):
        return {
            "payload": payload,
            "count": count,
            "header": x_validation_count,
            "cookie": validation_cookie,
        }

    return test_app


def test_header_cookie_query_union_and_list_values_never_reflect(caplog):
    _capture_info(caplog)
    with TestClient(_privacy_test_app()) as test_client:
        test_client.cookies.set("validation_cookie", MARKER)
        response = test_client.post(
            "/mixed-sources",
            params={"count": MARKER},
            headers={"X-Validation-Count": MARKER},
            json={"choice": {MARKER: [MARKER]}},
        )

    _assert_safe_validation_response(response, caplog)
    sources = {detail["loc"][0] for detail in response.json()["error"]["details"]}
    assert sources == {"body", "cookie", "header", "query"}


def test_header_and_dynamic_field_locations_never_reflect_markers(caplog):
    _capture_info(caplog)
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
    _capture_info(caplog)
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


def _synthetic_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/synthetic-validation-probe",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def _invoke_handler(error: RequestValidationError):
    return asyncio.run(validation_exception_handler(_synthetic_request(), error))


def test_42_source_category_pairs_are_deterministically_capped(caplog):
    _capture_info(caplog)
    sources = ["body", "query", "path", "header", "cookie", MARKER]
    error_types = [
        "missing",
        "json_invalid",
        "int_parsing",
        "enum",
        "greater_than",
        "extra_forbidden",
        "future_validation_type",
    ]
    errors = [
        {
            "type": error_type,
            "loc": (source, MARKER, index),
            "msg": MARKER,
            "input": MARKER,
            "ctx": {"error": ValueError(MARKER), "nested": {"secret": MARKER}},
        }
        for index, (source, error_type) in enumerate(
            (source, error_type)
            for source in sources
            for error_type in error_types
        )
    ]

    response = _invoke_handler(RequestValidationError(errors, body={MARKER: MARKER}))
    response_body = response.body.decode()
    assert response.status_code == 422
    assert MARKER not in response_body
    details = json.loads(response_body)["error"]["details"]
    categories = [
        "choice_error",
        "constraint_error",
        "extra_field",
        "invalid",
        "invalid_json",
        "missing",
        "type_error",
    ]
    expected = [
        {"loc": [source], "type": category, "message": "Invalid request value."}
        for source in ["body", "cookie", "header", "path", "query", "request"]
        for category in categories
    ][:VALIDATION_ERROR_DETAIL_LIMIT]
    assert details == expected
    assert len(details) == VALIDATION_ERROR_DETAIL_LIMIT
    assert MARKER not in caplog.text


class _CountingValidationError(RequestValidationError):
    def __init__(self) -> None:
        super().__init__([])
        self.visited = 0

    def errors(self):
        for index in range(VALIDATION_ERROR_SCAN_LIMIT + 50):
            self.visited += 1
            yield {
                "type": "missing" if index % 2 else "future_validation_type",
                "loc": ("body", MARKER, index),
                "msg": MARKER,
                "input": MARKER,
                "ctx": {"error": RuntimeError(MARKER)},
            }


def test_validation_error_traversal_and_output_are_bounded(caplog):
    _capture_info(caplog)
    error = _CountingValidationError()

    response = _invoke_handler(error)

    assert response.status_code == 422
    assert error.visited == VALIDATION_ERROR_SCAN_LIMIT
    assert MARKER not in response.body.decode()
    assert MARKER not in caplog.text


def test_uvicorn_access_records_are_sanitized_before_handlers():
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Capture()
    logger = logging.getLogger("uvicorn.access")
    original_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1:1",
            "GET",
            f"/synthetic?token={MARKER}",
            "1.1",
            422,
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)

    assert len(captured) == 1
    record = captured[0]
    assert record.getMessage() == "http_server_access"
    assert record.http_method == "GET"
    assert record.http_route == "<unmatched>"
    assert record.http_status == 422
    assert MARKER not in repr(record.__dict__)


def test_http_client_records_discard_messages_arguments_and_exceptions():
    for logger_name, expected_event in (
        ("httpx2", "http_client_access"),
        ("httpcore.connection", "http_client_transport"),
    ):
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture()
        logger = logging.getLogger(logger_name)
        original_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            try:
                raise RuntimeError(MARKER)
            except RuntimeError:
                logger.info(
                    "client request %s",
                    f"/synthetic?token={MARKER}",
                    exc_info=True,
                    stack_info=True,
                )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

        assert len(captured) == 1
        record = captured[0]
        assert record.getMessage() == expected_event
        assert record.exc_info is None
        assert record.stack_info is None
        assert MARKER not in repr(record.__dict__)


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
