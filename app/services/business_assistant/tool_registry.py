"""Small server-authorised product-help tool pack for the bounded text runtime."""

from __future__ import annotations

from typing import Any

from .adapters import BusinessAssistantReadAdapters


PRODUCT_HELP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "read_product_help",
            "description": "Read the current authorised setup summary for product help and onboarding.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_onboarding_progress",
            "description": "Read the current owner's durable onboarding milestones and authorised setup summary.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "strict": True,
        },
    },
)


class ProductHelpToolRegistry:
    """Execute only the scoped native reads exposed in the initial product-help pack."""

    def __init__(self, adapters: BusinessAssistantReadAdapters) -> None:
        self._adapters = adapters

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        return PRODUCT_HELP_TOOLS

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Reject unknown arguments and return one real server-authorised read result."""
        if arguments:
            return {"status": "rejected", "reason": "This read action does not accept arguments."}
        if name == "read_product_help":
            return {"status": "ok", "product_help": self._adapters.read_product_help().tool_result()}
        if name == "read_onboarding_progress":
            return {"status": "ok", "onboarding": self._adapters.read_onboarding().tool_result()}
        return {"status": "rejected", "reason": "This capability is not available in the product-help tool pack."}
