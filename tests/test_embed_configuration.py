from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.embed_configuration import EmbedAppearance, EmbedRuntimeSettings
from app.services.embed_configuration import catalogue, embed_code, runtime_manifest


def _form():
    return SimpleNamespace(
        slug="main-booking",
        module_order=["location", "category", "service", "provider", "time"],
        enabled_modules={
            "location": True,
            "category": True,
            "service": True,
            "provider": True,
            "time": True,
        },
        provider_selection_mode="optional",
        predefined_values={"location_id": 2},
        appearance={
            "theme": "minimal",
            "colours": {"accent": "#112233"},
            "item_display": "grid",
        },
        settings={"layout": "modern", "datepicker": "inline_calendar"},
        clear_session_on_start=True,
        allow_switch_to_ada=True,
    )


def test_catalogue_exposes_supported_options_and_defaults():
    data = catalogue()
    assert "minimal" in data.themes
    assert "accessible" in data.themes
    assert "modern" in data.layouts
    assert data.defaults.appearance.theme == "minimal"
    assert data.defaults.runtime.minimum_height == 600


def test_appearance_rejects_unsafe_theme_and_invalid_colour():
    with pytest.raises(ValidationError):
        EmbedAppearance(theme="../../unsafe")
    with pytest.raises(ValidationError):
        EmbedAppearance.model_validate({"colours": {"accent": "red"}})


def test_runtime_rejects_inverted_height_range():
    with pytest.raises(ValidationError):
        EmbedRuntimeSettings(minimum_height=1200, maximum_height=800)


def test_embed_markup_uses_neutral_project_naming():
    code = embed_code(_form(), script_url="/static/booking-widget.js", tenant_key="acme")
    assert 'class="booking-surface"' in code
    assert 'data-tenant="acme"' in code
    assert 'data-form="main-booking"' in code
    assert "simplybook" not in code.lower()
    assert "sb-" not in code.lower()


def test_runtime_manifest_contains_flow_and_typed_design():
    manifest = runtime_manifest(
        _form(),
        script_url="/static/booking-widget.js",
        tenant_key="acme",
    )
    assert manifest["surface"]["type"] == "iframe"
    assert manifest["flow"]["provider_selection_mode"] == "optional"
    assert manifest["appearance"]["colours"]["accent"] == "#112233"
    assert manifest["runtime"]["layout"] == "modern"
    assert manifest["runtime"]["clear_session_on_start"] is True
    assert manifest["runtime"]["allow_accessible_theme_switch"] is True
