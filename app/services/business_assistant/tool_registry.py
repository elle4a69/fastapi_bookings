"""Modular server-authorised tool packs and execution engine for Business Assistant."""

from __future__ import annotations

from typing import Any, Optional

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
    {
        "type": "function",
        "function": {
            "name": "read_system_settings",
            "description": "Read safe, non-secret tenant settings, enabled modules, and business operational rules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "setting_key": {
                        "type": "string",
                        "description": "Optional specific safe setting key to inspect (e.g. 'enabled_modules', 'timezone', 'subscription_tier', 'assistant_policy'). If omitted, returns all safe settings.",
                    }
                },
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

BOOKING_AVAILABILITY_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List available bookable services in the current tenant with duration, pricing, and modes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Whether to only list active services (default true).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of services to return (1-50, default 20).",
                    },
                },
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_providers",
            "description": "List providers/staff delivering services in the current tenant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "Optional service ID to filter providers eligible to deliver that service.",
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "Whether to only list active providers (default true).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of providers to return (1-50, default 20).",
                    },
                },
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_slot_availability",
            "description": "Check live real-time available appointment slots for a service, date, and optional provider/location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "ID of the service to check availability for.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date to check in YYYY-MM-DD ISO format.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Optional end date to check (YYYY-MM-DD, max 7 days from start_date). Defaults to start_date.",
                    },
                    "provider_id": {
                        "type": "integer",
                        "description": "Optional provider ID to restrict availability to a specific provider.",
                    },
                    "location_id": {
                        "type": "integer",
                        "description": "Optional location ID to restrict availability to a specific location.",
                    },
                    "service_mode": {
                        "type": "string",
                        "enum": ["in_call", "out_call"],
                        "description": "Service mode: 'in_call' (default) or 'out_call'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of slots to return (1-50, default 20).",
                    },
                },
                "required": ["service_id", "start_date"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

ALL_BUSINESS_ASSISTANT_TOOLS: tuple[dict[str, Any], ...] = (
    *PRODUCT_HELP_TOOLS,
    *BOOKING_AVAILABILITY_TOOLS,
)


class BusinessAssistantToolRegistry:
    """Execute server-authorised tools across modular tool packs."""

    def __init__(
        self,
        adapters: BusinessAssistantReadAdapters,
        *,
        packs: tuple[str, ...] = ("product_help", "booking_availability"),
    ) -> None:
        self._adapters = adapters
        self._packs = packs

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        active: list[dict[str, Any]] = []
        if "product_help" in self._packs:
            active.extend(PRODUCT_HELP_TOOLS)
        if "booking_availability" in self._packs:
            active.extend(BOOKING_AVAILABILITY_TOOLS)
        return tuple(active)

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate tool membership, arguments, and dispatch to server-authorised adapters."""
        if not isinstance(arguments, dict):
            return {"status": "rejected", "reason": "Arguments must be a valid JSON dictionary."}

        # Check if the tool is in enabled packs
        active_names = {tool["function"]["name"] for tool in self.schemas}
        if name not in active_names:
            return {"status": "rejected", "reason": f"Tool '{name}' is not available in the active tool packs."}

        # Dispatch based on tool name
        if name == "read_product_help":
            if arguments:
                return {"status": "rejected", "reason": "This read action does not accept arguments."}
            return {"status": "ok", "product_help": self._adapters.read_product_help().tool_result()}

        if name == "read_onboarding_progress":
            if arguments:
                return {"status": "rejected", "reason": "This read action does not accept arguments."}
            return {"status": "ok", "onboarding": self._adapters.read_onboarding().tool_result()}

        if name == "read_system_settings":
            setting_key = arguments.get("setting_key")
            if setting_key is not None and not isinstance(setting_key, str):
                return {"status": "rejected", "reason": "setting_key must be a string."}
            return self._adapters.read_system_settings(setting_key=setting_key)

        if name == "list_services":
            active_only = arguments.get("active_only", True)
            if not isinstance(active_only, bool):
                return {"status": "rejected", "reason": "active_only must be a boolean."}
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int):
                return {"status": "rejected", "reason": "limit must be an integer."}
            try:
                services = self._adapters.list_services(active_only=active_only, limit=limit)
                return {"status": "ok", "services": services}
            except (ValueError, LookupError) as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "list_providers":
            service_id = arguments.get("service_id")
            if service_id is not None and not isinstance(service_id, int):
                return {"status": "rejected", "reason": "service_id must be an integer."}
            active_only = arguments.get("active_only", True)
            if not isinstance(active_only, bool):
                return {"status": "rejected", "reason": "active_only must be a boolean."}
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int):
                return {"status": "rejected", "reason": "limit must be an integer."}
            try:
                providers = self._adapters.list_providers(
                    service_id=service_id,
                    active_only=active_only,
                    limit=limit,
                )
                return {"status": "ok", "providers": providers}
            except (ValueError, LookupError) as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "check_slot_availability":
            service_id = arguments.get("service_id")
            start_date = arguments.get("start_date")
            if service_id is None or not isinstance(service_id, int):
                return {"status": "rejected", "reason": "service_id is required and must be an integer."}
            if not start_date or not isinstance(start_date, str):
                return {"status": "rejected", "reason": "start_date is required and must be a string in YYYY-MM-DD format."}

            end_date = arguments.get("end_date")
            if end_date is not None and not isinstance(end_date, str):
                return {"status": "rejected", "reason": "end_date must be a string in YYYY-MM-DD format."}

            provider_id = arguments.get("provider_id")
            if provider_id is not None and not isinstance(provider_id, int):
                return {"status": "rejected", "reason": "provider_id must be an integer."}

            location_id = arguments.get("location_id")
            if location_id is not None and not isinstance(location_id, int):
                return {"status": "rejected", "reason": "location_id must be an integer."}

            service_mode = arguments.get("service_mode", "in_call")
            if not isinstance(service_mode, str):
                return {"status": "rejected", "reason": "service_mode must be a string."}

            limit = arguments.get("limit", 20)
            if not isinstance(limit, int):
                return {"status": "rejected", "reason": "limit must be an integer."}

            try:
                return self._adapters.check_slot_availability(
                    service_id=service_id,
                    start_date=start_date,
                    end_date=end_date,
                    provider_id=provider_id,
                    location_id=location_id,
                    service_mode=service_mode,
                    limit=limit,
                )
            except (ValueError, LookupError, PermissionError) as exc:
                return {"status": "rejected", "reason": str(exc)}

        return {"status": "rejected", "reason": f"Capability '{name}' is not supported."}


class ProductHelpToolRegistry:
    """Execute only the scoped native reads exposed in the initial product-help pack."""

    def __init__(self, adapters: BusinessAssistantReadAdapters) -> None:
        self._inner = BusinessAssistantToolRegistry(
            adapters,
            packs=("product_help",),
        )

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        # Preserve original 2 schemas for strict legacy compatibility
        return PRODUCT_HELP_TOOLS[:2]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Reject unknown arguments and return one real server-authorised read result."""
        if name not in ("read_product_help", "read_onboarding_progress"):
            return {"status": "rejected", "reason": "This capability is not available in the product-help tool pack."}
        return self._inner.execute(name, arguments)
