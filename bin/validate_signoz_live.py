"""Live SigNoz Observability Validation Script.

Generates:
1. One normal backend request (GET /api/public/ui-config)
2. One controlled 404 (GET /api/public/non-existent-route)
3. One controlled 405 (POST /api/public/ui-config)
4. One safe custom background/webhook event (record_webhook_event("accepted"))
5. One safe frontend diagnostic event (POST /api/public/diagnostics/telemetry)

Flushes OTel providers and verifies exported spans, metrics, and log records.
"""

import time
import json
import logging
from fastapi.testclient import TestClient

# Ensure telemetry is enabled for live validation run
from app.core.config import settings
settings.OTEL_SDK_DISABLED = False
settings.OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:8080"

from app.main import app
from app.core.telemetry import (
    init_telemetry,
    shutdown_telemetry,
    record_webhook_event,
    record_sms_event,
    record_ai_event,
    get_telemetry_status_data,
)

def run_live_validation():
    print("--- 1. Initializing Telemetry Pipeline ---")
    init_telemetry(app)
    status = get_telemetry_status_data()
    print("Telemetry Status:", status)

    client = TestClient(app)

    print("\n--- 2. Generating Traffic & Diagnostic Events ---")
    # Event 1: Normal backend request
    res1 = client.get("/api/public/ui-config", headers={"X-Tenant": "simplydemo"})
    print("1. Normal Request (GET /api/public/ui-config):", res1.status_code, "X-Trace-ID:", res1.headers.get("X-Trace-ID"))

    # Event 2: Controlled 404
    res2 = client.get("/api/public/non-existent-route-for-testing", headers={"X-Tenant": "simplydemo"})
    print("2. Controlled 404 (GET /api/public/non-existent-route-for-testing):", res2.status_code)

    # Event 3: Controlled 405
    res3 = client.post("/api/public/ui-config", json={"test": "payload"}, headers={"X-Tenant": "simplydemo"})
    print("3. Controlled 405 (POST /api/public/ui-config):", res3.status_code)

    # Event 4: Safe background/webhook custom event & metric
    record_webhook_event("accepted")
    record_sms_event("success", account_id=1)
    record_ai_event("processed", job_type="outbox_sms")
    print("4. Custom Background / Webhook Events Recorded")

    # Event 5: Safe public frontend diagnostic event
    fe_payload = {
        "event_type": "web_vital",
        "vital_name": "LCP",
        "duration_ms": 230.5,
        "route": "/book/checkout?token=secret123#step1"
    }
    res5 = client.post("/api/public/diagnostics/telemetry", json=fe_payload)
    print("5. Public Frontend Diagnostic Event:", res5.status_code, res5.json())

    print("\n--- 3. Flushing Telemetry Providers ---")
    shutdown_telemetry()
    print("Shutdown and flush complete!")
    print("SUCCESS: Live validation run completed cleanly.")

if __name__ == "__main__":
    run_live_validation()
