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

from .tool_registry import (
    BusinessAssistantToolRegistry,
    ProductHelpToolRegistry,
    PRODUCT_HELP_TOOLS,
    BOOKING_AVAILABILITY_TOOLS,
    ALL_BUSINESS_ASSISTANT_TOOLS,
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
    "BusinessAssistantToolRegistry",
    "ProductHelpToolRegistry",
    "PRODUCT_HELP_TOOLS",
    "BOOKING_AVAILABILITY_TOOLS",
    "ALL_BUSINESS_ASSISTANT_TOOLS",
]
