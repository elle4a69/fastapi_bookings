"""Localization and terminology services."""

from .presets import (
    DEFAULT_TERMINOLOGY,
    INDUSTRY_PRESETS,
    get_preset,
    list_presets,
    resolve_terminology,
)

__all__ = [
    "DEFAULT_TERMINOLOGY",
    "INDUSTRY_PRESETS",
    "get_preset",
    "list_presets",
    "resolve_terminology",
]
