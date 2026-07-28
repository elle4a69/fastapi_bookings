"""Fixed-point booking-form constraint propagation."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import BookingForm
from ..schemas.booking_form import DEFAULT_MODULE_ORDER, ResolutionSource
from .booking_relationship_resolver import get_entity, get_valid_records, pair_allowed


class BookingFormResolutionError(ValueError):
    pass


ID_KEYS = {module: f"{module}_id" for module in DEFAULT_MODULE_ORDER if module != "time"}


def _config_dict(form: BookingForm, name: str) -> dict[str, Any]:
    return dict(getattr(form, name) or {})


def _option(record: Any) -> dict[str, Any]:
    result = {"id": record.id, "name": record.name}
    for field in ("description", "duration", "price", "timezone", "address"):
        if hasattr(record, field):
            value = getattr(record, field)
            if value is not None:
                result[field] = str(value) if field == "price" else value
    return result


def validate_form_presets(db: Session, form: BookingForm) -> None:
    presets = _config_dict(form, "predefined_values")
    selected: list[tuple[str, int]] = []
    for module, key in ID_KEYS.items():
        value = presets.get(key)
        if value is None:
            continue
        if not get_entity(db, form.tenant_id, module, value):
            raise BookingFormResolutionError(f"Predefined {module} does not exist in this tenant")
        selected.append((module, value))
    for index, (left_type, left_id) in enumerate(selected):
        for right_type, right_id in selected[index + 1 :]:
            if not pair_allowed(db, form.tenant_id, left_type, left_id, right_type, right_id):
                raise BookingFormResolutionError(f"Predefined {left_type} and {right_type} are incompatible")
    if form.provider_selection_mode == "predefined" and not presets.get("provider_id"):
        raise BookingFormResolutionError("Predefined provider mode requires provider_id")


def resolve_booking_form(db: Session, form: BookingForm, selections: dict[str, int | None] | None = None) -> dict[str, Any]:
    validate_form_presets(db, form)
    selections = selections or {}
    enabled = _config_dict(form, "enabled_modules")
    presets = _config_dict(form, "predefined_values")
    context: dict[str, int | None] = {module: None for module in ID_KEYS}
    sources: dict[str, str] = {}
    warnings: list[str] = []

    for module, key in ID_KEYS.items():
        if not enabled.get(module, True):
            sources[module] = ResolutionSource.disabled.value
        elif presets.get(key) is not None:
            context[module] = presets[key]
            sources[module] = ResolutionSource.predefined.value
        elif selections.get(key) is not None:
            record = get_entity(db, form.tenant_id, module, selections[key])
            if not record:
                raise BookingFormResolutionError(f"Selected {module} does not exist in this tenant")
            context[module] = selections[key]
            sources[module] = ResolutionSource.customer_selected.value
        elif module == "provider" and form.provider_selection_mode == "automatic":
            sources[module] = ResolutionSource.automatic.value
        else:
            sources[module] = ResolutionSource.unresolved.value

    chosen = [(module, value) for module, value in context.items() if value is not None]
    for index, (left_type, left_id) in enumerate(chosen):
        for right_type, right_id in chosen[index + 1 :]:
            if not pair_allowed(db, form.tenant_id, left_type, left_id, right_type, right_id):
                raise BookingFormResolutionError(f"Selected {left_type} and {right_type} are incompatible")

    options: dict[str, list[dict[str, Any]]] = {}
    changed = True
    while changed:
        changed = False
        for module in form.module_order:
            if module == "time" or sources.get(module) != ResolutionSource.unresolved.value:
                continue
            records = get_valid_records(db, form.tenant_id, module, context)
            options[module] = [_option(record) for record in records]
            if not records:
                warnings.append(f"This configuration resolves to no valid {module} records.")
            should_infer = len(records) == 1 and not (
                module == "provider" and form.provider_selection_mode == "optional"
            )
            if should_infer:
                context[module] = records[0].id
                sources[module] = ResolutionSource.inferred.value
                options.pop(module, None)
                changed = True

    for module in ID_KEYS:
        if sources[module] == ResolutionSource.disabled.value and context[module] is None:
            records = get_valid_records(db, form.tenant_id, module, context)
            if len(records) != 1 and module in {"service", "location", "category"}:
                warnings.append(f"{module.title()} is disabled but remains unresolved.")

    visible = [
        module
        for module in form.module_order
        if module == "time" or sources.get(module) == ResolutionSource.unresolved.value
    ]
    if "provider" in visible and form.provider_selection_mode == "optional":
        options.setdefault("provider", get_valid_records(db, form.tenant_id, "provider", context))
        if options["provider"] and not isinstance(options["provider"][0], dict):
            options["provider"] = [_option(record) for record in options["provider"]]
        options["provider"] = [{"id": None, "name": "Anyone available"}, *options["provider"]]
    visible.append("client")
    return {
        "resolved_context": {ID_KEYS[module]: value for module, value in context.items()},
        "resolution_source": sources,
        "visible_modules": visible,
        "options": options,
        "warnings": list(dict.fromkeys(warnings)),
    }
