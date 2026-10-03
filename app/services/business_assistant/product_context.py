"""Read-only, allowlisted native state for product help and onboarding."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...models.location import Location
from ...models.provider import Provider
from ...models.service import Service
from ...models.tenant import ADDON_MODULE_KEYS, CORE_MODULE_KEYS, Tenant


_ALLOWED_MODULE_KEYS = frozenset((*CORE_MODULE_KEYS, *ADDON_MODULE_KEYS))


@dataclass(frozen=True)
class ProductContext:
    """A non-sensitive snapshot, deliberately limited to setup-level facts."""

    availability: str
    enabled_modules: tuple[str, ...] = ()
    active_services: int | None = None
    active_providers: int | None = None
    active_locations: int | None = None

    def instruction_text(self) -> str:
        """Render only allowlisted values for the bounded text runtime."""
        if self.availability != "available":
            return (
                "Authorised product context is unavailable. Do not guess dynamic business facts; "
                "say that this information is currently unavailable."
            )
        modules = ", ".join(self.enabled_modules) or "none"
        return (
            "Authorised read-only product context for the current owner: "
            f"enabled module keys: {modules}; active setup counts: "
            f"services={self.active_services}, providers={self.active_providers}, locations={self.active_locations}. "
            "These are the only live facts available for this turn. Do not infer any other tenant data or perform changes."
        )


class ProductContextAdapter:
    """Read a small, tenant-scoped setup snapshot from authoritative ORM records."""

    def __init__(self, db: Session, tenant_id: int) -> None:
        self._db = db
        self._tenant_id = tenant_id

    def read(self) -> ProductContext:
        """Return unavailable rather than manufacture data if a source cannot be read."""
        try:
            tenant = self._db.get(Tenant, self._tenant_id)
            if not tenant:
                return ProductContext(availability="unavailable")
            active_services = self._active_count(Service)
            active_providers = self._active_count(Provider)
            active_locations = self._active_count(Location)
        except SQLAlchemyError:
            return ProductContext(availability="unavailable")
        return ProductContext(
            availability="available",
            enabled_modules=tuple(
                module_key for module_key in tenant.get_enabled_modules() if module_key in _ALLOWED_MODULE_KEYS
            ),
            active_services=active_services,
            active_providers=active_providers,
            active_locations=active_locations,
        )

    def _active_count(self, model: type[Service] | type[Provider] | type[Location]) -> int:
        query = self._db.query(func.count(model.id)).filter(model.tenant_id == self._tenant_id, model.active.is_(True))
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        return int(query.scalar() or 0)
