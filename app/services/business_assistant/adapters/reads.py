"""Tenant- and user-scoped read adapters for bounded Business Assistant tools.

These adapters compose the existing native product-context, scheduling, catalog,
and ticket services. They do not accept model-selected tenant or user identifiers,
do not expose customer content or secrets, and have no mutation, worker, or
external-action capability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ....models.location import Location
from ....models.provider import Provider
from ....models.service import Service
from ....models.service_provider import ServiceProvider
from ....models.tenant import Tenant
from ....models.user import User
from ....services.scheduling_service import compute_availability
from ..product_context import ProductContextAdapter
from ..repository import BusinessAssistantRepository


SAFE_TENANT_SETTING_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "subdomain",
        "timezone",
        "country",
        "subscription_tier",
        "addon_quota",
        "enabled_modules",
        "allow_in_call",
        "allow_out_call",
        "travel_charge_origin",
        "max_advance_days",
        "public_address_visibility",
        "assistant_policy",
    }
)


@dataclass(frozen=True)
class ProductHelpRead:
    """Allowlisted live setup facts safe to use for product-help responses."""

    availability: str
    enabled_modules: tuple[str, ...]
    active_services: int | None
    active_providers: int | None
    active_locations: int | None

    def tool_result(self) -> dict[str, Any]:
        """Return a JSON-compatible tool result with no tenant identifiers."""
        result = asdict(self)
        result["enabled_modules"] = list(self.enabled_modules)
        return result


@dataclass(frozen=True)
class OnboardingRead:
    """Personal onboarding status paired with the same bounded setup snapshot."""

    status: str
    completed_steps: tuple[str, ...]
    updated_at: datetime | None
    product_help: ProductHelpRead

    def tool_result(self) -> dict[str, Any]:
        """Return a JSON-compatible result that omits internal ownership fields."""
        result = asdict(self)
        result["completed_steps"] = list(self.completed_steps)
        result["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        result["product_help"] = self.product_help.tool_result()
        return result


@dataclass(frozen=True)
class SystemSettingsRead:
    """Safe allowlisted tenant settings and operational rules with secrets omitted."""

    name: str
    subdomain: str
    timezone: str
    country: Optional[str]
    subscription_tier: str
    addon_quota: int
    enabled_modules: tuple[str, ...]
    allow_in_call: bool
    allow_out_call: bool
    travel_charge_origin: str
    max_advance_days: int
    public_address_visibility: str
    assistant_policy: Optional[str]

    def tool_result(self) -> dict[str, Any]:
        """Return a JSON-compatible result with safe fields."""
        result = asdict(self)
        result["enabled_modules"] = list(self.enabled_modules)
        return result


@dataclass(frozen=True)
class ServiceSummaryRead:
    """Allowlisted bookable service representation."""

    id: int
    name: str
    description: Optional[str]
    duration: int
    price: Optional[float]
    active: bool
    allow_in_call: bool
    allow_out_call: bool
    buffer_before: int
    buffer_after: int

    def tool_result(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderSummaryRead:
    """Allowlisted provider representation."""

    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    active: bool
    allow_in_call: bool
    allow_out_call: bool

    def tool_result(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SlotAvailabilityRead:
    """Live computed slot availability results."""

    service_id: int
    service_name: str
    service_mode: str
    date_range: dict[str, str]
    total_available_slots: int
    slots: tuple[dict[str, Any], ...]

    def tool_result(self) -> dict[str, Any]:
        result = asdict(self)
        result["slots"] = list(self.slots)
        return result


@dataclass(frozen=True)
class TicketHandoffStatus:
    """User-safe, non-dispatching status for an existing scoped support ticket."""

    ticket_id: int
    category: str
    severity: str
    status: str
    created_at: datetime
    updated_at: datetime
    event_types: tuple[str, ...]

    def tool_result(self) -> dict[str, Any]:
        """Return status-only metadata, never the ticket body or worker internals."""
        result = asdict(self)
        result["event_types"] = list(self.event_types)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        return result


class BusinessAssistantReadAdapters:
    """Expose real native reads through the authoritative scoped service boundary."""

    def __init__(self, db: Session, *, tenant_id: int, user_id: int) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._repository = BusinessAssistantRepository(db, tenant_id, user_id)
        self._product_context = ProductContextAdapter(db, tenant_id)

    def _get_user(self) -> Optional[User]:
        return (
            self._db.query(User)
            .filter(
                User.id == self._user_id,
                User.tenant_id == self._tenant_id,
            )
            .first()
        )

    def _get_tenant(self) -> Tenant:
        tenant = self._db.query(Tenant).filter(Tenant.id == self._tenant_id).first()
        if not tenant:
            raise LookupError("Tenant was not found in the authenticated scope.")
        return tenant

    def read_product_help(self) -> ProductHelpRead:
        """Read current, allowlisted setup facts for the authenticated tenant."""
        context = self._product_context.read()
        return ProductHelpRead(
            availability=context.availability,
            enabled_modules=context.enabled_modules,
            active_services=context.active_services,
            active_providers=context.active_providers,
            active_locations=context.active_locations,
        )

    def read_onboarding(self) -> OnboardingRead:
        """Read the caller's durable onboarding progress and live setup snapshot."""
        progress = self._repository.get_onboarding_progress()
        return OnboardingRead(
            status=progress.status if progress else "not_started",
            completed_steps=tuple(progress.completed_steps or ()) if progress else (),
            updated_at=progress.updated_at if progress else None,
            product_help=self.read_product_help(),
        )

    def read_system_settings(self, *, setting_key: Optional[str] = None) -> dict[str, Any]:
        """Read allowlisted tenant settings and operational rules without leaking secrets."""
        tenant = self._get_tenant()
        safe_settings = SystemSettingsRead(
            name=tenant.name,
            subdomain=tenant.subdomain,
            timezone=tenant.timezone,
            country=tenant.country,
            subscription_tier=tenant.subscription_tier,
            addon_quota=tenant.addon_quota,
            enabled_modules=tuple(tenant.get_enabled_modules()),
            allow_in_call=tenant.allow_in_call,
            allow_out_call=tenant.allow_out_call,
            travel_charge_origin=str(tenant.travel_charge_origin),
            max_advance_days=tenant.max_advance_days,
            public_address_visibility=tenant.public_address_visibility,
            assistant_policy=tenant.assistant_policy,
        ).tool_result()

        if setting_key is not None:
            if setting_key not in SAFE_TENANT_SETTING_FIELDS:
                return {
                    "status": "rejected",
                    "reason": f"Setting key '{setting_key}' is not accessible or not recognized.",
                }
            return {
                "status": "ok",
                "key": setting_key,
                "value": safe_settings.get(setting_key),
            }

        return {"status": "ok", "settings": safe_settings}

    def list_services(self, *, active_only: bool = True, limit: int = 20) -> list[dict[str, Any]]:
        """List bookable services in the authenticated tenant scope."""
        if not 1 <= limit <= 50:
            raise ValueError("Service limit must be between 1 and 50.")
        query = self._db.query(Service).filter(
            Service.tenant_id == self._tenant_id,
            Service.deleted_at.is_(None),
        )
        if active_only:
            query = query.filter(Service.active.is_(True))
        services = query.order_by(Service.name.asc()).limit(limit).all()
        return [
            ServiceSummaryRead(
                id=s.id,
                name=s.name,
                description=s.description,
                duration=s.duration,
                price=float(s.price) if s.price is not None else None,
                active=s.active,
                allow_in_call=s.allow_in_call,
                allow_out_call=s.allow_out_call,
                buffer_before=s.buffer_before,
                buffer_after=s.buffer_after,
            ).tool_result()
            for s in services
        ]

    def list_providers(
        self,
        *,
        service_id: Optional[int] = None,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List providers in the authenticated tenant, respecting provider role bounds."""
        if not 1 <= limit <= 50:
            raise ValueError("Provider limit must be between 1 and 50.")
        user = self._get_user()
        user_role = (user.role or "").lower() if user else "unknown"
        user_provider_id = user.provider_id if user else None

        query = self._db.query(Provider).filter(
            Provider.tenant_id == self._tenant_id,
            Provider.deleted_at.is_(None),
        )
        if user_role == "provider" and user_provider_id:
            query = query.filter(Provider.id == user_provider_id)

        if service_id is not None:
            service = (
                self._db.query(Service)
                .filter(
                    Service.id == service_id,
                    Service.tenant_id == self._tenant_id,
                    Service.deleted_at.is_(None),
                )
                .first()
            )
            if not service:
                raise LookupError("Service was not found in the authenticated scope.")
            query = query.join(ServiceProvider, ServiceProvider.provider_id == Provider.id).filter(
                ServiceProvider.service_id == service_id
            )

        if active_only:
            query = query.filter(Provider.active.is_(True))

        providers = query.order_by(Provider.name.asc()).limit(limit).all()
        return [
            ProviderSummaryRead(
                id=p.id,
                name=p.name,
                email=p.email,
                phone=p.phone,
                active=p.active,
                allow_in_call=p.allow_in_call,
                allow_out_call=p.allow_out_call,
            ).tool_result()
            for p in providers
        ]

    def check_slot_availability(
        self,
        *,
        service_id: int,
        start_date: str,
        end_date: Optional[str] = None,
        provider_id: Optional[int] = None,
        location_id: Optional[int] = None,
        service_mode: str = "in_call",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Compute live available appointment slots using the native scheduling engine."""
        if not 1 <= limit <= 50:
            raise ValueError("Slot limit must be between 1 and 50.")
        if service_mode not in ("in_call", "out_call"):
            raise ValueError("Service mode must be 'in_call' or 'out_call'.")

        service = (
            self._db.query(Service)
            .filter(
                Service.id == service_id,
                Service.tenant_id == self._tenant_id,
                Service.deleted_at.is_(None),
            )
            .first()
        )
        if not service:
            raise LookupError("Service was not found in the authenticated scope.")

        user = self._get_user()
        user_role = (user.role or "").lower() if user else "unknown"
        user_provider_id = user.provider_id if user else None

        if user_role == "provider" and user_provider_id:
            if provider_id is not None and provider_id != user_provider_id:
                raise PermissionError("Providers may only inspect availability for their own schedule.")
            provider_id = user_provider_id

        provider = None
        if provider_id is not None:
            provider = (
                self._db.query(Provider)
                .filter(
                    Provider.id == provider_id,
                    Provider.tenant_id == self._tenant_id,
                    Provider.deleted_at.is_(None),
                )
                .first()
            )
            if not provider:
                raise LookupError("Provider was not found in the authenticated scope.")

        location = None
        if location_id is not None:
            location = (
                self._db.query(Location)
                .filter(
                    Location.id == location_id,
                    Location.tenant_id == self._tenant_id,
                )
                .first()
            )
            if not location:
                raise LookupError("Location was not found in the authenticated scope.")

        try:
            start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Invalid start_date '{start_date}'. Expected format: YYYY-MM-DD.") from exc

        if end_date:
            try:
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError(f"Invalid end_date '{end_date}'. Expected format: YYYY-MM-DD.") from exc
        else:
            end_d = start_d

        if start_d > end_d:
            raise ValueError("start_date cannot be after end_date.")
        if (end_d - start_d).days > 7:
            raise ValueError("Date range cannot exceed 7 days.")

        start_time = datetime.combine(start_d, time.min).replace(tzinfo=timezone.utc)
        end_time = datetime.combine(end_d, time.max).replace(tzinfo=timezone.utc)

        slots = compute_availability(
            self._db,
            service=service,
            provider=provider,
            location=location,
            start_time=start_time,
            end_time=end_time,
            desired_duration=service.duration,
            service_mode=service_mode,
        )

        formatted_slots = tuple(
            {
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "provider_id": (
                    s["provider"]["id"]
                    if "provider" in s and s["provider"]
                    else (provider.id if provider else None)
                ),
                "provider_name": (
                    s["provider"]["name"]
                    if "provider" in s and s["provider"]
                    else (provider.name if provider else None)
                ),
            }
            for s in slots[:limit]
        )

        return {
            "status": "ok",
            "availability": SlotAvailabilityRead(
                service_id=service.id,
                service_name=service.name,
                service_mode=service_mode,
                date_range={"start": start_date, "end": end_date or start_date},
                total_available_slots=len(slots),
                slots=formatted_slots,
            ).tool_result(),
        }

    def get_ticket_handoff_status(self, ticket_id: int) -> TicketHandoffStatus:
        """Read one ticket's user-safe status; no worker action is possible here."""
        ticket = self._repository.get_ticket(ticket_id)
        if not ticket:
            raise LookupError("Ticket was not found in the authenticated scope.")
        events = self._repository.list_ticket_events(ticket_id)
        return TicketHandoffStatus(
            ticket_id=ticket.id,
            category=ticket.category,
            severity=ticket.severity,
            status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            event_types=tuple(event.event_type for event in events),
        )

    def list_ticket_handoff_statuses(self, *, limit: int) -> list[TicketHandoffStatus]:
        """List status-only ticket records visible to the authenticated ticket owner."""
        if not 1 <= limit <= 100:
            raise ValueError("Ticket status limit must be between 1 and 100.")
        return [self.get_ticket_handoff_status(ticket.id) for ticket in self._repository.list_tickets(limit=limit)]
