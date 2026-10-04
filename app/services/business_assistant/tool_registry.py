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

CUSTOMER_OPERATIONS_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "search_customer_conversations",
            "description": "Search authorised customer conversations within the current tenant and provider scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional search term for contact name, identifier, or message snippet.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "archived", "paused", "all"],
                        "description": "Filter by conversation status (default 'active').",
                    },
                    "provider_id": {
                        "type": "integer",
                        "description": "Optional provider ID to filter conversations. Enforced automatically if user is a provider.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of conversations to return (1-50, default 20).",
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
            "name": "get_customer_conversation_thread",
            "description": "Inspect a customer conversation thread, recent messages, and client opt-in/opt-out status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "ID of the customer conversation to inspect.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent messages to return (1-50, default 20).",
                    },
                },
                "required": ["conversation_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_customer_message_draft",
            "description": "Prepare a response message draft for an authorised customer conversation without sending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "ID of the customer conversation to respond to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Draft message response text.",
                    },
                    "request_key": {
                        "type": "string",
                        "description": "Optional idempotency key for draft creation.",
                    },
                },
                "required": ["conversation_id", "content"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign_proposal",
            "description": "Create an audience-selected campaign proposal with explainable inclusion criteria and recipient preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Campaign title or campaign objective.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Campaign message text or template.",
                    },
                    "marketing_opt_in_only": {
                        "type": "boolean",
                        "description": "Whether to only include clients who accepted marketing (default true).",
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "Whether to only include active clients (default true).",
                    },
                    "exclude_pending_holds": {
                        "type": "boolean",
                        "description": "Whether to exclude clients with pending holds/bookings (default true).",
                    },
                    "min_completed_bookings": {
                        "type": "integer",
                        "description": "Minimum number of completed bookings required for inclusion (default 0).",
                    },
                    "provider_id": {
                        "type": "integer",
                        "description": "Optional provider ID filter for prior bookings.",
                    },
                    "request_key": {
                        "type": "string",
                        "description": "Optional idempotency key for campaign proposal creation.",
                    },
                },
                "required": ["title", "content"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

SUPPORT_ENGINEERING_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a sanitised internal technical support or engineering ticket without automatic dispatch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["support", "bug", "feature", "access", "security", "upgrade"],
                        "description": "Ticket category.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Clear, concise title describing the issue or request (1-240 characters).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed explanation of the issue with all customer PII and secrets omitted.",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "critical"],
                        "description": "Ticket severity (default 'normal').",
                    },
                    "observed_behaviour": {
                        "type": "string",
                        "description": "Optional observed behaviour or error details.",
                    },
                    "affected_product_area": {
                        "type": "string",
                        "description": "Optional application area affected (e.g. 'calendar', 'checkout', 'sms', 'invoicing').",
                    },
                    "user_impact": {
                        "type": "string",
                        "description": "Optional summary of customer or business impact.",
                    },
                    "acceptance_criteria": {
                        "type": "string",
                        "description": "Optional desired outcome or acceptance criteria.",
                    },
                    "request_key": {
                        "type": "string",
                        "description": "Optional idempotency key.",
                    },
                },
                "required": ["category", "title", "description"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": "Inspect user-safe status and lifecycle events for an existing support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "ID of the support ticket to inspect.",
                    },
                },
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_support_tickets",
            "description": "List user-safe support tickets created in the current tenant scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter by ticket status (e.g. 'awaiting_engineering', 'pending_owner_approval', 'resolved').",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["support", "bug", "feature", "access", "security", "upgrade"],
                        "description": "Optional filter by ticket category.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (1-50, default 20).",
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
            "name": "request_ticket_approval",
            "description": "Request owner approval token for an elevated access or security ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "ID of the elevated ticket requiring owner approval.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional explanatory reason for the approval request.",
                    },
                },
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

