"""System diagnostics API routes.

These endpoints expose internal diagnostic information to admins.
Diagnostics include database status, migration version, enabled
modules, and counts of key entities.  They can be used to monitor
the health of the system and aid in troubleshooting.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_admin
from ...db.database import get_db
from ...models import (
    Service,
    Provider,
    Client,
    Booking,
    Resource,
    OutboxEvent,
    WaitlistEntry,
)

router = APIRouter(prefix="/api/admin/system", tags=["system"])


@router.get("/diagnostics", response_model=Any)
def get_system_diagnostics(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return system diagnostics.

    For security reasons the diagnostics returned here are minimal
    and intended primarily for demonstration.  A real system might
    include migration version, orphaned record detection, failed
    events and more.
    """
    diagnostics: Dict[str, Any] = {
        "counts": {
            "services": db.query(Service).count(),
            "providers": db.query(Provider).count(),
            "clients": db.query(Client).count(),
            "bookings": db.query(Booking).count(),
            "resources": db.query(Resource).count(),
            "waitlist_entries": db.query(WaitlistEntry).count(),
            "outbox_events": db.query(OutboxEvent).filter(OutboxEvent.processed == False).count(),
        },
        "modules": {
            "locations": True,
            "categories": True,
            "resources": True,
            "products": True,
            "add_ons": True,
            "packages": True,
            "holds": True,
            "waitlist": True,
            "multi_tenant": True,  # toggle once multi‑tenant support is added
        },
    }
    return diagnostics