"""UI configuration endpoints.

These endpoints expose configuration metadata for front‑end clients.  They
describe which modules are enabled, which booking flow entry points
are allowed and other settings necessary for generating dynamic forms
and screens.  In a multi‑tenant system these values would be loaded
from tenant settings.  For now the configuration is static but can be
customised via environment variables or configuration files in the
future.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from ...db.database import get_db
from ..deps import get_public_tenant
from ...models import Tenant

router = APIRouter(prefix="/api/public/ui-config", tags=["ui-config"])


@router.get("", response_model=Any)
def get_public_ui_config(tenant: Tenant = Depends(get_public_tenant)) -> Dict[str, Any]:
    """Return configuration for the public booking UI.

    The returned object contains flags indicating which modules are
    enabled and which entry points are allowed for starting the
    booking flow.  Future versions may pull this data from the
    database or environment variables.
    """
    config: Dict[str, Any] = {
        "modules": {
            "locations": True,
            "categories": True,
            "resources": True,
            "products": True,
            "add_ons": True,
        },
        "bookingFlow": {
            "allowedEntryPoints": ["location", "provider", "category", "service", "date_time"],
            "defaultEntryPoint": "service",
        },
    }
    return config


@router.get("/admin", response_model=Any)
def get_admin_ui_config(tenant: Tenant = Depends(get_public_tenant)) -> Dict[str, Any]:
    """Return configuration for the admin dashboard UI.

    This endpoint returns module flags and other settings specific to
    the admin interface.  Currently it mirrors the public config but
    could be extended to include admin‑only modules (e.g. reports,
    exports, diagnostics).
    """
    config: Dict[str, Any] = {
        "modules": {
            "locations": True,
            "categories": True,
            "resources": True,
            "products": True,
            "add_ons": True,
            "audit": True,
            "diagnostics": True,
            "export": True,
            "backup": True,
        }
    }
    return config