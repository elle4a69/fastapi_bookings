"""Tenant-safe generic relationship, inline-create, and aggregate editor APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models import Booking, Client, ProviderSpecialDay, ProviderWorkDay, Tenant
from ...services.booking_relationship_resolver import ENTITY_MODELS, RELATIONS, get_entity, get_valid_records


router = APIRouter(prefix="/api/admin", tags=["relationship-management"])

ALLOWED_CREATE_LINKS = {
    frozenset(("location", "category")),
    frozenset(("location", "provider")),
    frozenset(("location", "service")),
    frozenset(("location", "product")),
    frozenset(("category", "service")),
    frozenset(("category", "provider")),
    frozenset(("provider", "service")),
    frozenset(("service", "product")),
    frozenset(("service", "add_on")),
}


class CreateAndConnectRequest(BaseModel):
    record: dict[str, Any] = Field(default_factory=dict)


class RelationshipListResponse(BaseModel):
    ok: bool
    data: list[dict[str, Any]]


class RelationshipLinkResponse(BaseModel):
    ok: bool
    data: dict[str, Any]


class RelationshipEditorResponse(BaseModel):
    ok: bool
    data: dict[str, Any]


def _normalize(entity: str) -> str:
    value = entity.lower().replace("-", "_")
    aliases = {"addon": "add_on", "addons": "add_on", "add_ons": "add_on", "categories": "category", "services": "service", "providers": "provider", "locations": "location", "products": "product"}
    normalized = aliases.get(value, value.rstrip("s"))
    if normalized not in ENTITY_MODELS:
        raise HTTPException(status_code=422, detail=f"Unsupported entity type: {entity}")
    return normalized


def _serialize(record: Any) -> dict[str, Any]:
    return {column.key: getattr(record, column.key) for column in sa_inspect(record).mapper.column_attrs}


def _spec_and_columns(left_type: str, right_type: str):
    spec = RELATIONS.get(frozenset((left_type, right_type)))
    if not spec:
        raise HTTPException(status_code=422, detail="Unsupported relationship")
    columns = {spec.left.removesuffix("_id"): spec.left, spec.right.removesuffix("_id"): spec.right}
    if "add_on" in (left_type, right_type):
        columns["add_on"] = "add_on_id"
    return spec, getattr(spec.model, columns[left_type]), getattr(spec.model, columns[right_type])


def _source_or_404(db: Session, tenant_id: int, entity: str, entity_id: int):
    record = get_entity(db, tenant_id, entity, entity_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"{entity.replace('_', ' ').title()} not found")
    return record


@router.get("/relationships/{left_type}/{left_id}/{right_type}", response_model=RelationshipListResponse)
def list_explicit_relationships(
    left_type: str,
    left_id: int,
    right_type: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    left_type, right_type = _normalize(left_type), _normalize(right_type)
    _source_or_404(db, tenant.id, left_type, left_id)
    spec, left_col, right_col = _spec_and_columns(left_type, right_type)
    links = db.query(spec.model).filter(spec.model.tenant_id == tenant.id, left_col == left_id).all()
    records = [get_entity(db, tenant.id, right_type, getattr(link, right_col.key)) for link in links]
    return {"ok": True, "data": [_serialize(record) for record in records if record]}


@router.post("/relationships/{left_type}/{left_id}/{right_type}/{right_id:int}", status_code=status.HTTP_201_CREATED, response_model=RelationshipLinkResponse)
def link_records(
    left_type: str,
    left_id: int,
    right_type: str,
    right_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    left_type, right_type = _normalize(left_type), _normalize(right_type)
    _source_or_404(db, tenant.id, left_type, left_id)
    _source_or_404(db, tenant.id, right_type, right_id)
    spec, left_col, right_col = _spec_and_columns(left_type, right_type)
    existing = db.query(spec.model).filter(spec.model.tenant_id == tenant.id, left_col == left_id, right_col == right_id).first()
    if existing:
        return {"ok": True, "data": {"id": existing.id}}
    link = spec.model(tenant_id=tenant.id, **{left_col.key: left_id, right_col.key: right_id})
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"ok": True, "data": {"id": link.id}}


@router.delete("/relationships/{left_type}/{left_id}/{right_type}/{right_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_records(
    left_type: str,
    left_id: int,
    right_type: str,
    right_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    left_type, right_type = _normalize(left_type), _normalize(right_type)
    spec, left_col, right_col = _spec_and_columns(left_type, right_type)
    link = db.query(spec.model).filter(spec.model.tenant_id == tenant.id, left_col == left_id, right_col == right_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Relationship not found")
    db.delete(link)
    db.commit()


@router.post("/relationships/{left_type}/{left_id}/{right_type}/create-and-connect", status_code=status.HTTP_201_CREATED, response_model=RelationshipLinkResponse)
def create_and_connect(
    left_type: str,
    left_id: int,
    right_type: str,
    payload: CreateAndConnectRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    left_type, right_type = _normalize(left_type), _normalize(right_type)
    if frozenset((left_type, right_type)) not in ALLOWED_CREATE_LINKS:
        raise HTTPException(status_code=422, detail="Unsupported create-and-connect relationship")
    _source_or_404(db, tenant.id, left_type, left_id)
    spec, left_col, right_col = _spec_and_columns(left_type, right_type)
    model = ENTITY_MODELS[right_type]
    protected = {"id", "tenant_id", "created_at", "updated_at", "deleted_at"}
    values = {key: value for key, value in payload.record.items() if key not in protected}
    record = model(tenant_id=tenant.id, **values)
    db.add(record)
    try:
        db.flush()
        link = spec.model(tenant_id=tenant.id, **{left_col.key: left_id, right_col.key: record.id})
        db.add(link)
        db.commit()
    except (IntegrityError, TypeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="Record could not be created and connected") from exc
    db.refresh(record)
    return {"ok": True, "data": {"record": _serialize(record), "relationship_id": link.id}}


EDITOR_RELATIONS = {
    "provider": ("location", "category", "service"),
    "service": ("location", "category", "provider", "product", "add_on"),
    "location": ("provider", "category", "service", "product"),
    "category": ("location", "provider", "service"),
    "product": ("location", "service"),
}


def _editor(db: Session, tenant_id: int, entity: str, entity_id: int) -> dict[str, Any]:
    record = _source_or_404(db, tenant_id, entity, entity_id)
    relationships = {}
    context = {entity: entity_id}
    for related in EDITOR_RELATIONS[entity]:
        spec, left_col, right_col = _spec_and_columns(entity, related)
        links = db.query(spec.model).filter(spec.model.tenant_id == tenant_id, left_col == entity_id).all()
        explicit_ids = {getattr(link, right_col.key) for link in links}
        linked = [get_entity(db, tenant_id, related, record_id) for record_id in explicit_ids]
        available = [candidate for candidate in get_valid_records(db, tenant_id, related, context) if candidate.id not in explicit_ids]
        relationships[related] = {
            "linked": [_serialize(item) for item in linked if item],
            "available": [_serialize(item) for item in available],
        }
    result = {"record": _serialize(record), "relationships": relationships}
    if entity == "provider":
        result["schedule"] = {
            "workdays": [_serialize(row) for row in db.query(ProviderWorkDay).filter(ProviderWorkDay.tenant_id == tenant_id, ProviderWorkDay.provider_id == entity_id).all()],
            "special_days": [_serialize(row) for row in db.query(ProviderSpecialDay).filter(ProviderSpecialDay.tenant_id == tenant_id, ProviderSpecialDay.provider_id == entity_id).all()],
        }
    return result


@router.get("/providers/{record_id}/editor", response_model=RelationshipEditorResponse)
def provider_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return {"ok": True, "data": _editor(db, tenant.id, "provider", record_id)}


@router.get("/services/{record_id}/editor", response_model=RelationshipEditorResponse)
def service_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return {"ok": True, "data": _editor(db, tenant.id, "service", record_id)}


@router.get("/locations/{record_id}/editor", response_model=RelationshipEditorResponse)
def location_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return {"ok": True, "data": _editor(db, tenant.id, "location", record_id)}


@router.get("/categories/{record_id}/editor", response_model=RelationshipEditorResponse)
def category_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return {"ok": True, "data": _editor(db, tenant.id, "category", record_id)}


@router.get("/products/{record_id}/editor", response_model=RelationshipEditorResponse)
def product_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return {"ok": True, "data": _editor(db, tenant.id, "product", record_id)}


@router.get("/clients/{record_id}/editor", response_model=RelationshipEditorResponse)
def client_editor(record_id: int, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    client = db.query(Client).filter(Client.id == record_id, Client.tenant_id == tenant.id, Client.deleted_at.is_(None)).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    bookings = db.query(Booking).filter(Booking.tenant_id == tenant.id, Booking.client_id == record_id).order_by(Booking.start_time.desc()).all()
    return {"ok": True, "data": {"record": _serialize(client), "bookings": [_serialize(row) for row in bookings]}}
