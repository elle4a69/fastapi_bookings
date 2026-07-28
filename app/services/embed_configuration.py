"""Normalization and manifest generation for embedded booking surfaces."""

from __future__ import annotations

from typing import Any

from ..models.booking_form import BookingForm
from ..schemas.embed_configuration import EmbedAppearance, EmbedCatalogue, EmbedConfiguration, EmbedRuntimeSettings


THEMES = [
    "space",
    "creative",
    "minimal",
    "dainty",
    "inspiration",
    "air",
    "emeri",
    "classic",
    "hugo",
    "belle",
    "concise",
    "simple_beauty",
    "blur",
    "skittish",
    "tender",
    "default",
    "accessible",
]
LAYOUTS = [
    "flexible",
    "modern",
    "flexible_week",
    "slots_week",
    "provider_flexible",
    "classes_week",
    "classes_day",
]
DATEPICKERS = ["top_calendar", "inline_calendar"]
ITEM_DISPLAYS = ["grid", "list"]
MODERN_DISPLAYS = ["slots", "table"]
VIEWPORT_MODES = ["responsive", "phone", "tablet", "desktop"]


def normalize_configuration(
    appearance: dict[str, Any] | None,
    settings: dict[str, Any] | None,
    *,
    clear_session_on_start: bool = False,
    allow_accessible_theme_switch: bool = False,
) -> EmbedConfiguration:
    appearance_model = EmbedAppearance.model_validate(appearance or {})
    runtime_data = dict(settings or {})
    runtime_data.setdefault("clear_session_on_start", clear_session_on_start)
    runtime_data.setdefault("allow_accessible_theme_switch", allow_accessible_theme_switch)
    runtime_model = EmbedRuntimeSettings.model_validate(runtime_data)
    return EmbedConfiguration(appearance=appearance_model, runtime=runtime_model)


def configuration_for_form(form: BookingForm) -> EmbedConfiguration:
    return normalize_configuration(
        form.appearance,
        form.settings,
        clear_session_on_start=form.clear_session_on_start,
        allow_accessible_theme_switch=form.allow_switch_to_ada,
    )


def catalogue() -> EmbedCatalogue:
    return EmbedCatalogue(
        themes=THEMES,
        layouts=LAYOUTS,
        datepickers=DATEPICKERS,
        item_displays=ITEM_DISPLAYS,
        modern_displays=MODERN_DISPLAYS,
        viewport_modes=VIEWPORT_MODES,
        defaults=EmbedConfiguration(),
    )


def runtime_manifest(form: BookingForm, *, script_url: str, tenant_key: str) -> dict[str, Any]:
    config = configuration_for_form(form)
    return {
        "version": 1,
        "surface": {
            "type": "iframe",
            "form_slug": form.slug,
            "tenant": tenant_key,
            "script_url": script_url,
        },
        "flow": {
            "module_order": list(form.module_order),
            "enabled_modules": dict(form.enabled_modules),
            "provider_selection_mode": form.provider_selection_mode,
            "predefined_values": dict(form.predefined_values or {}),
        },
        "appearance": config.appearance.model_dump(mode="json"),
        "runtime": config.runtime.model_dump(mode="json"),
    }


def embed_code(form: BookingForm, *, script_url: str, tenant_key: str) -> str:
    return (
        f'<div class="booking-surface" data-tenant="{tenant_key}" '
        f'data-form="{form.slug}"></div>\n'
        f'<script src="{script_url}" defer></script>'
    )