WEBSITE_BUILDER_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "inspect_website_state",
            "description": "Inspect the active tenant's public website configuration, published status, active version, and pending draft proposals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_history": {
                        "type": "boolean",
                        "description": "Whether to include recent proposal history (default false).",
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
            "name": "propose_website_edit",
            "description": "Propose bounded content, layout, template, or theme edits for the tenant website. Edits remain safely in draft state and cannot publish automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief description of the proposed website modification (1-200 characters).",
                    },
                    "content_payload": {
                        "type": "object",
                        "description": "Dictionary containing proposed section modifications (hero, about, services, booking, testimonials, contact, footer) or template/theme settings.",
                    },
                    "expected_version": {
                        "type": "integer",
                        "description": "Optional expected current proposal version to enforce optimistic concurrency checks.",
                    },
                    "request_key": {
                        "type": "string",
                        "description": "Optional client-supplied idempotency key (8-128 characters).",
                    },
                },
                "required": ["title", "content_payload"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_website_edit",
            "description": "Render a full preview of proposed website changes merged with the current live website and advance the proposal state to 'preview'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "integer",
                        "description": "ID of the website proposal to preview.",
                    },
                },
                "required": ["proposal_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_website_publication",
            "description": "Request publication approval for a website proposal. Generates a cryptographic confirmation token. Publication CANNOT occur through ordinary conversational confirmation; it requires explicit owner approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "integer",
                        "description": "ID of the website proposal to request publication for.",
                    },
                },
                "required": ["proposal_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_website_version",
            "description": "Rollback the live website configuration to a previously published version with optimistic concurrency checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_version": {
                        "type": "integer",
                        "description": "Version number to rollback to.",
                    },
                    "expected_current_version": {
                        "type": "integer",
                        "description": "Optional expected current version for optimistic concurrency.",
                    },
                    "confirmation_token": {
                        "type": "string",
                        "description": "Optional cryptographic confirmation token if required.",
                    },
                },
                "required": ["target_version"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
)

ALL_BUSINESS_ASSISTANT_TOOLS: tuple[dict[str, Any], ...] = (
    *PRODUCT_HELP_TOOLS,
    *BOOKING_AVAILABILITY_TOOLS,
    *BUSINESS_KNOWLEDGE_TOOLS,
    *CUSTOMER_OPERATIONS_TOOLS,
    *SUPPORT_ENGINEERING_TOOLS,
    *WEBSITE_BUILDER_TOOLS,
)

