"""Tenant- and user-scoped read adapters for bounded Business Assistant tools.

These adapters compose the existing native product-context and ticket services.
They do not accept model-selected tenant or user identifiers, do not expose
customer content, and have no mutation, worker, or external-action capability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..product_context import ProductContextAdapter
from ..repository import BusinessAssistantRepository


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
        self._repository = BusinessAssistantRepository(db, tenant_id, user_id)
        self._product_context = ProductContextAdapter(db, tenant_id)

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
