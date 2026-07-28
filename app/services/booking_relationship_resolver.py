"""Central tenant-safe relationship compatibility queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    AddOn,
    Category,
    Location,
    LocationCategory,
    LocationProduct,
    LocationProvider,
    LocationService,
    Product,
    Provider,
    ProviderCategory,
    Service,
    ServiceAddOn,
    ServiceCategory,
    ServiceProduct,
    ServiceProvider,
)


@dataclass(frozen=True)
class RelationSpec:
    model: Any
    left: str
    right: str


RELATIONS: dict[frozenset[str], RelationSpec] = {
    frozenset(("location", "provider")): RelationSpec(LocationProvider, "location_id", "provider_id"),
    frozenset(("location", "service")): RelationSpec(LocationService, "location_id", "service_id"),
    frozenset(("location", "category")): RelationSpec(LocationCategory, "location_id", "category_id"),
    frozenset(("location", "product")): RelationSpec(LocationProduct, "location_id", "product_id"),
    frozenset(("service", "provider")): RelationSpec(ServiceProvider, "service_id", "provider_id"),
    frozenset(("service", "category")): RelationSpec(ServiceCategory, "service_id", "category_id"),
    frozenset(("service", "product")): RelationSpec(ServiceProduct, "service_id", "product_id"),
    frozenset(("service", "add_on")): RelationSpec(ServiceAddOn, "service_id", "add_on_id"),
    frozenset(("provider", "category")): RelationSpec(ProviderCategory, "provider_id", "category_id"),
}

ENTITY_MODELS = {
    "location": Location,
    "category": Category,
    "service": Service,
    "provider": Provider,
    "product": Product,
    "add_on": AddOn,
}


def _column(spec: RelationSpec, entity: str):
    if spec.left.startswith(f"{entity}_") or (entity == "add_on" and spec.left == "add_on_id"):
        return getattr(spec.model, spec.left)
    return getattr(spec.model, spec.right)


def pair_allowed(db: Session, tenant_id: int, left_type: str, left_id: int, right_type: str, right_id: int) -> bool:
    """Return symmetric universal-default compatibility for an entity pair."""
    spec = RELATIONS.get(frozenset((left_type, right_type)))
    if spec is None:
        return True
    left_col = _column(spec, left_type)
    right_col = _column(spec, right_type)
    explicit = db.query(spec.model).filter(
        spec.model.tenant_id == tenant_id,
        left_col == left_id,
        right_col == right_id,
    ).first()
    if explicit:
        return True
    left_restricted = db.query(spec.model).filter(spec.model.tenant_id == tenant_id, left_col == left_id).first() is not None
    right_restricted = db.query(spec.model).filter(spec.model.tenant_id == tenant_id, right_col == right_id).first() is not None
    return not left_restricted and not right_restricted


def get_entity(db: Session, tenant_id: int, entity: str, entity_id: int):
    model = ENTITY_MODELS[entity]
    query = db.query(model).filter(model.id == entity_id, model.tenant_id == tenant_id)
    if hasattr(model, "active"):
        query = query.filter(model.active.is_(True))
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    return query.first()


def get_valid_records(db: Session, tenant_id: int, entity: str, context: dict[str, int | None]) -> list[Any]:
    model = ENTITY_MODELS[entity]
    query = db.query(model).filter(model.tenant_id == tenant_id)
    if hasattr(model, "active"):
        query = query.filter(model.active.is_(True))
    if hasattr(model, "is_visible"):
        query = query.filter(model.is_visible.is_(True))
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    candidates = query.order_by(model.id).all()
    selected = [(kind, value) for kind, value in context.items() if value is not None and kind != entity]
    return [
        candidate
        for candidate in candidates
        if all(pair_allowed(db, tenant_id, entity, candidate.id, other, other_id) for other, other_id in selected)
    ]


def get_valid_locations(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[Location]:
    return get_valid_records(db, tenant_id, "location", context)


def get_valid_categories(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[Category]:
    return get_valid_records(db, tenant_id, "category", context)


def get_valid_services(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[Service]:
    return get_valid_records(db, tenant_id, "service", context)


def get_valid_providers(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[Provider]:
    return get_valid_records(db, tenant_id, "provider", context)


def get_valid_products(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[Product]:
    return get_valid_records(db, tenant_id, "product", context)


def get_valid_addons(db: Session, tenant_id: int, context: dict[str, int | None]) -> list[AddOn]:
    return get_valid_records(db, tenant_id, "add_on", context)
