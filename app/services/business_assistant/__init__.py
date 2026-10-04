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

from .confirmation import (
    ConfirmationError,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    ConfirmationSignatureError,
    DynamicFactRejectedError,
    compute_rule_payload_hash,
    compute_draft_payload_hash,
    compute_campaign_payload_hash,
    generate_confirmation_token,
    validate_static_business_knowledge,
    verify_confirmation_token,
)
from .tool_registry import (
    BusinessAssistantToolRegistry,
    ProductHelpToolRegistry,
    PRODUCT_HELP_TOOLS,
    BOOKING_AVAILABILITY_TOOLS,
    BUSINESS_KNOWLEDGE_TOOLS,
    CUSTOMER_OPERATIONS_TOOLS,
    SUPPORT_ENGINEERING_TOOLS,
    ALL_BUSINESS_ASSISTANT_TOOLS,
)

__all__ = [
    "SUPPORT_ENGINEERING_TOOLS",
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
    "BUSINESS_KNOWLEDGE_TOOLS",
    "CUSTOMER_OPERATIONS_TOOLS",
    "ALL_BUSINESS_ASSISTANT_TOOLS",
    "ConfirmationError",
    "ConfirmationExpiredError",
    "ConfirmationPayloadMismatchError",
    "ConfirmationScopeMismatchError",
    "ConfirmationSignatureError",
    "DynamicFactRejectedError",
    "compute_rule_payload_hash",
    "compute_draft_payload_hash",
    "compute_campaign_payload_hash",
    "generate_confirmation_token",
    "validate_static_business_knowledge",
    "verify_confirmation_token",
]
