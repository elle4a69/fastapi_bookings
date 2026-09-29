"""FastAPI Bookings Conversational Assistant Service.

Provides typed runtime context, central variable interpolation, authoritative
10-tier prompt policy hierarchy, and server-enforced live tool execution.
"""

from .runtime_context import (
    ClientInfo,
    LocationInfo,
    NormalizedTurn,
    RuntimeContext,
    ToolExecution,
)
from .variable_registry import (
    VariableDefinition,
    VariableRegistry,
    create_default_variable_registry,
    default_variable_registry,
)
from .prompt_policy import (
    AssembledPrompt,
    DEFAULT_AGENT_POLICY_V1,
    IMMUTABLE_SAFETY_POLICY,
    MessageStyleExample,
    PromptPolicyAssembler,
    assemble_assistant_prompt,
)
from .tools import (
    ALLOWED_TOOL_NAMES,
    ASSISTANT_TOOL_DEFINITIONS,
    AssistantToolEngine,
    address_validation_tool,
    check_availability_tool,
    get_assistant_tool_definitions,
    provider_lookup_tool,
    quote_travel_tool,
    service_lookup_tool,
)

__all__ = [
    # Runtime Context
    "ClientInfo",
    "LocationInfo",
    "NormalizedTurn",
    "RuntimeContext",
    "ToolExecution",
    # Variable Registry
    "VariableDefinition",
    "VariableRegistry",
    "create_default_variable_registry",
    "default_variable_registry",
    # Prompt Policy
    "AssembledPrompt",
    "DEFAULT_AGENT_POLICY_V1",
    "IMMUTABLE_SAFETY_POLICY",
    "MessageStyleExample",
    "PromptPolicyAssembler",
    "assemble_assistant_prompt",
    # Tools
    "ALLOWED_TOOL_NAMES",
    "ASSISTANT_TOOL_DEFINITIONS",
    "AssistantToolEngine",
    "address_validation_tool",
    "check_availability_tool",
    "get_assistant_tool_definitions",
    "provider_lookup_tool",
    "quote_travel_tool",
    "service_lookup_tool",
]
