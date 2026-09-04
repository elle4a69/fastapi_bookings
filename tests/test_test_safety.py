"""Regression coverage for the test-suite network safety boundary."""

import socket
import threading

import pytest

from app.core.config import settings
import conftest


def test_real_network_is_blocked_with_plausible_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
):
    """Credentials must never allow a test to open a real outbound socket."""
    monkeypatch.setattr(settings, "CLICKSEND_API_USERNAME", "plausible-test-user")
    monkeypatch.setattr(settings, "CLICKSEND_API_KEY", "plausible-test-key")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as outbound_socket:
        with pytest.raises(RuntimeError, match="Outbound network access is disabled"):
            outbound_socket.connect(("203.0.113.1", 443))


def test_socketpair_permit_does_not_allow_other_threads_to_connect(
    monkeypatch: pytest.MonkeyPatch,
):
    """Asyncio's private socketpair permit cannot create a global bypass."""
    permit_active = threading.Event()
    release_socketpair = threading.Event()
    worker_result = {}

    def controlled_socketpair(*args, **kwargs):
        permit_active.set()
        assert release_socketpair.wait(timeout=1)
        return object(), object()

    def create_socketpair():
        try:
            worker_result["value"] = socket.socketpair()
        except Exception as exc:  # pragma: no cover - asserted below
            worker_result["error"] = exc

    monkeypatch.setattr(conftest, "_ORIGINAL_SOCKETPAIR", controlled_socketpair)
    worker = threading.Thread(target=create_socketpair)
    worker.start()
    assert permit_active.wait(timeout=1)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as outbound_socket:
            with pytest.raises(RuntimeError, match="Outbound network access is disabled"):
                outbound_socket.connect(("203.0.113.1", 443))
    finally:
        release_socketpair.set()
        worker.join(timeout=1)

    assert not worker.is_alive()
    assert "error" not in worker_result
