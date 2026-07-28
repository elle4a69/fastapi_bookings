"""Typed contracts for embedded booking-surface presentation and runtime behaviour."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


LayoutMode = Literal[
    "flexible",
    "modern",
    "flexible_week",
    "slots_week",
    "provider_flexible",
    "classes_week",
    "classes_day",
]
DatePickerMode = Literal["top_calendar", "inline_calendar"]
ItemDisplayMode = Literal["grid", "list"]
ModernDisplayMode = Literal["slots", "table"]
ViewportMode = Literal["responsive", "phone", "tablet", "desktop"]

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_THEME_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ButtonGradient(BaseModel):
    start: str = "#f5a778"
    middle: str = "#e6938f"
    end: str = "#e28c96"

    @field_validator("start", "middle", "end")
    @classmethod
    def validate_colour(cls, value: str) -> str:
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError("colour must use six-digit hexadecimal notation")
        return value.lower()


class SurfaceColours(BaseModel):
    accent: str = "#e49092"
    buttons: ButtonGradient = Field(default_factory=ButtonGradient)
    links: str = "#e49092"
    background: str = "#ffffff"
    text: str = "#2b212b"
    text_on_accent: str = "#ffffff"
    heading: str = "#e49092"
    unavailable: str = "#aaa6aa"
    available: str = "#2b212b"

    @field_validator(
        "accent",
        "links",
        "background",
        "text",
        "text_on_accent",
        "heading",
        "unavailable",
        "available",
    )
    @classmethod
    def validate_colour(cls, value: str) -> str:
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError("colour must use six-digit hexadecimal notation")
        return value.lower()


class EmbedAppearance(BaseModel):
    theme: str = "minimal"
    colours: SurfaceColours = Field(default_factory=SurfaceColours)
    review_image_url: str | None = None
    item_display: ItemDisplayMode = "grid"
    hide_images: bool = False
    hide_company_heading: bool = False
    right_to_left: bool = False
    custom_class: str | None = Field(None, max_length=100)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        value = value.strip().lower()
        if not _THEME_KEY.fullmatch(value):
            raise ValueError("theme must be a safe lowercase key")
        return value

    @field_validator("custom_class")
    @classmethod
    def validate_custom_class(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", value):
            raise ValueError("custom_class must be a single valid CSS class token")
        return value


class EmbedRuntimeSettings(BaseModel):
    layout: LayoutMode = "flexible"
    datepicker: DatePickerMode = "top_calendar"
    modern_display: ModernDisplayMode = "slots"
    show_only_available_times: bool = True
    hide_unavailable_days: bool = False
    show_end_time: bool = True
    clear_session_on_start: bool = False
    allow_accessible_theme_switch: bool = False
    initial_viewport: ViewportMode = "responsive"
    minimum_height: int = Field(600, ge=320, le=2400)
    maximum_height: int = Field(1800, ge=480, le=5000)

    @model_validator(mode="after")
    def validate_heights(self) -> "EmbedRuntimeSettings":
        if self.maximum_height < self.minimum_height:
            raise ValueError("maximum_height must be greater than or equal to minimum_height")
        return self


class EmbedConfiguration(BaseModel):
    appearance: EmbedAppearance = Field(default_factory=EmbedAppearance)
    runtime: EmbedRuntimeSettings = Field(default_factory=EmbedRuntimeSettings)


class EmbedConfigurationPatch(BaseModel):
    appearance: EmbedAppearance | None = None
    runtime: EmbedRuntimeSettings | None = None


class EmbedCatalogue(BaseModel):
    themes: list[str]
    layouts: list[LayoutMode]
    datepickers: list[DatePickerMode]
    item_displays: list[ItemDisplayMode]
    modern_displays: list[ModernDisplayMode]
    viewport_modes: list[ViewportMode]
    defaults: EmbedConfiguration
