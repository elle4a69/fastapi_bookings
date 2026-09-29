"""Server-Enforced Live Tool Framework for the Assistant Platform.

Provides strictly scoped, read-only tools for live availability calculation,
travel quoting, service lookup, provider lookup, and address validation.
Guarantees that LLM tool calls cannot specify, spoof, or override tenant or
provider scoping boundaries.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from .runtime_context import RuntimeContext, ToolExecution

logger = logging.getLogger(__name__)

# Permitted read-only live tools
ALLOWED_TOOL_NAMES = {
    "check_availability",
    "quote_travel",
    "service_lookup",
    "provider_lookup",
    "address_validation",
}


# ===========================================================================
# Tool Implementations (Server-Enforced Scoping)
# ===========================================================================

def check_availability_tool(
    context: RuntimeContext,
    service_id: int,
    start_date: str,
    end_date: str,
    service_mode: str = "in_call",
    destination_address: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Check availability slots using the authoritative 5-segment availability engine.

    Enforces tenant_id and provider_id from context server-side.
    """
    if db is None:
        return {"error": "Database session required for availability checking.", "success": False}

    from ...models.service import Service
    from ...models.provider import Provider
    from ..booking.availability_service import get_available_slots

    # 1. Authoritative Tenant Scoping for Service
    service = (
        db.query(Service)
        .filter(
            Service.id == service_id,
            Service.tenant_id == context.tenant_id,
            Service.active.is_(True),
            Service.deleted_at.is_(None),
        )
        .first()
    )
    if not service:
        return {
            "error": f"Service id {service_id} not found or unauthorized for tenant {context.tenant_id}.",
            "success": False,
        }

    # 2. Authoritative Provider Selection
    provider_id = context.provider_id
    if provider_id is not None:
        prov = (
            db.query(Provider)
            .filter(
                Provider.id == provider_id,
                Provider.tenant_id == context.tenant_id,
                Provider.active.is_(True),
                Provider.deleted_at.is_(None),
            )
            .first()
        )
        if not prov:
            return {
                "error": f"Provider id {provider_id} not found or unauthorized for tenant {context.tenant_id}.",
                "success": False,
            }
    else:
        # Pick default active provider for tenant
        prov = (
            db.query(Provider)
            .filter(
                Provider.tenant_id == context.tenant_id,
                Provider.active.is_(True),
                Provider.deleted_at.is_(None),
            )
            .first()
        )
        if not prov:
            return {"error": "No active providers configured for this tenant.", "success": False}
        provider_id = prov.id

    # 3. Date range parsing & clamping (max 7 days per call)
    try:
        dt_start = date.fromisoformat(start_date)
        dt_end = date.fromisoformat(end_date)
    except Exception as e:
        return {"error": f"Invalid date format (must be YYYY-MM-DD): {e}", "success": False}

    if dt_end < dt_start:
        return {"error": "end_date must be greater than or equal to start_date", "success": False}

    max_end = dt_start + timedelta(days=7)
    if dt_end > max_end:
        dt_end = max_end

    results = []
    curr = dt_start
    while curr <= dt_end:
        date_dt = datetime.combine(curr, datetime.min.time()).replace(tzinfo=timezone.utc)
        try:
            slots = get_available_slots(
                db=db,
                service_duration=service.duration,
                provider_id=provider_id,
                date=date_dt,
                service_id=service.id,
                service_mode=service_mode,
                service_address=destination_address,
            )
            formatted_slots = [
                {
                    "start": s["start"].isoformat() if isinstance(s.get("start"), datetime) else str(s.get("start")),
                    "end": s["end"].isoformat() if isinstance(s.get("end"), datetime) else str(s.get("end")),
                }
                for s in slots
            ]
            results.append({"date": curr.isoformat(), "slots": formatted_slots})
        except Exception as exc:
            logger.error("Availability calculation error for %s: %s", curr, exc)
            results.append({"date": curr.isoformat(), "slots": [], "error": str(exc)})
        curr += timedelta(days=1)

    return {
        "success": True,
        "service": {"id": service.id, "name": service.name, "duration": service.duration},
        "provider": {"id": prov.id, "name": prov.name},
        "service_mode": service_mode,
        "availability": results,
    }


