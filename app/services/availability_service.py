"""Availability calculation service.

This module provides compatibility wrappers for availability calculations.
It routes all requests to the central scheduling service engine.
"""

from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from ..models.service import Service
from ..models.provider import Provider
from .scheduling_service import compute_availability


def get_available_slots(
    db: Session,
    service_duration: int,
    provider_id: int,
    date: datetime,
    service_id: int | None = None,
) -> List[dict]:
    """Return a list of available time slots for a provider on a given date.

    Compatibility wrapper routing to scheduling_service.compute_availability.
    """
    # Load first provider and service to extract context
    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.deleted_at.is_(None)).first()
    if not provider:
        return []

    # Resolve the requested service; compatibility callers without service_id
    # may only use the unique active service for the tenant.
    service_query = db.query(Service).filter(
        Service.tenant_id == provider.tenant_id,
        Service.active.is_(True),
        Service.deleted_at.is_(None),
    )
    if service_id is not None:
        service_query = service_query.filter(Service.id == service_id)
        service = service_query.first()
    else:
        services = service_query.limit(2).all()
        service = services[0] if len(services) == 1 else None
    if not service:
        return []

    # Define a search window covering the requested date
    # Use timezone-aware datetimes as required by timezone discipline
    start_time = datetime.combine(date.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
    end_time = datetime.combine(date.date(), datetime.max.time()).replace(tzinfo=timezone.utc)

    slots = compute_availability(
        db,
        service=service,
        provider=provider,
        start_time=start_time,
        end_time=end_time,
        desired_duration=service_duration,
    )

    # Convert response to expected compatible structure with 'start' and 'end' keys
    compatible_slots = []
    for slot in slots:
        compatible_slots.append({
            "start": datetime.fromisoformat(slot["start_time"]),
            "end": datetime.fromisoformat(slot["end_time"]),
        })
    return compatible_slots
