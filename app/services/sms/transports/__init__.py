from typing import Dict
from .base import SmsTransportAdapter
from .fake import FakeTransportAdapter


DISABLED_DIRECT_TRANSPORTS = frozenset({"mobilemessage"})
DIRECT_PROVIDER_DISABLED_DETAIL = "Direct MobileMessage integration is disabled."
DIRECT_TRANSPORT_TERMINAL_REASON = "transport_disabled"


def is_disabled_direct_transport(transport_type: str) -> bool:
    """Return whether a retired direct-provider transport is fail-closed."""
    return transport_type.strip().lower() in DISABLED_DIRECT_TRANSPORTS

_transports: Dict[str, SmsTransportAdapter] = {
    "simulator": FakeTransportAdapter(),
}

def get_transport_adapter(transport_type: str) -> SmsTransportAdapter:
    """Resolve the transport adapter for the given type name."""
    adapter = _transports.get(transport_type.lower())
    if not adapter:
        raise ValueError(f"Unknown transport type: {transport_type}")
    return adapter
