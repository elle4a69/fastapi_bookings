"""Central Variable Registry for the Assistant Platform.

Provides secure, tenant-scoped interpolation of dynamic runtime and system
variables into prompt templates without risking cross-tenant data leakage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


class VariableDefinition(BaseModel):
    """Metadata and resolver for a template variable."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    source: str  # "system", "database", "session", "tool"
    scope: str  # "system", "tenant", "provider", "conversation"
    resolver_func: Callable[[RuntimeContext, Optional[Session]], Any]
    ttl_seconds: Optional[int] = None
    description: str = ""


class VariableRegistry:
    """Registry managing standard and custom variables for prompt interpolation."""

    def __init__(self) -> None:
        self._variables: Dict[str, VariableDefinition] = {}

    def register(self, var_def: VariableDefinition) -> None:
        """Register a variable definition."""
        self._variables[var_def.name] = var_def

    def get(self, name: str) -> Optional[VariableDefinition]:
        """Retrieve a variable definition by name."""
        return self._variables.get(name)

    def list_variables(self) -> List[VariableDefinition]:
        """Return all registered variable definitions."""
        return list(self._variables.values())

    def resolve_variable(
        self,
        name: str,
        context: RuntimeContext,
        db: Optional[Session] = None,
    ) -> Tuple[bool, Any]:
        """Resolve a variable value safely.

        Returns:
            Tuple of (is_resolved, value). If variable is unknown or resolution
            encounters an error, is_resolved is False.
        """
        var_def = self._variables.get(name)
        if not var_def:
            return False, None

        try:
            val = var_def.resolver_func(context, db)
            return True, val
        except Exception as exc:
            logger.warning("Failed to resolve variable '%s': %s", name, exc)
            return False, None

    def interpolate(
        self,
        template: str,
        context: RuntimeContext,
        db: Optional[Session] = None,
        unresolved_vars: Optional[List[str]] = None,
    ) -> str:
        """Interpolate all recognizable {{variable_name}} tokens in template.

        Unknown variables fail gracefully and are left untouched in the output.
        Optionally records unresolvable variables into `unresolved_vars`.
        """
        pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

        def _replacer(match: re.Match) -> str:
            var_name = match.group(1)
            is_resolved, val = self.resolve_variable(var_name, context, db)
            if is_resolved and val is not None:
                return str(val)
            if unresolved_vars is not None:
                unresolved_vars.append(var_name)
            return match.group(0)  # leave untouched

        return pattern.sub(_replacer, template)


# Standard Resolvers with strict server-side tenant scoping
# ---------------------------------------------------------------------------

def _resolve_business_name(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve tenant's business name from DB or context."""
    if db is not None:
        from ...models.tenant import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == context.tenant_id).first()
        if tenant and tenant.name:
            return tenant.name
    return "Our Business"


