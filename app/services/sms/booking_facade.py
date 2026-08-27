import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ...models.provider import Provider
from ...models.service import Service
from ...models.client import Client
from ...models.booking import Booking
from ...models.location import Location
from ...services.scheduling_service import compute_availability, allocate_resources, release_resources
from ...services.outbox_service import create_outbox_event

logger = logging.getLogger(__name__)

def get_provider_profile(db: Session, provider_id: int) -> Dict[str, Any]:
    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.active == True).first()
    if not provider:
        raise ValueError("Provider not found or inactive.")
    return {
        "id": provider.id,
        "name": provider.name,
        "description": provider.description,
        "color": provider.color
    }

def list_provider_services(db: Session, provider_id: int) -> List[Dict[str, Any]]:
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise ValueError("Provider not found.")
    
    services = []
    for sp in provider.services:
        s = sp.service
        if not s.deleted_at:
            services.append({
                "id": s.id,
                "name": s.name,
                "price": float(s.price) if s.price else 0.0,
                "duration": s.duration
            })
    return services

def get_service_details(db: Session, provider_id: int, service_id: int) -> Dict[str, Any]:
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise ValueError("Provider not found.")
        
    # Verify provider is eligible to deliver this service
    eligible_service_ids = [sp.service_id for sp in provider.services]
    if service_id not in eligible_service_ids:
        raise ValueError("Provider is not eligible to deliver this service.")
        
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service or service.deleted_at:
        raise ValueError("Service not found.")
        
    return {
        "id": service.id,
        "name": service.name,
        "duration": service.duration,
        "price": float(service.price) if service.price else 0.0,
        "description": service.description
    }

def find_live_availability(
    db: Session, 
    provider_id: int, 
    service_id: int, 
    search_days: int = 7
) -> List[Dict[str, Any]]:
    """Query live availability slots using existing booking domain logic."""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    service = db.query(Service).filter(Service.id == service_id).first()
    if not provider or not service:
        raise ValueError("Provider or Service not found.")

    start_search = datetime.now(timezone.utc)
    end_search = start_search + timedelta(days=search_days)

    slots = compute_availability(
        db=db,
        service=service,
        provider=provider,
        start_time=start_search,
        end_time=end_search
    )
    
    # Format slots for AI/SMS use
    formatted_slots = []
    for slot in slots[:5]:  # Return at most 5 slots to keep SMS short
        formatted_slots.append({
            "service_id": service_id,
            "service_name": service.name,
            "provider_id": provider_id,
            "provider_name": provider.name,
            "start": slot["start"].isoformat(),
            "end": slot["end"].isoformat(),
            "display": slot["start"].strftime("%A %B %d at %I:%M %p")
        })
        
    return formatted_slots

def create_booking(
    db: Session,
    tenant_id: int,
    provider_id: int,
    service_id: int,
    client_phone: str,
    client_name: str,
    start_time: datetime,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """Idempotently create a booking in the FastAPI Bookings domain."""
    if idempotency_key:
        existing = db.query(Booking).filter(Booking.idempotency_key == idempotency_key).first()
        if existing:
            logger.info(f"Booking creation deduplicated via idempotency_key={idempotency_key}")
            return {"booking_id": existing.id, "status": existing.status.value, "duplicate": True}

    # 1. Resolve or create Client
    client = db.query(Client).filter(
        Client.tenant_id == tenant_id,
        Client.phone == client_phone
    ).first()
    
    if not client:
        client = Client(
            tenant_id=tenant_id,
            name=client_name,
            phone=client_phone,
            active=True
        )
        db.add(client)
        db.flush()

    # 2. Fetch service duration
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise ValueError("Service not found.")
    
    end_time = start_time + timedelta(minutes=service.duration)

    # 3. Create Booking
    booking = Booking(
        tenant_id=tenant_id,
        client_id=client.id,
        provider_id=provider_id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
        idempotency_key=idempotency_key
    )
    db.add(booking)
    db.flush()

    # 4. Allocate resources
    try:
        allocate_resources(db, booking=booking, commit=False)
    except Exception as e:
        db.rollback()
        raise ValueError(f"Failed to allocate resources: {e}")

    # 5. Create outbox event (triggers confirmation notifications)
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "status": "confirmed"
    }
    create_outbox_event(db, "booking.created", payload, tenant_id=tenant_id)
    
    db.commit()
    return {"booking_id": booking.id, "status": "confirmed", "duplicate": False}

def cancel_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """Idempotently cancel a booking in the FastAPI Bookings domain."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.tenant_id == tenant_id
    ).first()
    
    if not booking:
        raise ValueError("Booking not found.")

    if booking.status.value == "cancelled":
        return {"booking_id": booking.id, "status": "cancelled", "duplicate": True}

    booking.status = "cancelled"
    
    # Release resources
    try:
        release_resources(db, booking=booking, commit=False)
    except Exception as e:
        logger.warning(f"Error releasing resources for booking {booking_id}: {e}")

    # Outbox event
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "status": "cancelled",
        "reason": reason
    }
    create_outbox_event(db, "booking.cancelled", payload, tenant_id=tenant_id)
    
    db.commit()
    return {"booking_id": booking.id, "status": "cancelled", "duplicate": False}

def amend_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    start_time: datetime,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """Idempotently amend/reschedule an existing booking."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.tenant_id == tenant_id
    ).first()
    
    if not booking:
        raise ValueError("Booking not found.")

    if booking.status.value == "cancelled":
        raise ValueError("Cannot reschedule a cancelled booking.")

    # Idempotency check
    if booking.start_time == start_time:
        return {"booking_id": booking.id, "status": booking.status.value, "duplicate": True}

    # Release existing resources first
    try:
        release_resources(db, booking=booking, commit=False)
    except Exception as e:
        logger.warning(f"Error releasing resources for booking {booking_id}: {e}")

    # Calculate new end_time
    service = booking.service
    end_time = start_time + timedelta(minutes=service.duration)
    
    booking.start_time = start_time
    booking.end_time = end_time
    booking.idempotency_key = idempotency_key

    # Re-allocate resources for new window
    try:
        allocate_resources(db, booking=booking, commit=False)
    except Exception as e:
        db.rollback()
        raise ValueError(f"Failed to allocate resources for the new slot: {e}")

    # Create outbox event
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "status": booking.status.value
    }
    create_outbox_event(db, "booking.updated", payload, tenant_id=tenant_id)
    
    db.commit()
    return {"booking_id": booking.id, "status": booking.status.value, "duplicate": False}
