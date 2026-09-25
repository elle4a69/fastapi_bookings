"""Cal.com integration router for FastAPI Bookings.

Exposes endpoints for testing connection, listing event types, generating
embed codes, and inspecting / syncing external slots.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_current_admin, get_current_tenant
from ...core.config import settings
from ...models.tenant import Tenant
from ...models.user import User
from ...services.scheduling.calcom_adapter import CalComAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/integrations/calcom", tags=["calcom-integration"])


def _get_adapter() -> CalComAdapter:
    """Helper to instantiate CalComAdapter with configured settings."""
    return CalComAdapter(
        api_key=getattr(settings, "CALCOM_API_KEY", ""),
        base_url=getattr(settings, "CALCOM_BASE_URL", "https://api.cal.com/v1"),
    )


@router.get("/status")
async def get_calcom_status(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Test Cal.com connection and return configuration and event types summary."""
    adapter = _get_adapter()
    try:
        status_info = await adapter.check_connection()
        return {
            "ok": True,
            "data": {
                "tenant_id": tenant.id,
                **status_info,
            },
        }
    finally:
        await adapter.close()


@router.get("/event-types")
async def get_calcom_event_types(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Fetch Cal.com event types and booking links for embedding."""
    adapter = _get_adapter()
    try:
        event_types = await adapter.get_event_types()
        return {
            "ok": True,
            "data": event_types,
            "count": len(event_types),
        }
    finally:
        await adapter.close()


@router.get("/embed")
def get_calcom_embed_config(
    cal_link: str = Query(..., description="Cal.com username or event slug e.g. john/30min"),
    theme: str = Query("auto", description="Theme style: light, dark, or auto"),
    layout: str = Query("month_view", description="Embed layout: month_view, week_view, or column_view"),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Generate embed parameters and HTML/JS snippet for Cal.com headless scheduler."""
    adapter = _get_adapter()
    embed_data = adapter.get_embed_config(cal_link=cal_link, theme=theme, layout=layout)
    return {
        "ok": True,
        "data": embed_data,
    }


@router.get("/slots")
async def get_calcom_slots(
    event_type_id: int = Query(..., description="Cal.com event type ID"),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    time_zone: str = Query("UTC", description="Timezone name"),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Fetch live available slots directly from Cal.com."""
    if not start_time:
        start_time = datetime.now(timezone.utc)
    if not end_time:
        end_time = start_time + timedelta(days=7)

    adapter = _get_adapter()
    try:
        slots = await adapter.get_available_slots(
            event_type_id=event_type_id,
            start_time=start_time,
            end_time=end_time,
            time_zone=time_zone,
        )
        return {
            "ok": True,
            "data": slots,
            "count": len(slots),
        }
    finally:
        await adapter.close()
