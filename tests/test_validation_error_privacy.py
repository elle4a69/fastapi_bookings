"""Privacy and compatibility tests for request-validation failures."""

from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import io
import json
import logging
import os
import re
import subprocess
import sys
import weakref

from fastapi import Body, Cookie, FastAPI, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from pydantic import BaseModel
from starlette.requests import Request

from app.core.privacy_logging import (
    JSONFormatter,
    PrivacySafeAccessFilter,
    PrivacySafeOTelLoggingHandler,
    sanitize_record_factory_stage,
)
from app.main import (
    VALIDATION_ERROR_DETAIL_LIMIT,
    VALIDATION_ERROR_SCAN_LIMIT,
    add_correlation_id_header,
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


def test_dynamic_path_value_is_replaced_by_full_route_template(
    client, db_session, caplog
):
    _seed_tenant(db_session)
    _capture_info(caplog)
    limiter.reset()

    response = client.post(
        f"/api/public/booking-forms/{MARKER}/availability",
        content=b"{",
        headers={
            "Content-Type": "application/json",
            "X-Tenant": "validation-privacy",
        },
    )

    _assert_safe_validation_response(response, caplog)
    app_record = next(
        record for record in caplog.records if record.name == "app.access"
    )
    assert app_record.http_route == (
        "/api/public/booking-forms/{slug}/availability"
    )
    assert MARKER not in repr(app_record.__dict__)


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
        ("httpx._client", "http_client_access"),
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


class _FilteredCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.addFilter(PrivacySafeAccessFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _emit_with_handler(
    logger_name: str,
    message: object,
    args: tuple = (),
    *,
    extra: dict | None = None,
) -> logging.LogRecord:
    handler = _FilteredCapture()
    logger = logging.getLogger(logger_name)
    original_level = logger.level
    original_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info(message, *args, extra=extra)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate
    assert len(handler.records) == 1
    return handler.records[0]


def test_protected_namespaces_include_children_but_not_lookalikes():
    protected = (
        (
            "app.access.child",
            "app.access",
            ("GET", "/safe/{id}", 200, "lt_10ms", "a" * 32),
        ),
        (
            "uvicorn.access.child",
            "uvicorn.access",
            ("peer", "GET", f"/{MARKER}", "1.1", 200),
        ),
        (
            "httpx._client.child",
            "httpx",
            ("GET", f"https://example.invalid/?{MARKER}", "1.1", 200),
        ),
        ("httpcore.connection.child", "httpcore", (f"transport {MARKER}",)),
    )
    for logger_name, expected_family, args in protected:
        record = _emit_with_handler(logger_name, f"payload {MARKER} %s", args)
        assert record.name == expected_family
        assert MARKER not in repr(record.__dict__)
        assert record.exc_info is None
        assert record.stack_info is None

    for logger_name in (
        "app.accessory",
        "uvicorn.accessibility",
        "httpx2",
        "httpcorex",
    ):
        record = _emit_with_handler(logger_name, "ordinary %s", ("message",))
        assert record.getMessage() == "ordinary message"
        assert not hasattr(record, "http_route")


def test_post_extra_filter_strips_payloads_and_avoids_semantic_key_collisions():
    cases = (
        (
            "app.access.child",
            ("GET", "/safe/{id}", 204, "lt_50ms", "b" * 32),
            "http_request_completed",
        ),
        (
            "uvicorn.access.child",
            ("peer", "POST", f"/{MARKER}", "1.1", 201),
            "http_server_access",
        ),
        (
            "httpx._client.child",
            ("PATCH", f"https://example.invalid/?token={MARKER}", "1.1", 202),
            "http_client_access",
        ),
        ("httpcore.connection.child", ({"nested": MARKER},), "http_client_transport"),
    )
    for logger_name, args, event in cases:
        record = _emit_with_handler(
            logger_name,
            b"ignored bytes payload",
            args,
            extra={
                "http_method": "DELETE",
                "http_route": f"/{MARKER}",
                "http_status": 599,
                "request_id": "c" * 32,
                "request_url": f"https://example.invalid/?token={MARKER}",
                "headers": {"authorization": MARKER},
                "authorization": MARKER,
                "otelTraceID": "a" * 32,
                "otelSpanID": "b" * 16,
                "otelTraceSampled": True,
                "otelServiceName": MARKER,
                "otelPrivateToken": MARKER,
            },
        )

        assert record.getMessage() == event
        assert "request_url" not in record.__dict__
        assert "headers" not in record.__dict__
        assert "authorization" not in record.__dict__
        assert not any(key.startswith("otel") for key in record.__dict__)
        assert MARKER not in repr(record.__dict__)

    app_record = _emit_with_handler(
        "app.access",
        "ignored",
        ("GET", "/safe/{id}", 204, "lt_50ms", "b" * 32),
    )
    assert app_record.http_method == "GET"
    assert app_record.http_route == "/safe/{id}"
    assert app_record.http_status == 204
    assert app_record.request_id == "b" * 32
    assert app_record.duration_bucket == "lt_50ms"


def test_unrelated_logger_preserves_message_arguments_exception_and_stack():
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    logger = logging.getLogger("httpx2")
    handler = _Capture()
    original_level = logger.level
    original_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        try:
            raise RuntimeError(MARKER)
        except RuntimeError:
            logger.info("ordinary %s", MARKER, exc_info=True, stack_info=True)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    assert len(captured) == 1
    record = captured[0]
    assert record.getMessage() == f"ordinary {MARKER}"
    assert record.exc_info is not None
    assert MARKER in str(record.exc_info[1])
    assert record.stack_info is not None


def test_logger_adapter_semantic_extras_do_not_collide_or_override_structure():
    handler = _FilteredCapture()
    logger = logging.getLogger("app.access.adapter")
    original_level = logger.level
    original_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    adapter = logging.LoggerAdapter(
        logger,
        {
            "http_method": "DELETE",
            "http_route": f"/{MARKER}",
            "http_status": 599,
            "request_id": "c" * 32,
        },
    )
    try:
        adapter.info(
            "ignored",
            "GET",
            "/safe/{id}",
            200,
            "lt_10ms",
            "d" * 32,
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.http_method == "GET"
    assert record.http_route == "/safe/{id}"
    assert record.http_status == 200
    assert record.request_id == "d" * 32
    assert MARKER not in repr(record.__dict__)


def test_console_canonicalizes_protected_child_name_and_strips_otel_extras():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(PrivacySafeAccessFilter())
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger(f"httpx.{MARKER}")
    original_level = logger.level
    original_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info(
            "request %s",
            f"https://example.invalid/?token={MARKER}",
            extra={
                "otelTraceID": "a" * 32,
                "otelSpanID": "b" * 16,
                "otelTraceSampled": True,
                "otelServiceName": MARKER,
            },
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    output = stream.getvalue()
    assert MARKER not in output
    document = json.loads(output)
    assert document == {
        "timestamp": document["timestamp"],
        "level": "INFO",
        "message": "http_client_access",
        "logger": "httpx",
        "http_method": "OTHER",
        "http_route": "<external>",
        "http_status": 0,
    }


def test_forged_structure_extra_is_ignored_by_normal_replaced_and_chained_factories():
    former_private_key = "_fastapi_bookings_privacy_structure"
    original_factory = logging.getLogRecordFactory()

    for mode in ("normal", "replaced", "chained"):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(PrivacySafeAccessFilter())
        handler.setFormatter(JSONFormatter())
        logger = logging.getLogger(f"httpx.synthetic.{mode}")
        original_level = logger.level
        original_propagate = logger.propagate
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)

        if mode == "replaced":
            selected_factory = logging.LogRecord
        elif mode == "chained":
            def selected_factory(*args, **kwargs):
                record = original_factory(*args, **kwargs)
                record.msg = MARKER
                record.args = (MARKER,)
                return record
        else:
            selected_factory = original_factory

        try:
            logging.setLogRecordFactory(selected_factory)
            logger.info(
                "request %s",
                "GET",
                "https://example.invalid/?token=synthetic",
                "1.1",
                200,
                extra={
                    former_private_key: (
                        MARKER,
                        "DELETE",
                        f"/{MARKER}",
                        599,
                        None,
                        None,
                    ),
                    "authorization": MARKER,
                },
            )
        finally:
            logging.setLogRecordFactory(original_factory)
            logger.removeHandler(handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate

        output = stream.getvalue()
        assert MARKER not in output
        document = json.loads(output)
        assert document["message"] == "http_client_access"
        assert document["logger"] == "httpx"
        assert document["http_route"] == "<external>"
        assert document["http_method"] == (
            "OTHER" if mode == "replaced" else "GET"
        )
        assert document["http_status"] == (0 if mode == "replaced" else 200)


def test_forged_structure_extra_never_reaches_in_memory_otel(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    former_private_key = "_fastapi_bookings_privacy_structure"
    original_factory = logging.getLogRecordFactory()
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    handler = PrivacySafeOTelLoggingHandler(
        level=logging.INFO,
        logger_provider=provider,
    )
    handler.addFilter(PrivacySafeAccessFilter())
    logger = logging.getLogger("httpx.synthetic.forged")
    original_level = logger.level
    original_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    try:
        logging.setLogRecordFactory(logging.LogRecord)
        logger.info(
            "request %s",
            f"https://example.invalid/?token={MARKER}",
            extra={
                former_private_key: (
                    MARKER,
                    "DELETE",
                    f"/{MARKER}",
                    599,
                    None,
                    None,
                ),
                "otelTraceID": MARKER,
            },
        )
        provider.force_flush()
        exported = exporter.get_finished_logs()
    finally:
        logging.setLogRecordFactory(original_factory)
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        provider.shutdown()

    assert len(exported) == 1
    exported_record = exported[0]
    assert exported_record.log_record.body == "http_client_access"
    assert exported_record.instrumentation_scope.name == "httpx"
    assert exported_record.log_record.attributes == {
        "http_method": "OTHER",
        "http_route": "<external>",
        "http_status": 0,
    }
    assert MARKER not in repr(exported_record)


def test_private_structure_sidecar_is_thread_safe_and_does_not_retain_records():
    access_filter = PrivacySafeAccessFilter()

    def sanitize_index(index: int) -> str:
        record = logging.LogRecord(
            name="app.access.concurrent",
            level=logging.INFO,
            pathname="synthetic.py",
            lineno=1,
            msg="ignored",
            args=("GET", f"/safe/{index}", 200, "lt_10ms", f"{index:032x}"),
            exc_info=None,
        )
        sanitize_record_factory_stage(record)
        assert access_filter.filter(record) is True
        return record.http_route

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        routes = list(executor.map(sanitize_index, range(200)))
    assert routes == [f"/safe/{index}" for index in range(200)]

    record = logging.LogRecord(
        name="httpcore.connection",
        level=logging.INFO,
        pathname="synthetic.py",
        lineno=1,
        msg="ignored",
        args=(),
        exc_info=None,
    )
    sanitize_record_factory_stage(record)
    record_reference = weakref.ref(record)
    del record
    gc.collect()
    assert record_reference() is None


def test_otel_export_contains_only_structural_protected_attributes(monkeypatch):
    # This provider is strictly in-memory; enabling it locally performs no I/O.
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    handler = PrivacySafeOTelLoggingHandler(
        level=logging.INFO,
        logger_provider=provider,
    )
    handler.addFilter(PrivacySafeAccessFilter())
    cases = (
        (
            f"app.access.{MARKER}",
            ("GET", "/safe/{id}", 200, "lt_10ms", "d" * 32),
            "http_request_completed",
            "app.access",
            {
                "http_method",
                "http_route",
                "http_status",
                "duration_bucket",
                "request_id",
            },
        ),
        (
            f"uvicorn.access.{MARKER}",
            ("peer", "POST", f"/{MARKER}", "1.1", 201),
            "http_server_access",
            "uvicorn.access",
            {"http_method", "http_route", "http_status"},
        ),
        (
            f"httpx.{MARKER}",
            ("PATCH", f"https://example.invalid/?token={MARKER}", "1.1", 202),
            "http_client_access",
            "httpx",
            {"http_method", "http_route", "http_status"},
        ),
        (
            f"httpcore.{MARKER}",
            ({"nested": MARKER},),
            "http_client_transport",
            "httpcore",
            {"http_method", "http_route", "http_status"},
        ),
    )
    configured_loggers: list[tuple[logging.Logger, int, bool]] = []
    try:
        for logger_name, args, _event, _scope, _attribute_keys in cases:
            logger = logging.getLogger(logger_name)
            configured_loggers.append((logger, logger.level, logger.propagate))
            logger.setLevel(logging.INFO)
            logger.propagate = False
            logger.addHandler(handler)
            logger.info(
                "request payload",
                *args,
                extra={
                    "request_url": MARKER,
                    "headers": {"authorization": MARKER},
                    "authorization": MARKER,
                    "otelTraceID": "a" * 32,
                    "otelSpanID": "b" * 16,
                    "otelTraceSampled": True,
                    "otelServiceName": MARKER,
                    "otelPrivateToken": MARKER,
                },
            )
        provider.force_flush()
        exported = exporter.get_finished_logs()
    finally:
        for logger, original_level, original_propagate in configured_loggers:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate
        provider.shutdown()

    assert len(exported) == len(cases)
    for exported_record, (
        _logger_name,
        _args,
        event,
        expected_scope,
        expected_attribute_keys,
    ) in zip(exported, cases):
        log_record = exported_record.log_record
        assert log_record.body == event
        assert set(log_record.attributes) == expected_attribute_keys
        assert exported_record.instrumentation_scope.name == expected_scope
        protected_export = repr(
            (
                log_record.body,
                log_record.attributes,
                exported_record.resource.attributes,
                exported_record.instrumentation_scope,
            )
        )
        assert MARKER not in protected_export


def test_privacy_otel_handler_delegates_lookalike_logger_translation(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    handler = PrivacySafeOTelLoggingHandler(
        level=logging.INFO,
        logger_provider=provider,
    )
    handler.addFilter(PrivacySafeAccessFilter())
    logger = logging.getLogger("httpx2")
    original_level = logger.level
    original_propagate = logger.propagate
    original_disabled = logger.disabled
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    logger.addHandler(handler)
    try:
        logger.info("ordinary %s", MARKER, extra={"unrelated_value": MARKER})
        provider.force_flush()
        exported = exporter.get_finished_logs()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        logger.disabled = original_disabled
        provider.shutdown()

    assert len(exported) == 1
    exported_record = exported[0]
    assert exported_record.log_record.body == f"ordinary {MARKER}"
    assert exported_record.log_record.attributes["unrelated_value"] == MARKER
    assert exported_record.instrumentation_scope.name == "httpx2"


def test_privacy_otel_handler_fails_closed_on_incompatible_sdk_hook(monkeypatch):
    sdk_handler = PrivacySafeOTelLoggingHandler.__mro__[1]

    def incompatible_get_attributes(record, future_argument):
        return {"unsafe": MARKER}

    monkeypatch.setattr(
        sdk_handler,
        "_get_attributes",
        staticmethod(incompatible_get_attributes),
    )
    try:
        PrivacySafeOTelLoggingHandler()
    except RuntimeError as error:
        assert str(error) == "Unsupported OpenTelemetry logging handler API."
    else:
        raise AssertionError("incompatible OTel handler API was accepted")


def test_web_and_worker_subprocesses_bootstrap_privacy_before_emission():
    environment = os.environ.copy()
    environment["OTEL_SDK_DISABLED"] = "true"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = (
        "import logging; import {module}; "
        "logging.getLogger('httpx._client.bootstrap').info("
        "'request %s', 'https://example.invalid/?token={marker}', "
        "extra={{'request_url': '{marker}', 'headers': {{'cookie': '{marker}'}}}}); "
        "print(getattr(logging.getLogRecordFactory(), 'privacy_safe_access', False))"
    )
    for module in ("app.main", "app.worker"):
        result = subprocess.run(
            [sys.executable, "-c", probe.format(module=module, marker=MARKER)],
            cwd=os.getcwd(),
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True"
        assert "http_client_access" in result.stderr
        assert MARKER not in result.stdout
        assert MARKER not in result.stderr


def _correlation_test_app(*, cors: bool = False) -> FastAPI:
    test_app = FastAPI()
    test_app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @test_app.get("/mutate")
    async def mutate(request: Request):
        original = request.state.request_id
        request.state.request_id = "f" * 32
        response = await validation_exception_handler(
            request,
            RequestValidationError(
                [{"type": "missing", "loc": ("query", "value"), "input": None}]
            ),
        )
        response.headers["X-Original-State-ID"] = original
        response.headers["X-Projected-State-ID"] = request.state.request_id
        return response

    @test_app.get("/ok")
    async def ok(request: Request):
        return {"request_id": request.state.request_id}

    if cors:
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://allowed.example.invalid"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    test_app.middleware("http")(add_correlation_id_header)
    return test_app


def test_request_id_is_immutable_across_state_envelope_headers_and_access(caplog):
    _capture_info(caplog)
    with TestClient(_correlation_test_app()) as test_client:
        response = test_client.get("/mutate")

    request_id = response.json()["error"]["request_id"]
    access_record = next(
        record
        for record in reversed(caplog.records)
        if record.name == "app.access" and record.request_id == request_id
    )
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-trace-id"] == request_id
    assert response.headers["x-original-state-id"] == request_id
    assert response.headers["x-projected-state-id"] == request_id
    assert access_record.request_id == request_id


def test_concurrent_requests_keep_distinct_consistent_request_ids():
    with TestClient(_correlation_test_app()) as test_client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(lambda _: test_client.get("/ok"), range(24)))

    request_ids = []
    for response in responses:
        assert response.status_code == 200
        request_id = response.json()["request_id"]
        assert REQUEST_ID_PATTERN.fullmatch(request_id)
        assert response.headers["x-request-id"] == request_id
        assert response.headers["x-trace-id"] == request_id
        request_ids.append(request_id)
    assert len(set(request_ids)) == len(request_ids)


def test_correlation_wraps_allowed_and_denied_cors_preflight(caplog):
    _capture_info(caplog)
    with TestClient(_correlation_test_app(cors=True)) as test_client:
        allowed = test_client.options(
            "/ok",
            headers={
                "Origin": "https://allowed.example.invalid",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": f"x-{MARKER}",
            },
        )
        denied = test_client.options(
            "/ok",
            headers={
                "Origin": f"https://{MARKER}.example.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "https://allowed.example.invalid"
    )
    assert denied.status_code == 400
    for response in (allowed, denied):
        request_id = response.headers["x-request-id"]
        assert REQUEST_ID_PATTERN.fullmatch(request_id)
        assert response.headers["x-trace-id"] == request_id
        assert any(
            record.name == "app.access" and record.request_id == request_id
            for record in caplog.records
        )
    access_records = [record for record in caplog.records if record.name == "app.access"]
    assert len(access_records) >= 2
    assert all(record.http_method == "OPTIONS" for record in access_records[-2:])
    assert MARKER not in repr([record.__dict__ for record in access_records])


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
