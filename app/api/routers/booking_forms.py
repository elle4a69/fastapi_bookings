"""Admin and narrow public-widget APIs for configurable booking forms."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, get_public_tenant
from ...core.config import settings
from ...core.state_machine import BookingStatus
from ...models import Booking, BookingForm, Client, Location, Provider, Service, Tenant
from ...schemas.embed_configuration import EmbedConfiguration, EmbedConfigurationPatch, EmbedCatalogue, EmbedAppearance, EmbedRuntimeSettings
from ...schemas.booking_form import (
    AvailabilityRequest,
    BookingFormBase,
    BookingFormCreate,
    BookingFormOut,
    BookingFormUpdate,
    DuplicateBookingFormRequest,
    ResolveRequest,
    WidgetBookingRequest,
)
from ...schemas.booking import BookingResponse
from ...services import scheduling_service
from ...services.booking_form_resolver import (
    BookingFormResolutionError,
    resolve_booking_form,
    validate_form_presets,
)
from ...services.booking_relationship_resolver import get_entity, get_valid_providers
from ...services.embed_configuration import catalogue, configuration_for_form, embed_code, runtime_manifest
from pydantic import BaseModel, Field
from typing import Optional, Any


class FormCatalogueResponse(BaseModel):
    ok: bool
    data: EmbedCatalogue


class ResolvedContext(BaseModel):
    location_id: Optional[int] = None
    provider_id: Optional[int] = None
    category_id: Optional[int] = None
    service_id: Optional[int] = None


class FormOption(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    duration: Optional[int] = None
    price: Optional[float] = None


class ResolvedBookingForm(BaseModel):
    resolved_context: ResolvedContext
    resolution_source: dict[str, str]
    visible_modules: list[str]
    options: dict[str, list[FormOption]]
    warnings: list[str]


class EmbedManifestSurface(BaseModel):
    type: str
    form_slug: str
    tenant: str
    script_url: str


class EmbedManifestFlow(BaseModel):
    module_order: list[str]
    enabled_modules: dict[str, bool]
    provider_selection_mode: str
    predefined_values: dict[str, Optional[int]]


class EmbedManifest(BaseModel):
    version: int
    surface: EmbedManifestSurface
    flow: EmbedManifestFlow
    appearance: EmbedAppearance
    runtime: EmbedRuntimeSettings


class FormEmbedData(BaseModel):
    form_slug: str
    surface_type: str
    script_url: str
    embed_code: str
    manifest: EmbedManifest


class FormPreviewData(ResolvedBookingForm):
    embed: FormEmbedData


class FormPreviewResponse(BaseModel):
    ok: bool
    data: FormPreviewData


class FormEmbedResponse(BaseModel):
    ok: bool
    data: FormEmbedData


class WidgetFormData(ResolvedBookingForm):
    form: BookingFormOut


class WidgetFormResponse(BaseModel):
    ok: bool
    data: WidgetFormData


class WidgetResolveResponse(BaseModel):
    ok: bool
    data: ResolvedBookingForm


class SearchAvailabilityProvider(BaseModel):
    id: int
    name: str


class SearchAvailabilityResource(BaseModel):
    id: int
    name: str
    quantity: int


class SearchAvailabilityService(BaseModel):
    id: int
    name: str


class SearchAvailabilityItem(BaseModel):
    start_time: str
    end_time: str
    provider: SearchAvailabilityProvider
    provider_id: Optional[int] = None
    resources: list[SearchAvailabilityResource]
    service: Optional[SearchAvailabilityService] = None


class SearchAvailabilityMeta(BaseModel):
    count: int


class WidgetAvailabilityData(BaseModel):
    resolution: ResolvedBookingForm
    slots: list[SearchAvailabilityItem]


class WidgetAvailabilityResponse(BaseModel):
    ok: bool
    data: WidgetAvailabilityData
    meta: SearchAvailabilityMeta


class WidgetRuntimeManifestResponse(BaseModel):
    ok: bool
    data: EmbedManifest


admin_router = APIRouter(prefix="/api/admin/booking-forms", tags=["booking-forms-admin"])
public_router = APIRouter(prefix="/api/public/booking-forms", tags=["booking-forms-widget"])


def _form_or_404(db: Session, tenant_id: int, form_id: int) -> BookingForm:
    form = db.query(BookingForm).filter(BookingForm.id == form_id, BookingForm.tenant_id == tenant_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Booking form not found")
    return form


def _public_form_or_404(db: Session, tenant_id: int, slug: str) -> BookingForm:
    form = db.query(BookingForm).filter(
        BookingForm.tenant_id == tenant_id,
        BookingForm.slug == slug.lower(),
        BookingForm.active.is_(True),
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Booking form not found")
    return form


def _as_model_data(payload: BookingFormBase) -> dict:
    data = payload.model_dump(mode="json")
    data["predefined_values"] = payload.predefined_values.model_dump()
    return data


def _resolution_or_422(db: Session, form: BookingForm, selections: dict | None = None) -> dict:
    try:
        return resolve_booking_form(db, form, selections)
    except BookingFormResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _embed(form: BookingForm) -> dict:
    script_url = settings.WIDGET_SCRIPT_URL
    tenant_key = form.tenant.subdomain
    manifest = runtime_manifest(form, script_url=script_url, tenant_key=tenant_key)
    return {
        "form_slug": form.slug,
        "surface_type": "iframe",
        "script_url": script_url,
        "embed_code": embed_code(form, script_url=script_url, tenant_key=tenant_key),
        "manifest": manifest,
    }


@admin_router.get("/configuration-catalogue", response_model=FormCatalogueResponse)
def get_embed_configuration_catalogue(_admin=Depends(get_current_admin)):
    return {"ok": True, "data": catalogue()}


@admin_router.get("", response_model=list[BookingFormOut])
def list_booking_forms(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return db.query(BookingForm).filter(BookingForm.tenant_id == tenant.id).order_by(BookingForm.name).all()


@admin_router.post("", response_model=BookingFormOut, status_code=status.HTTP_201_CREATED)
def create_booking_form(
    payload: BookingFormCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    form = BookingForm(tenant_id=tenant.id, **_as_model_data(payload))
    db.add(form)
    try:
        db.flush()
        validate_form_presets(db, form)
        db.commit()
    except BookingFormResolutionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Booking form slug already exists") from exc
    db.refresh(form)
    return form


@admin_router.get("/{form_id}", response_model=BookingFormOut)
def get_booking_form(
    form_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return _form_or_404(db, tenant.id, form_id)


@admin_router.put("/{form_id}", response_model=BookingFormOut)
def update_booking_form(
    form_id: int,
    payload: BookingFormUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    form = _form_or_404(db, tenant.id, form_id)
    merged = BookingFormCreate.model_validate({
        **BookingFormOut.model_validate(form).model_dump(exclude={"id", "tenant_id", "created_at", "updated_at"}),
        **payload.model_dump(exclude_unset=True),
    })
    for key, value in _as_model_data(merged).items():
        setattr(form, key, value)
    try:
        validate_form_presets(db, form)
        db.commit()
    except BookingFormResolutionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Booking form slug already exists") from exc
    db.refresh(form)
    return form


@admin_router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking_form(
    form_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    db.delete(_form_or_404(db, tenant.id, form_id))
    db.commit()


@admin_router.post("/{form_id}/duplicate", response_model=BookingFormOut, status_code=status.HTTP_201_CREATED)
def duplicate_booking_form(
    form_id: int,
    payload: DuplicateBookingFormRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    source = _form_or_404(db, tenant.id, form_id)
    slug = payload.slug or f"{source.slug}-copy"
    name = payload.name or f"{source.name} Copy"
    candidate = slug
    index = 2
    while db.query(BookingForm).filter(BookingForm.tenant_id == tenant.id, BookingForm.slug == candidate).first():
        candidate = f"{slug}-{index}"
        index += 1
    clone = BookingForm(
        tenant_id=tenant.id,
        name=name,
        slug=candidate,
        description=source.description,
        active=False,
        module_order=list(source.module_order),
        enabled_modules=dict(source.enabled_modules),
        predefined_values=dict(source.predefined_values),
        provider_selection_mode=source.provider_selection_mode,
        clear_session_on_start=source.clear_session_on_start,
        allow_switch_to_ada=source.allow_switch_to_ada,
        widget_type=source.widget_type,
        appearance=dict(source.appearance or {}),
        settings=dict(source.settings or {}),
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@admin_router.get("/{form_id}/design", response_model=EmbedConfiguration)
def get_booking_form_design(
    form_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return configuration_for_form(_form_or_404(db, tenant.id, form_id))


@admin_router.put("/{form_id}/design", response_model=EmbedConfiguration)
def update_booking_form_design(
    form_id: int,
    payload: EmbedConfigurationPatch,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    form = _form_or_404(db, tenant.id, form_id)
    current = configuration_for_form(form)
    appearance = payload.appearance or current.appearance
    runtime = payload.runtime or current.runtime
    form.appearance = appearance.model_dump(mode="json")
    form.settings = runtime.model_dump(
        mode="json",
        exclude={"clear_session_on_start", "allow_accessible_theme_switch"},
    )
    form.clear_session_on_start = runtime.clear_session_on_start
    form.allow_switch_to_ada = runtime.allow_accessible_theme_switch
    form.widget_type = "iframe"
    db.commit()
    db.refresh(form)
    return configuration_for_form(form)


@admin_router.get("/{form_id}/preview", response_model=FormPreviewResponse)
def preview_booking_form(
    form_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    form = _form_or_404(db, tenant.id, form_id)
    return {"ok": True, "data": {**_resolution_or_422(db, form), "embed": _embed(form)}}


@admin_router.get("/{form_id}/embed", response_model=FormEmbedResponse)
def booking_form_embed(
    form_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return {"ok": True, "data": _embed(_form_or_404(db, tenant.id, form_id))}


@public_router.get("/{slug}", response_model=WidgetFormResponse)
def get_widget_form(slug: str, tenant: Tenant = Depends(get_public_tenant), db: Session = Depends(get_db)):
    form = _public_form_or_404(db, tenant.id, slug)
    return {"ok": True, "data": {"form": BookingFormOut.model_validate(form), **_resolution_or_422(db, form)}}


@public_router.post("/{slug}/resolve", response_model=WidgetResolveResponse)
def resolve_widget_form(
    slug: str,
    payload: ResolveRequest,
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
):
    form = _public_form_or_404(db, tenant.id, slug)
    return {"ok": True, "data": _resolution_or_422(db, form, payload.selections.model_dump())}


def _provider_load(db: Session, tenant_id: int, provider_id: int, start: datetime, end: datetime) -> int:
    return db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.provider_id == provider_id,
        Booking.status != BookingStatus.CANCELLED,
        Booking.end_time > start,
        Booking.start_time < end,
    ).count()


def _available_provider_slots(db: Session, form: BookingForm, resolved: dict, start: datetime, end: datetime) -> list[dict]:
    context = {key.removesuffix("_id"): value for key, value in resolved["resolved_context"].items()}
    service_id = context["service"]
    if not service_id:
        raise HTTPException(status_code=422, detail="Service must be resolved before availability")
    service = get_entity(db, form.tenant_id, "service", service_id)
    location = get_entity(db, form.tenant_id, "location", context["location"]) if context["location"] else None
    if context["provider"]:
        providers = [get_entity(db, form.tenant_id, "provider", context["provider"])]
    else:
        providers = get_valid_providers(db, form.tenant_id, context)
    by_time: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for provider in filter(None, providers):
        for slot in scheduling_service.compute_availability(
            db, service=service, provider=provider, location=location, start_time=start, end_time=end
        ):
            key = (slot["start_time"], slot["end_time"])
            by_time[key].append({**slot, "provider_id": provider.id})
    results = []
    for (slot_start, slot_end), choices in sorted(by_time.items()):
        start_dt = datetime.fromisoformat(slot_start)
        end_dt = datetime.fromisoformat(slot_end)
        selected = min(
            choices,
            key=lambda choice: (_provider_load(db, form.tenant_id, choice["provider_id"], start_dt, end_dt), choice["provider_id"]),
        )
        if form.provider_selection_mode not in {"automatic", "optional"} or context["provider"]:
            results.extend(choices)
        else:
            results.append(selected)
    return results


@public_router.post("/{slug}/availability", response_model=WidgetAvailabilityResponse)
def widget_availability(
    slug: str,
    payload: AvailabilityRequest,
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
):
    if payload.date_to <= payload.date_from:
        raise HTTPException(status_code=422, detail="date_to must be after date_from")
    form = _public_form_or_404(db, tenant.id, slug)
    resolved = _resolution_or_422(db, form, payload.selections.model_dump())
    slots = _available_provider_slots(db, form, resolved, payload.date_from, payload.date_to)
    return {"ok": True, "data": {"resolution": resolved, "slots": slots}, "meta": {"count": len(slots)}}


@public_router.post("/{slug}/bookings", status_code=status.HTTP_201_CREATED, response_model=BookingResponse)
def create_widget_booking(
    slug: str,
    payload: WidgetBookingRequest,
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
):
    form = _public_form_or_404(db, tenant.id, slug)
    client = db.query(Client).filter(
        Client.id == payload.client_id,
        Client.tenant_id == tenant.id,
        Client.deleted_at.is_(None),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.management_approval_required:
        raise HTTPException(status_code=403, detail="Client requires management approval before booking")
    resolved = _resolution_or_422(db, form, payload.selections.model_dump())
    slots = _available_provider_slots(db, form, resolved, payload.start_time, payload.end_time)
    match = next(
        (
            slot for slot in slots
            if datetime.fromisoformat(slot["start_time"]) == payload.start_time
            and datetime.fromisoformat(slot["end_time"]) == payload.end_time
        ),
        None,
    )
    if not match:
        raise HTTPException(status_code=409, detail="Selected slot is no longer available")
    context = resolved["resolved_context"]
    booking = Booking(
        tenant_id=tenant.id,
        client_id=client.id,
        service_id=context["service_id"],
        provider_id=match["provider_id"],
        location_id=context["location_id"],
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Selected slot is no longer available") from exc
    db.refresh(booking)
    return {"ok": True, "data": booking}


@public_router.get("/{slug}/runtime-manifest", response_model=WidgetRuntimeManifestResponse)
def booking_surface_runtime_manifest(
    slug: str,
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
):
    form = _public_form_or_404(db, tenant.id, slug)
    return {
        "ok": True,
        "data": runtime_manifest(
            form,
            script_url=settings.WIDGET_SCRIPT_URL,
            tenant_key=tenant.subdomain,
        ),
    }


@public_router.get("/{slug}/embed-config", response_model=FormEmbedResponse)
def widget_embed_config(slug: str, tenant: Tenant = Depends(get_public_tenant), db: Session = Depends(get_db)):
    return {"ok": True, "data": _embed(_public_form_or_404(db, tenant.id, slug))}
