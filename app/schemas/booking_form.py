"""Contracts for configurable booking forms and resolver responses."""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


BookingModule = Literal["location", "category", "service", "provider", "time"]
ProviderSelectionMode = Literal["required", "optional", "automatic", "predefined"]

DEFAULT_MODULE_ORDER = ["location", "category", "service", "provider", "time"]
DEFAULT_ENABLED_MODULES = {module: True for module in DEFAULT_MODULE_ORDER}


class ResolutionSource(str, Enum):
    predefined = "predefined"
    customer_selected = "customer_selected"
    inferred = "inferred"
    automatic = "automatic"
    unresolved = "unresolved"
    disabled = "disabled"


class PredefinedValues(BaseModel):
    location_id: int | None = None
    category_id: int | None = None
    service_id: int | None = None
    provider_id: int | None = None


class BookingSelections(PredefinedValues):
    pass


class BookingFormBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)
    description: str | None = None
    active: bool = True
    module_order: list[BookingModule] = Field(default_factory=lambda: list(DEFAULT_MODULE_ORDER))
    enabled_modules: dict[BookingModule, bool] = Field(default_factory=lambda: dict(DEFAULT_ENABLED_MODULES))
    predefined_values: PredefinedValues = Field(default_factory=PredefinedValues)
    provider_selection_mode: ProviderSelectionMode = "required"
    clear_session_on_start: bool = False
    allow_switch_to_ada: bool = False
    widget_type: str = "inline"
    appearance: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_configuration(self) -> "BookingFormBase":
        self.slug = self.slug.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.slug):
            raise ValueError("slug must contain lowercase letters, numbers, and single hyphens only")
        if len(self.module_order) != len(set(self.module_order)):
            raise ValueError("module_order contains duplicates")
        if set(self.module_order) != set(DEFAULT_MODULE_ORDER):
            raise ValueError("module_order must contain every supported module exactly once")
        unknown_enabled = set(self.enabled_modules) - set(DEFAULT_MODULE_ORDER)
        if unknown_enabled:
            raise ValueError(f"unknown enabled modules: {sorted(unknown_enabled)}")
        merged = dict(DEFAULT_ENABLED_MODULES)
        merged.update(self.enabled_modules)
        self.enabled_modules = merged
        if not self.enabled_modules["time"]:
            raise ValueError("time cannot be disabled")
        if self.provider_selection_mode == "predefined" and self.predefined_values.provider_id is None:
            raise ValueError("predefined provider mode requires predefined_values.provider_id")
        return self


class BookingFormCreate(BookingFormBase):
    pass


class BookingFormUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    active: bool | None = None
    module_order: list[BookingModule] | None = None
    enabled_modules: dict[BookingModule, bool] | None = None
    predefined_values: PredefinedValues | None = None
    provider_selection_mode: ProviderSelectionMode | None = None
    clear_session_on_start: bool | None = None
    allow_switch_to_ada: bool | None = None
    widget_type: str | None = None
    appearance: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


class BookingFormOut(BookingFormBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResolveRequest(BaseModel):
    selections: BookingSelections = Field(default_factory=BookingSelections)


class AvailabilityRequest(ResolveRequest):
    date_from: datetime
    date_to: datetime


class WidgetBookingRequest(BaseModel):
    client_id: int
    selections: BookingSelections
    start_time: datetime
    end_time: datetime
    notes: str | None = None


class DuplicateBookingFormRequest(BaseModel):
    name: str | None = None
    slug: str | None = None
