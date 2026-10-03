"""Tests for SMS carrier webhook endpoints fail-closed behavior (HTTP 410 GONE)."""

import pytest
from fastapi.testclient import TestClient


def test_clicksend_webhook_returns_410_gone(client: TestClient):
    """Verify legacy ClickSend and click_send webhook requests cleanly return HTTP 410 GONE."""
    for transport in ("clicksend", "click_send"):
        # 1. Inbound webhook with route parameter
        resp = client.post(f"/api/sms/webhooks/{transport}/acc-test-clicksend-id")
        assert resp.status_code == 410
        body = resp.json()
        detail = body.get("error", {}).get("message") or body.get("detail", "")
        assert "Legacy direct carrier webhook routes are permanently deactivated" in detail

        # 2. Generic inbound webhook with transport_type in payload
        resp_generic = client.post(
            "/api/sms/webhooks/incoming",
            json={"transport_type": transport, "account_public_id": "acc-clicksend"},
        )
        assert resp_generic.status_code == 410
        detail_generic = resp_generic.json().get("error", {}).get("message") or resp_generic.json().get("detail", "")
        assert "Legacy direct carrier webhook routes are permanently deactivated" in detail_generic

        # 3. Delivery receipt webhook with route parameter
        resp_dlr = client.post(f"/api/sms/webhooks/{transport}/acc-test-clicksend-id/delivery")
        assert resp_dlr.status_code == 410
        detail_dlr = resp_dlr.json().get("error", {}).get("message") or resp_dlr.json().get("detail", "")
        assert "Legacy direct carrier delivery receipt routes are permanently deactivated" in detail_dlr
