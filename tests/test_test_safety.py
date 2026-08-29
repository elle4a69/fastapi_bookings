"""Test Safety & Network Isolation Verification Suite (TEST-001, TEST-003).

Asserts that:
1. Outbound external network connections (sockets, urllib, httpx) are trapped and blocked.
2. Localhost/testserver connections are permitted.
3. Opt-in bypass mechanism (@pytest.mark.allow_network and allow_network_calls()) works for dedicated tests.
4. SMS provider adapters operate safely via mocks/fakes in test environments.
5. Synthetic phone numbers are used in test fixtures.
"""

import asyncio
import socket
import pytest
import httpx
import urllib.request
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.services.sms.transports.fake import FakeTransportAdapter
from app.services.sms.transports.mobilemessage import MobileMessageAdapter
from app.services.sms.transports.base import OutboundSmsCommand
from app.services.clicksend import ClickSendClient
from app.models.sms_account import SmsAccount
from tests.conftest import allow_network_calls, disable_network_trap


# ===========================================================================
# 1. External Network Trap Verification
# ===========================================================================

def test_raw_socket_connect_to_external_ip_is_blocked():
    """Verify raw socket connect to public IP raises RuntimeError with network trap message."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            s.connect(("8.8.8.8", 53))
        assert "Live network access is prohibited during testing" in str(exc_info.value)
    finally:
        s.close()


def test_raw_socket_connect_ex_to_external_ip_is_blocked():
    """Verify raw socket connect_ex to public IP raises RuntimeError."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            s.connect_ex(("1.1.1.1", 80))
        assert "Live network access is prohibited during testing" in str(exc_info.value)
    finally:
        s.close()


def test_socket_create_connection_to_external_host_is_blocked():
    """Verify socket.create_connection to external hostname raises RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        socket.create_connection(("example.com", 80))
    assert "Live network access is prohibited during testing" in str(exc_info.value)


def test_socket_connect_to_cloud_metadata_is_blocked():
    """Verify attempts to reach cloud metadata (169.254.169.254) are blocked."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            s.connect(("169.254.169.254", 80))
        assert "Live network access is prohibited during testing" in str(exc_info.value)
    finally:
        s.close()


def test_socket_connect_to_lan_ip_is_blocked():
    """Verify attempts to reach non-loopback LAN addresses are blocked."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            s.connect(("192.168.1.1", 80))
        assert "Live network access is prohibited during testing" in str(exc_info.value)
    finally:
        s.close()


def test_httpx_sync_client_to_external_api_is_blocked():
    """Verify httpx.Client calls to external domains are trapped."""
    with pytest.raises(RuntimeError) as exc_info:
        with httpx.Client() as client:
            client.get("https://api.stripe.com/v1/charges")
    assert "Live network access is prohibited during testing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_httpx_async_client_to_external_api_is_blocked():
    """Verify httpx.AsyncClient calls to external domains are trapped."""
    with pytest.raises(RuntimeError) as exc_info:
        async with httpx.AsyncClient() as client:
            await client.get("https://rest.clicksend.com/v3/sms/send")
    assert "Live network access is prohibited during testing" in str(exc_info.value)


def test_urllib_request_to_external_url_is_blocked():
    """Verify standard urllib.request calls to external URLs are trapped."""
    with pytest.raises(RuntimeError) as exc_info:
        urllib.request.urlopen("https://example.com")
    assert "Live network access is prohibited during testing" in str(exc_info.value)


# ===========================================================================
# 2. Localhost / TestServer Allowed Verification
# ===========================================================================

def test_testclient_requests_are_permitted(client: TestClient):
    """Verify that TestClient requests (which target testserver / localhost) are allowed."""
    response = client.get("/ready")
    assert response.status_code in (200, 503)


def test_localhost_socket_binding_and_connecting_permitted():
    """Verify loopback connections (127.0.0.1) are permitted through the trap."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # This connect call should NOT raise RuntimeError("Live network access is prohibited")
        client_sock.connect(("127.0.0.1", port))
        conn, _ = server_sock.accept()
        conn.close()
    finally:
        client_sock.close()
        server_sock.close()


def test_context_manager_allows_opt_in_bypass():
    """Verify allow_network_calls() / disable_network_trap() temporarily disables the trap."""
    with allow_network_calls():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Under allow_network_calls, socket connection is not trapped with RuntimeError
            # Instead, standard socket connection attempt occurs
            s.settimeout(0.001)
            try:
                s.connect(("192.0.2.1", 80))  # TEST-NET-1 (RFC 5737)
            except (socket.timeout, OSError, TimeoutError):
                pass  # Expected OS-level network failure, NOT RuntimeError
        finally:
            s.close()


@pytest.mark.allow_network
def test_marker_allows_opt_in_bypass():
    """Verify @pytest.mark.allow_network opts out of the network trap."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.001)
        try:
            s.connect(("192.0.2.1", 80))
        except (socket.timeout, OSError, TimeoutError):
            pass  # Expected OS-level network failure, NOT RuntimeError
    finally:
        s.close()


# ===========================================================================
# 3. SMS Provider Adapters & Synthetic Test Safety
# ===========================================================================

def test_fake_transport_adapter_operates_locally_without_network():
    """Verify FakeTransportAdapter operates purely in-memory."""
    FakeTransportAdapter.sent_messages.clear()
    adapter = FakeTransportAdapter()
    account = SmsAccount(id=1, tenant_id=1, transport_type="simulator", sender_address="61400000001")
    command = OutboundSmsCommand(to="61400000000", body="Synthetic test message")

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(adapter.send(account, command))
    loop.close()

    assert result.status == "success"
    assert result.provider_message_id is not None
    assert len(FakeTransportAdapter.sent_messages) == 1
    assert FakeTransportAdapter.sent_messages[0]["to"] == "61400000000"


def test_live_mobilemessage_adapter_is_trapped_without_mock():
    """Verify unmocked MobileMessageAdapter attempts are trapped before hitting the network."""
    adapter = MobileMessageAdapter()
    account = SmsAccount(
        id=1,
        tenant_id=1,
        transport_type="mobilemessage",
        sender_address="61400000001",
    )
    account.credentials = {"username": "live_user", "password": "live_password"}
    command = OutboundSmsCommand(to="61400000000", body="Trap check")

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(adapter.send(account, command))
        assert result.status == "exception"
        assert "Live network access is prohibited during testing" in result.error_message
    finally:
        loop.close()


def test_live_clicksend_client_is_trapped_without_mock():
    """Verify unmocked ClickSendClient attempts are trapped before hitting the network."""
    client = ClickSendClient()
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(RuntimeError) as exc_info:
            loop.run_until_complete(client.send_sms(to="+61400000000", body="Trap check"))
        assert "Live network access is prohibited during testing" in str(exc_info.value)
    finally:
        loop.close()
