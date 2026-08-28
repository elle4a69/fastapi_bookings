#!/usr/bin/env python
"""Live SigNoz validation — strictly fail-closed and run-scoped.

Generates labelled synthetic telemetry with a unique run ID, flushes all
providers, then queries ClickHouse inside Docker to prove receipt of traces,
metrics, and structured logs generated during THIS specific execution.

Exits non-zero if:
  - Any signal fails to reach ClickHouse
  - The OTLP endpoint is unreachable
  - SDK is disabled
  - A privacy canary leaks into stored data

Usage:
    python bin/validate_signoz_live.py
"""

import os
import subprocess
import sys
import time
import json
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

from app.core.telemetry import (
    PrivacySafeSpanExporter,
    record_telemetry_log,
    _TELEMETRY_LOGGER_NAME,
)

CLICKHOUSE_CONTAINER = "signoz-telemetrystore-clickhouse-0-0"
SERVICE_NAME = "fastapi-bookings"
PRIVACY_SENTINEL = "PRIVACY_SENTINEL_CANARY_12345"

failures: list[str] = []


def _ch_query(sql: str) -> str:
    """Execute a ClickHouse query via docker exec; return stdout."""
    result = subprocess.run(
        [
            "docker", "exec", CLICKHOUSE_CONTAINER,
            "clickhouse-client", "--query", sql,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ClickHouse query failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    run_start_ns = time.time_ns()
    run_start_ms = run_start_ns // 1_000_000
    run_id = f"val{int(time.time())}"

    base = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    print(f"=== Live SigNoz Validation (fail-closed, run_id={run_id}) ===")
    print(f"OTLP endpoint (from settings): {base}")
    print(f"SDK disabled: {settings.OTEL_SDK_DISABLED}")

    if settings.OTEL_SDK_DISABLED:
        print("[FAIL] OTEL_SDK_DISABLED is True — cannot validate live pipeline.")
        return 1

    resource = Resource.create({"service.name": SERVICE_NAME})

    # ── 1. Traces ─────────────────────────────────────────────────────────
    print("\n--- 1. Generating Traces ---")
    t_exp = OTLPSpanExporter(endpoint=f"{base}/v1/traces", timeout=5)
    safe_exp = PrivacySafeSpanExporter(t_exp)
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(safe_exp, max_export_batch_size=10,
                                             schedule_delay_millis=500))
    tracer = tp.get_tracer("live-validator")

    span_200_name = f"live_200_{run_id}"
    span_404_name = f"live_404_{run_id}"
    span_405_name = f"live_405_{run_id}"

    with tracer.start_as_current_span(span_200_name) as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.status_code", 200)
        span.set_attribute("http.route", "/api/health")
        # Inject privacy sentinel as an unallowlisted attribute
        span.set_attribute("customer_secret", PRIVACY_SENTINEL)

    with tracer.start_as_current_span(span_404_name) as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.status_code", 404)
        span.set_attribute("http.route", "/api/not-found")

    with tracer.start_as_current_span(span_405_name) as span:
        span.set_attribute("http.method", "POST")
        span.set_attribute("http.status_code", 405)
        span.set_attribute("http.route", "/api/read-only")

    tp.force_flush(timeout_millis=10000)
    print(f"  Exported 3 run-tagged spans ({span_200_name}, {span_404_name}, {span_405_name})")

    # ── 2. Metrics ────────────────────────────────────────────────────────
    print("\n--- 2. Generating Metrics ---")
    m_exp = OTLPMetricExporter(endpoint=f"{base}/v1/metrics", timeout=5)
    m_reader = PeriodicExportingMetricReader(m_exp, export_interval_millis=1000,
                                            export_timeout_millis=3000)
    mp = MeterProvider(resource=resource, metric_readers=[m_reader])
    meter = mp.get_meter("live-validator")
    ctr = meter.create_counter("live_validation_counter")
    ctr.add(1, {"status": "accepted", "event": "live_test"})
    mp.force_flush(timeout_millis=10000)
    print("  Exported 1 metric data point")

    # ── 3. Logs (dedicated pipeline) ──────────────────────────────────────
    print("\n--- 3. Generating Dedicated Structured Log ---")
    l_exp = OTLPLogExporter(endpoint=f"{base}/v1/logs", timeout=5)
    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(l_exp, max_queue_size=512,
                                                        max_export_batch_size=64))
    handler = LoggingHandler(level=logging.DEBUG, logger_provider=lp)
    dedicated = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    dedicated.addHandler(handler)
    dedicated.setLevel(logging.DEBUG)
    dedicated.propagate = False

    record_telemetry_log(
        event_code="LIVE_TEST_EVENT",
        level="INFO",
        module="live_validator",
        request_id=run_id,
        method="POST",
        status="200",
        duration_ms=42.0,
    )
    lp.force_flush(timeout_millis=10000)
    dedicated.removeHandler(handler)
    print(f"  Exported 1 structured log record tagged with request_id={run_id}")

    # ── 4. Flush and wait for batch writes ────────────────────────────────
    print("\n--- 4. Waiting 5s for ClickHouse Ingestion ---")
    tp.shutdown()
    mp.shutdown()
    lp.shutdown()
    time.sleep(5)

    # ── 5. Query ClickHouse ───────────────────────────────────────────────
    print("\n--- 5. ClickHouse Evidence Verification ---")

    # 5a. Traces: check specifically for this run's 3 span names
    try:
        count_str = _ch_query(
            f"SELECT count() FROM signoz_traces.signoz_index_v3 "
            f"WHERE resources_string['service.name'] = '{SERVICE_NAME}' "
            f"AND name IN ('{span_200_name}', '{span_404_name}', '{span_405_name}')"
        )
        trace_count = int(count_str)
        print(f"  Run-specific traces received: {trace_count} / 3")
        if trace_count < 3:
            failures.append(f"Expected 3 run-specific traces ({span_200_name}, {span_404_name}, {span_405_name}), got {trace_count}")
    except Exception as e:
        failures.append(f"Trace query failed: {e}")

    # 5b. Logs: check specifically for this run's request_id
    try:
        count_str = _ch_query(
            f"SELECT count() FROM signoz_logs.logs_v2 "
            f"WHERE resources_string['service.name'] = '{SERVICE_NAME}' "
            f"AND attributes_string['request_id'] = '{run_id}'"
        )
        log_count = int(count_str)
        print(f"  Run-specific structured logs received: {log_count} / 1")
        if log_count < 1:
            failures.append(f"Expected >= 1 log with request_id={run_id}, got {log_count}")
    except Exception as e:
        failures.append(f"Log query failed: {e}")

    # 5c. Metrics: check samples_v4 for timestamp >= run_start_ms
    try:
        count_str = _ch_query(
            f"SELECT count() FROM signoz_metrics.samples_v4 "
            f"WHERE metric_name = 'live_validation_counter' "
            f"AND unix_milli >= {run_start_ms}"
        )
        metric_count = int(count_str)
        print(f"  Run-specific metric samples received: {metric_count}")
        if metric_count < 1:
            failures.append(f"Expected >= 1 metric sample recorded since {run_start_ms}, got {metric_count}")
    except Exception as e:
        failures.append(f"Metric query failed: {e}")

    # 5d. Privacy scan: sentinel must NEVER appear in trace attributes
    try:
        leak_str = _ch_query(
            f"SELECT count() FROM signoz_traces.signoz_index_v3 "
            f"WHERE position(toString(attributes_string), '{PRIVACY_SENTINEL}') > 0"
        )
        leak_count = int(leak_str)
        print(f"  Privacy sentinel leaks: {leak_count}")
        if leak_count > 0:
            failures.append(f"PRIVACY VIOLATION: sentinel found in {leak_count} spans")
    except Exception as e:
        failures.append(f"Privacy scan failed: {e}")

    # ── 6. Report ─────────────────────────────────────────────────────────
    print()
    if failures:
        print("=== VALIDATION FAILED ===")
        for f in failures:
            print(f"  [FAIL] {f}")
        return 1
    else:
        print("=== VALIDATION PASSED ===")
        print(f"  [OK] Run {run_id} traces verified in SigNoz (200, 404, 405)")
        print(f"  [OK] Run {run_id} structured logs verified in SigNoz")
        print(f"  [OK] Run {run_id} metrics verified in SigNoz")
        print("  [OK] Privacy canary completely absent from stored telemetry")
        return 0


if __name__ == "__main__":
    sys.exit(main())
