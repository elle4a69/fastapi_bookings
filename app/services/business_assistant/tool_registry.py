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

BUSINESS_KNOWLEDGE_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "list_curator_questions",
            "description": "List pending or unresolved curator questions requiring business policy guidance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "resolved", "all"],
                        "description": "Filter by proposal status (default: 'pending').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (1-50, default 20).",
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
            "name": "draft_business_rule",
            "description": "Draft a business rule or policy, validate against dynamic facts, and return the assistant's interpretation and confirmation token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_key": {
                        "type": "string",
                        "description": "Unique key or slug for the rule (e.g. 'cancellation_policy', 'pet_policy').",
                    },
                    "content": {
                        "type": "string",
                        "description": "The durable rule description or policy text. Dynamic operational facts (prices, slots, dates) are forbidden.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category for the rule (default: 'policy').",
                    },
                    "curator_item_id": {
                        "type": "integer",
                        "description": "Optional ID of a curator proposal being resolved by this rule.",
                    },
                },
                "required": ["memory_key", "content"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_business_rule",
            "description": "Inspect a drafted or active business rule and its stored assistant interpretation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_key": {
                        "type": "string",
                        "description": "Key or slug of the business rule to inspect.",
                    },
                },
                "required": ["memory_key"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "activate_business_rule",
            "description": "Activate a previously drafted business rule using an authoritative confirmation token bound to its exact version and payload hash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_key": {
                        "type": "string",
                        "description": "Key of the business rule to activate.",
                    },
                    "confirmation_token": {
                        "type": "string",
                        "description": "Authoritative confirmation token received when drafting the rule.",
                    },
                },
                "required": ["memory_key", "confirmation_token"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_curator_question",
            "description": "Resolve, dismiss, or reject a curator question without drafting a rule.",
            "parameters": {
                "type": "object",
                "properties": {
                    "curator_item_id": {
                        "type": "integer",
                        "description": "ID of the curator question to resolve.",
                    },
                    "resolution": {
                        "type": "string",
                        "enum": ["resolved", "dismissed", "rejected"],
                        "description": "Resolution status (default: 'resolved').",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional explanatory note for the resolution.",
                    },
                },
                "required": ["curator_item_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

ALL_BUSINESS_ASSISTANT_TOOLS: tuple[dict[str, Any], ...] = (
    *PRODUCT_HELP_TOOLS,
    *BOOKING_AVAILABILITY_TOOLS,
    *BUSINESS_KNOWLEDGE_TOOLS,
)


class BusinessAssistantToolRegistry:
    """Execute server-authorised tools across modular tool packs."""

    def __init__(
        self,
        adapters: BusinessAssistantReadAdapters,
        *,
        service: Optional[Any] = None,
        packs: tuple[str, ...] = ("product_help", "booking_availability"),
    ) -> None:
        self._adapters = adapters
        self._service = service
        self._packs = packs

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        from .service import BusinessAssistantService

        return BusinessAssistantService(
            self._adapters._db,
            self._adapters._tenant_id,
            self._adapters._user_id,
        )

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        active: list[dict[str, Any]] = []
        if "product_help" in self._packs:
            active.extend(PRODUCT_HELP_TOOLS)
        if "booking_availability" in self._packs:
            active.extend(BOOKING_AVAILABILITY_TOOLS)
        if "business_knowledge" in self._packs:
            active.extend(BUSINESS_KNOWLEDGE_TOOLS)
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

        if name == "list_curator_questions":
            status_filter = arguments.get("status", "pending")
            if not isinstance(status_filter, str) or status_filter not in ("pending", "resolved", "all"):
                return {"status": "rejected", "reason": "status must be one of 'pending', 'resolved', 'all'."}
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                return {"status": "rejected", "reason": "limit must be an integer between 1 and 50."}
            try:
                service = self._get_service()
                questions = service.list_curator_questions(status=status_filter, limit=limit)
                return {
                    "status": "ok",
                    "questions": [
                        {
                            "id": q.id,
                            "category": q.category,
                            "user_query": q.user_query,
                            "proposed_response": q.proposed_response,
                            "reason_code": q.reason_code,
                            "status": q.status,
                            "confidence_score": q.confidence_score,
                            "created_at": q.created_at.isoformat() if q.created_at else None,
                        }
                        for q in questions
                    ],
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "draft_business_rule":
            memory_key = arguments.get("memory_key")
            content = arguments.get("content")
            if not memory_key or not isinstance(memory_key, str):
                return {"status": "rejected", "reason": "memory_key is required and must be a string."}
            if not content or not isinstance(content, str):
                return {"status": "rejected", "reason": "content is required and must be a string."}
            category = arguments.get("category", "policy")
            if not isinstance(category, str):
                return {"status": "rejected", "reason": "category must be a string."}
            curator_item_id = arguments.get("curator_item_id")
            if curator_item_id is not None and not isinstance(curator_item_id, int):
                return {"status": "rejected", "reason": "curator_item_id must be an integer."}
            try:
                service = self._get_service()
                memory, interpretation, token, hash_val = service.draft_business_rule(
                    memory_key=memory_key,
                    content=content,
                    category=category,
                    curator_item_id=curator_item_id,
                )
                return {
                    "status": "ok",
                    "draft": {
                        "id": memory.id,
                        "memory_key": memory.memory_key,
                        "content": memory.content,
                        "category": memory.category,
                        "status": memory.status,
                        "version": memory.version,
                        "payload_hash": hash_val,
                    },
                    "interpretation": interpretation,
                    "confirmation_token": token,
                    "payload_hash": hash_val,
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "get_business_rule":
            memory_key = arguments.get("memory_key")
            if not memory_key or not isinstance(memory_key, str):
                return {"status": "rejected", "reason": "memory_key is required and must be a string."}
            try:
                service = self._get_service()
                memory = service.get_business_rule(memory_key)
                return {
                    "status": "ok",
                    "rule": {
                        "id": memory.id,
                        "memory_key": memory.memory_key,
                        "content": memory.content,
                        "interpretation": memory.interpretation,
                        "category": memory.category,
                        "status": memory.status,
                        "version": memory.version,
                        "payload_hash": memory.payload_hash,
                        "created_at": memory.created_at.isoformat() if memory.created_at else None,
                        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
                        "activated_at": memory.activated_at.isoformat() if memory.activated_at else None,
                    },
                }
            except LookupError as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "activate_business_rule":
            memory_key = arguments.get("memory_key")
            confirmation_token = arguments.get("confirmation_token")
            if not memory_key or not isinstance(memory_key, str):
                return {"status": "rejected", "reason": "memory_key is required and must be a string."}
            if not confirmation_token or not isinstance(confirmation_token, str):
                return {"status": "rejected", "reason": "confirmation_token is required and must be a string."}
            try:
                service = self._get_service()
                activated = service.activate_business_rule(
                    id_or_key=memory_key,
                    confirmation_token=confirmation_token,
                )
                return {
                    "status": "ok",
                    "rule": {
                        "id": activated.id,
                        "memory_key": activated.memory_key,
                        "status": activated.status,
                        "version": activated.version,
                        "activated_at": activated.activated_at.isoformat() if activated.activated_at else None,
                    },
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "resolve_curator_question":
            curator_item_id = arguments.get("curator_item_id")
            if curator_item_id is None or not isinstance(curator_item_id, int):
                return {"status": "rejected", "reason": "curator_item_id is required and must be an integer."}
            resolution = arguments.get("resolution", "resolved")
            if resolution not in ("resolved", "dismissed", "rejected"):
                return {"status": "rejected", "reason": "resolution must be 'resolved', 'dismissed', or 'rejected'."}
            note = arguments.get("note")
            if note is not None and not isinstance(note, str):
                return {"status": "rejected", "reason": "note must be a string."}
            try:
                service = self._get_service()
                resolved = service.resolve_curator_question(
                    curator_item_id=curator_item_id,
                    resolution=resolution,
                    note=note,
                )
                return {
                    "status": "ok",
                    "resolved_item": {
                        "id": resolved.id,
                        "status": resolved.status,
                        "resolution_code": resolved.resolution_code,
                    },
                }
            except Exception as exc:
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
