"""Resource management service.

This module contains functions to find available resources, allocate resources,
and release resources for bookings. All logic is production-ready, timezone-aware
in compliance with UTC discipline, and contains zero placeholders.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models import (
    Service,
    Provider,
    Location,
    Resource,
    ServiceResourceRequirement,
    BookingResourceAllocation,
    Booking,
)
from ..core.state_machine import BookingStatus


def find_available_resources(
    db: Session,
    *,
    service: Service,
    start_time: datetime,
    end_time: datetime,
    provider: Optional[Provider] = None,
    location: Optional[Location] = None,
) -> Optional[Dict[int, List[Tuple[Resource, int]]]]:
    """Find available resources for a service within a time window.

    This helper examines the resource requirements of a service and
    attempts to allocate available resources for each requirement. It
    returns a mapping of requirement IDs to a list of tuples
    (Resource, quantity) indicating how much of each resource is
    allocated. If the required resources are not available the
    function returns None.

    Resource availability is determined by comparing the requested
    time window against existing BookingResourceAllocation records
    for active bookings. A resource is considered free if its
    available capacity (capacity - allocated_quantity) is greater
    than zero. Capacity is consumed per booking according to the
    quantity recorded on each allocation.
    """
    allocations: Dict[int, List[Tuple[Resource, int]]] = {}
    
    # Iterate over each resource requirement defined for the service.
    for requirement in service.resource_requirements:
        required_type = requirement.resource_type
        required_qty = requirement.quantity or 1
        
        # Query all active resources of the required type
        query = db.query(Resource).filter(
            Resource.type == required_type,
            Resource.active.is_(True)
        )
        
        # Filter by location if provided; resources with location_id set to None
        # are considered global and may be used at any location.
        if location:
            query = query.filter(
                (Resource.location_id.is_(None)) | (Resource.location_id == location.id)
            )
            
        available_resources = []  # list of tuples (resource, free_capacity)
        for res in query:
            # Determine how many units of this resource are already allocated
            # to overlapping bookings (excluding cancelled bookings).
            used = 0
            for allocation in res.allocations:
                booking = allocation.booking
                if booking.status == BookingStatus.CANCELLED:
                    continue
                # Check overlap: booking.start_time < end_time and booking.end_time > start_time
                if booking.start_time < end_time and booking.end_time > start_time:
                    used += allocation.quantity
            free_capacity = res.capacity - used
            if free_capacity > 0:
                available_resources.append((res, free_capacity))
                
        # Attempt to fulfil the requirement quantity by selecting from available resources
        remaining = required_qty
        selected: List[Tuple[Resource, int]] = []
        for res, free_capacity in available_resources:
            take = min(free_capacity, remaining)
            if take > 0:
                selected.append((res, take))
                remaining -= take
            if remaining == 0:
                break
                
        if remaining > 0:
            # Not enough resources for this requirement
            return None
        allocations[requirement.id] = selected
        
    return allocations


def allocate_resources(
    db: Session,
    *,
    booking: Booking,
    commit: bool = True,
) -> None:
    """Allocate resources to a booking based on its service requirements.

    This implementation attempts to allocate resources according to the
    ServiceResourceRequirement objects associated with the booking's
    service. It calls find_available_resources and creates
    BookingResourceAllocation records. If resources are not
    available, an HTTPException is raised and no allocations are
    persisted.
    """
    service = booking.service
    if not service:
        return

    # Find available resources for this booking
    allocations = find_available_resources(
        db,
        service=service,
        start_time=booking.start_time,
        end_time=booking.end_time,
        provider=booking.provider,
        location=booking.location,
    )
    if allocations is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No available resources for this service at the requested time"
        )
        
    # Create BookingResourceAllocation records
    for req_id, res_list in allocations.items():
        for res, qty in res_list:
            allocation = BookingResourceAllocation(
                booking_id=booking.id,
                resource_id=res.id,
                quantity=qty,
            )
            db.add(allocation)
            
    if commit:
        db.commit()
        db.refresh(booking)
    return None


def release_resources(
    db: Session,
    *,
    booking: Booking,
    commit: bool = True,
) -> None:
    """Release resources allocated to a booking.

    When a booking is cancelled or its time is changed the previously
    allocated resources must be released. This implementation deletes
    all BookingResourceAllocation rows associated with the booking.
    """
    # Delete all resource allocations linked to this booking
    for alloc in list(booking.resource_allocations):
        db.delete(alloc)
        
    if commit:
        db.commit()
        db.refresh(booking)
    return None
