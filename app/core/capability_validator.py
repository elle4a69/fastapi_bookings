"""Capability hierarchy and service mode domain validators.

Enforces:
1. Tenant -> Provider -> Service hierarchy (child can be more restrictive than parent, never broader).
2. Booking service mode compatibility against Service, Provider, and Tenant.
"""

from typing import Any, Optional, Protocol


class CapabilityEntity(Protocol):
    allow_in_call: bool
    allow_out_call: bool


class CapabilityHierarchyError(ValueError):
    """Raised when a child entity capability is broader than its parent."""
    pass


class ServiceModeValidationError(ValueError):
    """Raised when a booking requests an unpermitted service mode."""
    pass


def _get_bool(obj: Any, attr: str, default: bool = True) -> bool:
    """Helper to safely extract boolean capability attribute from model, dict, or schema."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(attr)
        return default if val is None else bool(val)
    val = getattr(obj, attr, None)
    return default if val is None else bool(val)


def validate_child_not_broader(
    parent: Any,
    child: Any,
    parent_type: str = "parent",
    child_type: str = "child",
) -> None:
    """Validate that child capabilities do not exceed parent capabilities.

    A child may be more restrictive than its parent, but never broader.
    If parent has allow_in_call=False, child cannot have allow_in_call=True.
    If parent has allow_out_call=False, child cannot have allow_out_call=True.
    """
    parent_in = _get_bool(parent, "allow_in_call", default=True)
    parent_out = _get_bool(parent, "allow_out_call", default=True)
    child_in = _get_bool(child, "allow_in_call", default=True)
    child_out = _get_bool(child, "allow_out_call", default=True)

    if not parent_in and child_in:
        raise CapabilityHierarchyError(
            f"{child_type.capitalize()} cannot enable in-call capability when {parent_type} disables it."
        )
    if not parent_out and child_out:
        raise CapabilityHierarchyError(
            f"{child_type.capitalize()} cannot enable out-call capability when {parent_type} disables it."
        )


def validate_provider_capability_against_tenant(tenant: Any, provider: Any) -> None:
    """Provider capability cannot be broader than Tenant."""
    validate_child_not_broader(parent=tenant, child=provider, parent_type="tenant", child_type="provider")


def validate_service_capability_against_provider(provider: Any, service: Any) -> None:
    """Service capability cannot be broader than Provider."""
    validate_child_not_broader(parent=provider, child=service, parent_type="provider", child_type="service")


def validate_service_capability_against_tenant(tenant: Any, service: Any) -> None:
    """Service capability cannot be broader than Tenant."""
    validate_child_not_broader(parent=tenant, child=service, parent_type="tenant", child_type="service")


def validate_capability_hierarchy(
    tenant: Optional[Any] = None,
    provider: Optional[Any] = None,
    service: Optional[Any] = None,
) -> None:
    """Full hierarchy check: Tenant -> Provider -> Service."""
    if tenant and provider:
        validate_provider_capability_against_tenant(tenant, provider)
    if provider and service:
        validate_service_capability_against_provider(provider, service)
    elif tenant and service:
        validate_service_capability_against_tenant(tenant, service)


def validate_booking_service_mode(
    service_mode: Any,
    service: Optional[Any],
    provider: Optional[Any] = None,
    tenant: Optional[Any] = None,
) -> None:
    """Validate that the requested booking service mode is permitted by Service, Provider, and Tenant."""
    if service_mode is None:
        mode_str = "in_call"
    elif hasattr(service_mode, "value"):
        mode_str = str(service_mode.value).lower()
    else:
        mode_str = str(service_mode).lower()

    if mode_str == "out_call":
        if service and not _get_bool(service, "allow_out_call", default=True):
            raise ServiceModeValidationError("Service does not permit out-call appointments.")
        if provider and not _get_bool(provider, "allow_out_call", default=True):
            raise ServiceModeValidationError("Provider does not permit out-call appointments.")
        if tenant and not _get_bool(tenant, "allow_out_call", default=True):
            raise ServiceModeValidationError("Tenant does not permit out-call appointments.")
    elif mode_str == "in_call":
        if service and not _get_bool(service, "allow_in_call", default=True):
            raise ServiceModeValidationError("Service does not permit in-call appointments.")
        if provider and not _get_bool(provider, "allow_in_call", default=True):
            raise ServiceModeValidationError("Provider does not permit in-call appointments.")
        if tenant and not _get_bool(tenant, "allow_in_call", default=True):
            raise ServiceModeValidationError("Tenant does not permit in-call appointments.")
    else:
        raise ServiceModeValidationError(f"Invalid service mode: '{service_mode}'. Must be 'in_call' or 'out_call'.")
