import hashlib
import hmac
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.assistant_booking_bridge import AssistantBookingBridgeBinding
from app.services import assistant_booking_bridge as bridge


def _signature(secret: str, method: str, path: str, stamp: str, nonce: str, body: bytes) -> str:
    key = hashlib.sha256(secret.encode()).hexdigest().encode("ascii")
    return hmac.new(key, bridge.canonical_request(method, path, stamp, nonce, body), hashlib.sha256).hexdigest()


def test_signed_request_is_one_use_and_does_not_require_raw_secret_storage(db_session):
    secret = "synthetic-bridge-secret"
    binding = AssistantBookingBridgeBinding(
        line_key="primary", tenant_id=1, provider_id=1, credential_key_id="synthetic-key",
        secret_verifier=hashlib.sha256(secret.encode()).hexdigest(), enabled=True,
    )
    db_session.add(binding); db_session.commit()
    stamp = str(int(datetime.now(timezone.utc).timestamp()))
    body = b'{"service_id":1}'
    signature = _signature(secret, "POST", "/api/internal/assistant-booking-bridge/availability", stamp, "nonce-1", body)
    authenticated = bridge.authenticate(db_session, method="POST", path="/api/internal/assistant-booking-bridge/availability", body=body, key_id="synthetic-key", timestamp=stamp, nonce="nonce-1", signature=signature)
    assert authenticated.line_key == "primary"
    with pytest.raises(HTTPException) as replay:
        bridge.authenticate(db_session, method="POST", path="/api/internal/assistant-booking-bridge/availability", body=body, key_id="synthetic-key", timestamp=stamp, nonce="nonce-1", signature=signature)
    assert replay.value.detail["code"] == "BRIDGE_REPLAY"


def test_disabled_binding_fails_closed_after_valid_signature(db_session):
    secret = "synthetic-disabled-secret"
    db_session.add(AssistantBookingBridgeBinding(line_key="primary", tenant_id=1, provider_id=1, credential_key_id="disabled-key", secret_verifier=hashlib.sha256(secret.encode()).hexdigest(), enabled=False))
    db_session.commit()
    stamp = str(int(datetime.now(timezone.utc).timestamp()))
    with pytest.raises(HTTPException) as unavailable:
        bridge.authenticate(db_session, method="GET", path="/api/internal/assistant-booking-bridge/catalog", body=b"", key_id="disabled-key", timestamp=stamp, nonce="nonce-disabled", signature=_signature(secret, "GET", "/api/internal/assistant-booking-bridge/catalog", stamp, "nonce-disabled", b""))
    assert unavailable.value.status_code == 503
