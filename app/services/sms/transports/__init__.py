from typing import Dict
from .base import SmsTransportAdapter
from .fake import FakeTransportAdapter
from .mobilemessage import MobileMessageAdapter

_transports: Dict[str, SmsTransportAdapter] = {
    "simulator": FakeTransportAdapter(),
    "mobilemessage": MobileMessageAdapter()
}

def get_transport_adapter(transport_type: str) -> SmsTransportAdapter:
    """Resolve the transport adapter for the given type name."""
    adapter = _transports.get(transport_type.lower())
    if not adapter:
        raise ValueError(f"Unknown transport type: {transport_type}")
    return adapter