async def quote_travel_tool_async(
    context: RuntimeContext,
    origin_location_id: int,
    destination_address: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Quote commercial travel fee using travel_service with server-enforced tenant scoping."""
    if db is None:
        return {"error": "Database session required for travel quotation.", "success": False}

    from ...models.tenant import Tenant
    from ...models.provider import Provider
    from ...models.location import Location
    from ..routing.travel_service import TravelCalculationService

    # 1. Authoritative Tenant & Location Scoping
    tenant = db.query(Tenant).filter(Tenant.id == context.tenant_id).first()
    if not tenant:
        return {"error": f"Tenant {context.tenant_id} not found.", "success": False}

    location = (
        db.query(Location)
        .filter(
            Location.id == origin_location_id,
            Location.tenant_id == context.tenant_id,
        )
        .first()
    )
    if not location:
        return {
            "error": f"Origin location {origin_location_id} not found or unauthorized for tenant {context.tenant_id}.",
            "success": False,
        }

    # 2. Authoritative Provider Scoping
    provider = None
    if context.provider_id:
        provider = (
            db.query(Provider)
            .filter(
                Provider.id == context.provider_id,
                Provider.tenant_id == context.tenant_id,
            )
            .first()
        )
    if not provider:
        provider = (
            db.query(Provider)
            .filter(
                Provider.tenant_id == context.tenant_id,
                Provider.allow_out_call.is_(True),
            )
            .first()
        )
    if not provider:
        return {"error": "No out-call provider available for this tenant.", "success": False}

    service_calc = TravelCalculationService()
    try:
        quote = await service_calc.calculate_chargeable_travel(
            tenant=tenant,
            provider=provider,
            client_destination=destination_address,
        )
        return {
            "success": True,
            "distance_km": quote.distance_km,
            "travel_fee": quote.travel_fee,
            "base_surcharge": quote.base_surcharge,
            "distance_fee": quote.distance_fee,
            "within_radius": quote.within_radius,
            "max_radius_km": quote.max_radius_km,
            "reason": quote.reason,
            "disclaimer": quote.disclaimer,
            "origin_address": quote.origin_address,
            "destination_address": quote.destination_address,
        }
    except Exception as exc:
        logger.error("Travel quote calculation error: %s", exc)
        return {"error": f"Failed to calculate travel: {exc}", "success": False}
    finally:
        await service_calc.close()


def quote_travel_tool(
    context: RuntimeContext,
    origin_location_id: int,
    destination_address: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Synchronous entrypoint for quote_travel_tool."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Running inside an active event loop (e.g. pytest-asyncio or async webserver)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                quote_travel_tool_async(context, origin_location_id, destination_address, db=db),
            )
            return future.result()
    else:
        return asyncio.run(
            quote_travel_tool_async(context, origin_location_id, destination_address, db=db)
        )


def service_lookup_tool(
    context: RuntimeContext,
    service_id_or_slug: Union[int, str],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Query active services belonging strictly to the tenant in context."""
    if db is None:
        return {"error": "Database session required for service lookup.", "success": False}

    from ...models.service import Service

    query = db.query(Service).filter(
        Service.tenant_id == context.tenant_id,
        Service.active.is_(True),
        Service.deleted_at.is_(None),
    )

    query_str = str(service_id_or_slug).strip()
    if query_str.isdigit():
        query = query.filter(Service.id == int(query_str))
    else:
        query = query.filter(Service.name.ilike(f"%{query_str}%"))

    services = query.all()
    results = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "duration": s.duration,
            "price": float(s.price) if s.price is not None else None,
            "allow_in_call": getattr(s, "allow_in_call", True),
            "allow_out_call": getattr(s, "allow_out_call", False),
            "deposit_amount": float(s.deposit_amount) if getattr(s, "deposit_amount", None) is not None else 0.0,
        }
        for s in services
    ]

    return {
        "success": True,
        "count": len(results),
        "services": results,
    }


