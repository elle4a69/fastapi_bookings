"""Native Business Assistant persistence boundary."""

from .repository import BusinessAssistantRepository
from .runtime import (
    BusinessAssistantTextRuntime,
    TextModelClientUnavailableError,
    TextModelConfigurationError,
    TextModelExecutionError,
    TextModelProviderRequestError,
)
from .service import (
    BusinessAssistantService,
    BusinessAssistantStorageUnavailableError,
    RealtimeTurnResult,
    TextTurnInProgressError,
    TextTurnResult,
    TicketCreateResult,
)
from .tickets import TicketContentSafetyError
from .idempotency import IdempotencyKeyConflictError
from .realtime import (
    BusinessAssistantRealtimeRuntime,
    RealtimeConfigurationError,
    RealtimeInvalidSdpError,
    RealtimeProviderUnavailableError,
)

__all__ = [
    "BusinessAssistantRepository",
    "BusinessAssistantService",
    "BusinessAssistantStorageUnavailableError",
    "BusinessAssistantTextRuntime",
    "TextModelClientUnavailableError",
    "TextModelConfigurationError",
    "TextModelExecutionError",
    "TextModelProviderRequestError",
    "TextTurnInProgressError",
    "RealtimeTurnResult",
    "TextTurnResult",
    "TicketContentSafetyError",
    "TicketCreateResult",
    "IdempotencyKeyConflictError",
    "BusinessAssistantRealtimeRuntime",
    "RealtimeConfigurationError",
    "RealtimeInvalidSdpError",
    "RealtimeProviderUnavailableError",
]