def _resolve_provider_name(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve assigned provider's name scoped to tenant."""
    if context.provider_id and db is not None:
        from ...models.provider import Provider
        provider = (
            db.query(Provider)
            .filter(
                Provider.id == context.provider_id,
                Provider.tenant_id == context.tenant_id,
                Provider.deleted_at.is_(None),
            )
            .first()
        )
        if provider and provider.name:
            return provider.name
    return "Our Provider" if context.provider_id else ""


def _resolve_location_name(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve location name from context or DB."""
    if context.location and context.location.name:
        return context.location.name
    if context.location and context.location.id and db is not None:
        from ...models.location import Location
        loc = (
            db.query(Location)
            .filter(
                Location.id == context.location.id,
                Location.tenant_id == context.tenant_id,
            )
            .first()
        )
        if loc and loc.name:
            return loc.name
    return ""


def _resolve_location_address(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve location address from context or DB."""
    if context.location and context.location.address:
        return context.location.address
    if context.location and context.location.id and db is not None:
        from ...models.location import Location
        loc = (
            db.query(Location)
            .filter(
                Location.id == context.location.id,
                Location.tenant_id == context.tenant_id,
            )
            .first()
        )
        if loc and loc.address:
            return loc.address
    return ""


def _resolve_channel(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve channel type."""
    return context.channel_type or "sms"


def _get_context_datetime(context: RuntimeContext) -> datetime:
    tz_str = "UTC"
    if context.location and context.location.timezone:
        tz_str = context.location.timezone
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz)


def _resolve_current_date(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve current date formatted for the location timezone."""
    now_dt = _get_context_datetime(context)
    return now_dt.strftime("%A, %B %d, %Y")


def _resolve_current_time(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve current time formatted for the location timezone."""
    now_dt = _get_context_datetime(context)
    return now_dt.strftime("%I:%M %p %Z").strip()


def _resolve_booking_link(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve tenant booking URL safely."""
    subdomain = "book"
    if db is not None:
        from ...models.tenant import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == context.tenant_id).first()
        if tenant and tenant.subdomain:
            subdomain = tenant.subdomain
    link = f"https://{subdomain}.fastapibookings.com/book"
    if context.provider_id:
        link += f"?provider_id={context.provider_id}"
    return link


def _resolve_service_area(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve service area name from context, location, or tenant."""
    if context.location and getattr(context.location, "name", None):
        return context.location.name
    return "our service area"


def _resolve_cancellation_window(context: RuntimeContext, db: Optional[Session]) -> str:
    """Resolve standard cancellation window."""
    return "24 hours"


def create_default_variable_registry() -> VariableRegistry:
    """Instantiate and populate the central registry with standard variables."""
    reg = VariableRegistry()
    reg.register(
        VariableDefinition(
            name="business_name",
            source="database",
            scope="tenant",
            resolver_func=_resolve_business_name,
            description="Tenant business name.",
        )
    )
    reg.register(
        VariableDefinition(
            name="provider_name",
            source="database",
            scope="provider",
            resolver_func=_resolve_provider_name,
            description="Assigned provider name.",
        )
    )
    reg.register(
        VariableDefinition(
            name="location_name",
            source="database",
            scope="tenant",
            resolver_func=_resolve_location_name,
            description="Operational location name.",
        )
    )
    reg.register(
        VariableDefinition(
            name="location_address",
            source="database",
            scope="tenant",
            resolver_func=_resolve_location_address,
            description="Operational location street address.",
        )
    )
    reg.register(
        VariableDefinition(
            name="channel",
            source="session",
            scope="conversation",
            resolver_func=_resolve_channel,
            description="Active communication channel (e.g. sms, whatsapp).",
        )
    )
    reg.register(
        VariableDefinition(
            name="current_date",
            source="system",
            scope="system",
            resolver_func=_resolve_current_date,
            description="Current calendar date in location timezone.",
        )
    )
    reg.register(
        VariableDefinition(
            name="current_time",
            source="system",
            scope="system",
            resolver_func=_resolve_current_time,
            description="Current local time in location timezone.",
        )
    )
    reg.register(
        VariableDefinition(
            name="booking_link",
            source="database",
            scope="tenant",
            resolver_func=_resolve_booking_link,
            description="Canonical online booking URL.",
        )
    )
    reg.register(
        VariableDefinition(
            name="service_area",
            source="database",
            scope="tenant",
            resolver_func=_resolve_service_area,
            description="Operational service area or region.",
        )
    )
    reg.register(
        VariableDefinition(
            name="cancellation_window",
            source="system",
            scope="tenant",
            resolver_func=_resolve_cancellation_window,
            description="Required advance cancellation notification window.",
        )
    )
    return reg


default_variable_registry = create_default_variable_registry()


def normalize_template_variables(text: str) -> str:
    """Re-export of canonical template variable normalizer."""
    from ..knowledge.classifier import normalize_template_variables as _norm
    return _norm(text)