def provider_lookup_tool(
    context: RuntimeContext,
    provider_id_or_slug: Union[int, str],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Query active providers belonging strictly to the tenant in context."""
    if db is None:
        return {"error": "Database session required for provider lookup.", "success": False}

    from ...models.provider import Provider

    query = db.query(Provider).filter(
        Provider.tenant_id == context.tenant_id,
        Provider.active.is_(True),
        Provider.deleted_at.is_(None),
    )

    query_str = str(provider_id_or_slug).strip()
    if query_str.isdigit():
        query = query.filter(Provider.id == int(query_str))
    else:
        query = query.filter(Provider.name.ilike(f"%{query_str}%"))

    providers = query.all()
    results = [
        {
            "id": p.id,
            "name": p.name,
            "description": getattr(p, "description", None),
            "allow_out_call": getattr(p, "allow_out_call", True),
            "out_call_radius_km": float(getattr(p, "out_call_radius_km", 25.0) or 25.0),
        }
        for p in providers
    ]

    return {
        "success": True,
        "count": len(results),
        "providers": results,
    }


def address_validation_tool(
    context: RuntimeContext,
    query: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Validate address, suburb, or postcode."""
    from ..routing.geocoding import lookup_au_postcode, KNOWN_CENTROIDS, _RUNTIME_REGISTRY

    query_clean = (query or "").strip()
    if not query_clean:
        return {"valid": False, "query": query, "error": "Query cannot be empty."}

    # 1. Test registry check
    lower_q = query_clean.lower()
    if lower_q in _RUNTIME_REGISTRY:
        coords = _RUNTIME_REGISTRY[lower_q]
        return {
            "valid": True,
            "query": query,
            "formatted_address": query_clean,
            "latitude": coords[0],
            "longitude": coords[1],
            "method": "test_registry",
        }

    # 2. Known centroids
    if lower_q in KNOWN_CENTROIDS:
        coords = KNOWN_CENTROIDS[lower_q]
        return {
            "valid": True,
            "query": query,
            "formatted_address": query_clean.title(),
            "latitude": coords[0],
            "longitude": coords[1],
            "method": "known_centroid",
        }

    # 3. AU postcodes database fast-path
    postcode_match = None
    suburb_arg = None
    if query_clean.isdigit() and len(query_clean) == 4:
        postcode_match = lookup_au_postcode(postcode=query_clean)
    else:
        # Try suburb
        postcode_match = lookup_au_postcode(suburb=query_clean)

    if postcode_match:
        return {
            "valid": True,
            "query": query,
            "suburb": postcode_match["suburb"],
            "postcode": postcode_match["postcode"],
            "state": postcode_match["state"],
            "latitude": postcode_match["latitude"],
            "longitude": postcode_match["longitude"],
            "formatted_address": f"{postcode_match['suburb']} {postcode_match['state']} {postcode_match['postcode']}",
            "method": "au_postcodes_db",
        }

    # If unrecognized
    return {
        "valid": False,
        "query": query,
        "error": f"Address or suburb '{query}' could not be resolved.",
    }


# ===========================================================================
# Tool Execution Engine with Scoping Guardrails
# ===========================================================================

class AssistantToolEngine:
    """Execution engine that executes tool calls with server-enforced scoping."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Any]] = {
            "check_availability": check_availability_tool,
            "quote_travel": quote_travel_tool,
            "service_lookup": service_lookup_tool,
            "provider_lookup": provider_lookup_tool,
            "address_validation": address_validation_tool,
        }

    def execute_tool(
        self,
        tool_name: Any,
        arguments: Any = None,
        context: Optional[RuntimeContext] = None,
        db: Optional[Session] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a tool with server-enforced tenant and provider isolation.

        Supports both instance and classmethod calls, and both (tool_name, args, context, db)
        and (db, tool_name, args, context) argument patterns.
        """
        if not isinstance(self, AssistantToolEngine):
            # Called as AssistantToolEngine.execute_tool(...) without instantiation
            engine = AssistantToolEngine()
            # If first arg is a db session: (db, tool_name, args, context)
            if hasattr(self, "query") or hasattr(self, "execute"):
                return engine._execute_tool_internal(
                    tool_name=str(tool_name),
                    arguments=arguments if isinstance(arguments, dict) else {},
                    context=context,
                    db=self,
                )
            else:
                return engine._execute_tool_internal(
                    tool_name=str(self),
                    arguments=tool_name if isinstance(tool_name, dict) else {},
                    context=arguments,
                    db=context if hasattr(context, "query") else db,
                )

        # Instance call: check if first arg was db
        if hasattr(tool_name, "query") or hasattr(tool_name, "execute"):
            return self._execute_tool_internal(
                tool_name=str(arguments),
                arguments=context if isinstance(context, dict) else {},
                context=db,
                db=tool_name,
            )

        return self._execute_tool_internal(
            tool_name=str(tool_name),
            arguments=arguments if isinstance(arguments, dict) else {},
            context=context,
            db=db,
        )

    def _execute_tool_internal(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[RuntimeContext],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        if context is None:
            return {"error": "RuntimeContext is required for tool execution.", "success": False}
        # 1. Allowlist verification
        if tool_name not in ALLOWED_TOOL_NAMES or tool_name not in self._handlers:
            err = f"Tool '{tool_name}' is not in the approved tool allowlist."
            logger.warning("Disallowed tool execution attempt: %s", tool_name)
            context.add_tool_execution(
                tool_name=tool_name,
                arguments=arguments,
                result={"error": err},
                success=False,
                error=err,
            )
            return {"error": err, "success": False}

        # 2. Strict Parameter Sanitization: Strip client/model-supplied scoping IDs
        clean_args = dict(arguments)
        stripped_params = []
        for forbidden_key in ("tenant_id", "tenant", "provider_id", "provider"):
            if forbidden_key in clean_args:
                stripped_params.append(forbidden_key)
                clean_args.pop(forbidden_key, None)

        if stripped_params:
            logger.warning(
                "Model attempted to specify forbidden scoping parameters %s. Server-enforced values will be used.",
                stripped_params,
            )
            context.set_flag("attempted_scoping_override", True)

        # 3. Dispatch to handler with authoritative context and db session
        handler = self._handlers[tool_name]
        try:
            result = handler(context=context, db=db, **clean_args)
            success = result.get("success", True) if isinstance(result, dict) else True
            err_msg = result.get("error") if isinstance(result, dict) else None

            context.add_tool_execution(
                tool_name=tool_name,
                arguments=clean_args,
                result=result,
                success=success,
                error=err_msg,
            )
            return result
        except Exception as exc:
            logger.exception("Error executing tool %s: %s", tool_name, exc)
            err_str = f"Execution error in {tool_name}: {exc}"
            context.add_tool_execution(
                tool_name=tool_name,
                arguments=clean_args,
                result={"error": err_str},
                success=False,
                error=err_str,
            )
            return {"error": err_str, "success": False}


# ===========================================================================
# OpenAI-Compatible Tool Definitions (No tenant_id or provider_id parameters)
# ===========================================================================

ASSISTANT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check real-time appointment availability slots for a service between start_date and end_date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "The ID of the service to check.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (maximum 7 days from start_date).",
                    },
                    "service_mode": {
                        "type": "string",
                        "enum": ["in_call", "out_call"],
                        "default": "in_call",
                        "description": "In-clinic (in_call) or mobile travel (out_call).",
                    },
                    "destination_address": {
                        "type": "string",
                        "description": "Client destination street address (required for out_call mode).",
                    },
                },
                "required": ["service_id", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_travel",
            "description": "Calculate commercial travel fee and road distance for mobile/out-call services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_location_id": {
                        "type": "integer",
                        "description": "Base operating location ID.",
                    },
                    "destination_address": {
                        "type": "string",
                        "description": "Client street address or suburb.",
                    },
                },
                "required": ["origin_location_id", "destination_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "service_lookup",
            "description": "Look up active services, prices, and durations offered by this business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id_or_slug": {
                        "type": "string",
                        "description": "Service ID (e.g. '12') or search term (e.g. 'haircut', 'facial').",
                    },
                },
                "required": ["service_id_or_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "provider_lookup",
            "description": "Look up active providers, bios, specialties, and travel parameters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id_or_slug": {
                        "type": "string",
                        "description": "Provider ID or provider name.",
                    },
                },
                "required": ["provider_id_or_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "address_validation",
            "description": "Validate an address, suburb, or postcode and resolve coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Address string, Australian suburb name, or 4-digit postcode.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def get_assistant_tool_definitions() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible function calling schemas for the assistant tools."""
    return list(ASSISTANT_TOOL_DEFINITIONS)