ALL_TOOL_PACKS: tuple[str, ...] = (
    "product_help",
    "booking_availability",
    "business_knowledge",
    "customer_operations",
    "support_engineering",
    "website_builder",
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
        if "customer_operations" in self._packs:
            active.extend(CUSTOMER_OPERATIONS_TOOLS)
        if "support_engineering" in self._packs:
            active.extend(SUPPORT_ENGINEERING_TOOLS)
        if "website_builder" in self._packs:
            active.extend(WEBSITE_BUILDER_TOOLS)
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

        if name == "search_customer_conversations":
            query = arguments.get("query")
            if query is not None and not isinstance(query, str):
                return {"status": "rejected", "reason": "query must be a string."}
            status_arg = arguments.get("status")
            if status_arg is not None and not isinstance(status_arg, str):
                return {"status": "rejected", "reason": "status must be a string."}
            provider_id = arguments.get("provider_id")
            if provider_id is not None and not isinstance(provider_id, int):
                return {"status": "rejected", "reason": "provider_id must be an integer."}
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                return {"status": "rejected", "reason": "limit must be an integer between 1 and 50."}
            try:
                service = self._get_service()
                convs = service.search_customer_conversations(
                    query=query,
                    status=status_arg,
                    provider_id=provider_id,
                    limit=limit,
                )
                return {"status": "ok", "conversations": convs}
            except (ValueError, LookupError, PermissionError) as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "get_customer_conversation_thread":
            conversation_id = arguments.get("conversation_id")
            if conversation_id is None or not isinstance(conversation_id, int):
                return {"status": "rejected", "reason": "conversation_id is required and must be an integer."}
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                return {"status": "rejected", "reason": "limit must be an integer between 1 and 50."}
            try:
                service = self._get_service()
                thread = service.get_customer_conversation_thread(
                    conversation_id=conversation_id,
                    limit=limit,
                )
                return {"status": "ok", "thread": thread}
            except (LookupError, PermissionError) as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "prepare_customer_message_draft":
            conversation_id = arguments.get("conversation_id")
            if conversation_id is None or not isinstance(conversation_id, int):
                return {"status": "rejected", "reason": "conversation_id is required and must be an integer."}
            content = arguments.get("content")
            if not content or not isinstance(content, str):
                return {"status": "rejected", "reason": "content is required and must be a string."}
            request_key = arguments.get("request_key")
            if request_key is not None and not isinstance(request_key, str):
                return {"status": "rejected", "reason": "request_key must be a string."}
            try:
                service = self._get_service()
                draft, token, preview = service.prepare_customer_message_draft(
                    conversation_id=conversation_id,
                    content=content,
                    request_key=request_key,
                )
                return {
                    "status": "ok",
                    "draft": {
                        "id": draft.id,
                        "conversation_id": draft.conversation_id,
                        "content": draft.content,
                        "recipient_preview": draft.recipient_preview,
                        "status": draft.status,
                        "version": draft.version,
                        "payload_hash": draft.payload_hash,
                    },
                    "confirmation_token": token,
                    "preview": preview,
                }
            except (LookupError, PermissionError, ValueError) as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "create_campaign_proposal":
            title = arguments.get("title")
            if not title or not isinstance(title, str):
                return {"status": "rejected", "reason": "title is required and must be a string."}
            content = arguments.get("content")
            if not content or not isinstance(content, str):
                return {"status": "rejected", "reason": "content is required and must be a string."}
            marketing_opt_in_only = arguments.get("marketing_opt_in_only", True)
            if not isinstance(marketing_opt_in_only, bool):
                return {"status": "rejected", "reason": "marketing_opt_in_only must be a boolean."}
            active_only = arguments.get("active_only", True)
            if not isinstance(active_only, bool):
                return {"status": "rejected", "reason": "active_only must be a boolean."}
            exclude_pending_holds = arguments.get("exclude_pending_holds", True)
            if not isinstance(exclude_pending_holds, bool):
                return {"status": "rejected", "reason": "exclude_pending_holds must be a boolean."}
            min_completed_bookings = arguments.get("min_completed_bookings", 0)
            if not isinstance(min_completed_bookings, int):
                return {"status": "rejected", "reason": "min_completed_bookings must be an integer."}
            provider_id = arguments.get("provider_id")
            if provider_id is not None and not isinstance(provider_id, int):
                return {"status": "rejected", "reason": "provider_id must be an integer."}
            request_key = arguments.get("request_key")
            if request_key is not None and not isinstance(request_key, str):
                return {"status": "rejected", "reason": "request_key must be a string."}
            try:
                service = self._get_service()
                proposal, token, summary = service.create_campaign_proposal(
                    title=title,
                    content=content,
                    marketing_opt_in_only=marketing_opt_in_only,
                    active_only=active_only,
                    exclude_pending_holds=exclude_pending_holds,
                    min_completed_bookings=min_completed_bookings,
                    provider_id=provider_id,
                    request_key=request_key,
                )
                return {
                    "status": "ok",
                    "proposal": {
                        "id": proposal.id,
                        "title": proposal.title,
                        "content": proposal.content,
                        "recipient_count": proposal.recipient_count,
                        "status": proposal.status,
                        "version": proposal.version,
                        "payload_hash": proposal.payload_hash,
                        "target_audience_criteria": proposal.target_audience_criteria,
                    },
                    "confirmation_token": token,
                    "summary": summary,
                }
            except (ValueError, LookupError, PermissionError) as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "create_support_ticket":
            category = arguments.get("category")
            if not category or not isinstance(category, str):
                return {"status": "rejected", "reason": "category is required and must be a string."}
            title = arguments.get("title")
            if not title or not isinstance(title, str):
                return {"status": "rejected", "reason": "title is required and must be a string."}
            description = arguments.get("description")
            if not description or not isinstance(description, str):
                return {"status": "rejected", "reason": "description is required and must be a string."}
            severity = arguments.get("severity", "normal")
            if not isinstance(severity, str):
                return {"status": "rejected", "reason": "severity must be a string."}
            observed_behaviour = arguments.get("observed_behaviour")
            if observed_behaviour is not None and not isinstance(observed_behaviour, str):
                return {"status": "rejected", "reason": "observed_behaviour must be a string."}
            affected_product_area = arguments.get("affected_product_area")
            if affected_product_area is not None and not isinstance(affected_product_area, str):
                return {"status": "rejected", "reason": "affected_product_area must be a string."}
            user_impact = arguments.get("user_impact")
            if user_impact is not None and not isinstance(user_impact, str):
                return {"status": "rejected", "reason": "user_impact must be a string."}
            acceptance_criteria = arguments.get("acceptance_criteria")
            if acceptance_criteria is not None and not isinstance(acceptance_criteria, str):
                return {"status": "rejected", "reason": "acceptance_criteria must be a string."}
            request_key = arguments.get("request_key")
            if request_key is not None and not isinstance(request_key, str):
                return {"status": "rejected", "reason": "request_key must be a string."}
            try:
                service = self._get_service()
                result = service.create_or_get_ticket(
                    category=category,
                    severity=severity,
                    title=title,
                    description=description,
                    observed_behaviour=observed_behaviour,
                    affected_product_area=affected_product_area,
                    user_impact=user_impact,
                    acceptance_criteria=acceptance_criteria,
                    request_key=request_key,
                )
                t = result.ticket
                return {
                    "status": "ok",
                    "ticket": {
                        "id": t.id,
                        "category": t.category,
                        "severity": t.severity,
                        "status": t.status,
                        "title": t.title,
                        "description": t.description,
                        "observed_behaviour": t.observed_behaviour,
                        "affected_product_area": t.affected_product_area,
                        "user_impact": t.user_impact,
                        "acceptance_criteria": t.acceptance_criteria,
                        "authorisation_state": t.authorisation_state,
                        "requires_owner_approval": t.requires_owner_approval,
                        "created_at": t.created_at.isoformat(),
                    },
                    "duplicate_ticket": result.duplicate_ticket,
                    "confirmation_token": result.confirmation_token,
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "get_ticket_status":
            ticket_id = arguments.get("ticket_id")
            if ticket_id is None or not isinstance(ticket_id, int):
                return {"status": "rejected", "reason": "ticket_id is required and must be an integer."}
            try:
                status_info = self._adapters.get_ticket_handoff_status(ticket_id)
                return {"status": "ok", "ticket": status_info.tool_result()}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "list_support_tickets":
            limit = arguments.get("limit", 20)
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                return {"status": "rejected", "reason": "limit must be an integer between 1 and 50."}
            status_arg = arguments.get("status")
            if status_arg is not None and not isinstance(status_arg, str):
                return {"status": "rejected", "reason": "status must be a string."}
            category_arg = arguments.get("category")
            if category_arg is not None and not isinstance(category_arg, str):
                return {"status": "rejected", "reason": "category must be a string."}
            try:
                ticket_statuses = self._adapters.list_ticket_handoff_statuses(
                    limit=limit,
                    status=status_arg,
                    category=category_arg,
                )
                return {
                    "status": "ok",
                    "tickets": [ts.tool_result() for ts in ticket_statuses],
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "request_ticket_approval":
            ticket_id = arguments.get("ticket_id")
            if ticket_id is None or not isinstance(ticket_id, int):
                return {"status": "rejected", "reason": "ticket_id is required and must be an integer."}
            note = arguments.get("note")
            if note is not None and not isinstance(note, str):
                return {"status": "rejected", "reason": "note must be a string."}
            try:
                service = self._get_service()
                ticket, token = service.request_ticket_approval(ticket_id=ticket_id, note=note)
                return {
                    "status": "ok",
                    "ticket_id": ticket.id,
                    "ticket_status": ticket.status,
                    "authorisation_state": ticket.authorisation_state,
                    "confirmation_token": token,
                    "instructions": "Present confirmation token to tenant owner for explicit dispatch approval.",
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "inspect_website_state":
            include_history = arguments.get("include_history", False)
            if not isinstance(include_history, bool):
                return {"status": "rejected", "reason": "include_history must be a boolean."}
            try:
                state_info = self._adapters.inspect_website_state(include_history=include_history)
                return {"status": "ok", "website_state": state_info.tool_result()}
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "propose_website_edit":
            title = arguments.get("title")
            if not title or not isinstance(title, str):
                return {"status": "rejected", "reason": "title is required and must be a non-empty string."}
            content_payload = arguments.get("content_payload")
            if content_payload is None or not isinstance(content_payload, dict):
                return {"status": "rejected", "reason": "content_payload is required and must be a dictionary."}
            expected_version = arguments.get("expected_version")
            if expected_version is not None and not isinstance(expected_version, int):
                return {"status": "rejected", "reason": "expected_version must be an integer if provided."}
            request_key = arguments.get("request_key")
            if request_key is not None and not isinstance(request_key, str):
                return {"status": "rejected", "reason": "request_key must be a string if provided."}
            try:
                service = self._get_service()
                proposal = service.propose_website_edit(
                    title=title,
                    content_payload=content_payload,
                    expected_version=expected_version,
                    request_key=request_key,
                )
                return {
                    "status": "ok",
                    "proposal": {
                        "id": proposal.id,
                        "title": proposal.title,
                        "version": proposal.version,
                        "status": proposal.status,
                        "payload_hash": proposal.payload_hash,
                        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
                    },
                    "instructions": "Proposal created in 'draft' status. Preview or request publication approval to proceed.",
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "preview_website_edit":
            proposal_id = arguments.get("proposal_id")
            if proposal_id is None or not isinstance(proposal_id, int):
                return {"status": "rejected", "reason": "proposal_id is required and must be an integer."}
            try:
                service = self._get_service()
                proposal, preview = service.preview_website_edit(proposal_id)
                return {
                    "status": "ok",
                    "proposal_id": proposal.id,
                    "version": proposal.version,
                    "proposal_status": proposal.status,
                    "preview": preview,
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "request_website_publication":
            proposal_id = arguments.get("proposal_id")
            if proposal_id is None or not isinstance(proposal_id, int):
                return {"status": "rejected", "reason": "proposal_id is required and must be an integer."}
            try:
                service = self._get_service()
                proposal, token = service.request_website_publication(proposal_id)
                return {
                    "status": "ok",
                    "proposal_id": proposal.id,
                    "version": proposal.version,
                    "proposal_status": proposal.status,
                    "confirmation_token": token,
                    "instructions": "Present confirmation token to tenant owner for explicit publication approval. Automatic publication from conversational confirmation alone is prohibited.",
                }
            except Exception as exc:
                return {"status": "rejected", "reason": str(exc)}

        if name == "rollback_website_version":
            target_version = arguments.get("target_version")
            if target_version is None or not isinstance(target_version, int):
                return {"status": "rejected", "reason": "target_version is required and must be an integer."}
            expected_current_version = arguments.get("expected_current_version")
            if expected_current_version is not None and not isinstance(expected_current_version, int):
                return {"status": "rejected", "reason": "expected_current_version must be an integer."}
            confirmation_token = arguments.get("confirmation_token")
            if confirmation_token is not None and not isinstance(confirmation_token, str):
                return {"status": "rejected", "reason": "confirmation_token must be a string."}
            try:
                service = self._get_service()
                rollback = service.rollback_website_version(
                    target_version=target_version,
                    confirmation_token=confirmation_token,
                    expected_current_version=expected_current_version,
                )
                return {
                    "status": "ok",
                    "rollback_proposal": {
                        "id": rollback.id,
                        "version": rollback.version,
                        "status": rollback.status,
                        "rollback_version": rollback.rollback_version,
                        "published_at": rollback.published_at.isoformat() if rollback.published_at else None,
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
