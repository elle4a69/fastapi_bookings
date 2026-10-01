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

def check_availability(
    db: Session,
    provider_id: int,
    service_id: int,
    date: Optional[datetime] = None,
    service_mode: str = "in_call",
    client_suburb: Optional[str] = None,
    service_address: Optional[str] = None,
    client_postcode: Optional[str] = None,
    search_days: int = 7,
) -> List[Dict[str, Any]]:
    """Query live availability slots supporting in-call and 5-segment out-call operational windows."""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    service = db.query(Service).filter(Service.id == service_id).first()
    if not provider or not service:
        raise ValueError("Provider or Service not found.")

    if date is not None:
        target_dates = [date]
    else:
        now_dt = datetime.now(timezone.utc)
        target_dates = [now_dt + timedelta(days=i) for i in range(max(1, search_days))]

    all_slots: List[Dict[str, Any]] = []
    from ..booking.availability_service import get_available_slots

    for d in target_dates:
        day_slots = get_available_slots(
            db=db,
            service_duration=service.duration,
            provider_id=provider.id,
            date=d,
            service_id=service.id,
            service_mode=service_mode,
            client_suburb=client_suburb,
            service_address=service_address,
            client_postcode=client_postcode,
        )
        for s in day_slots:
            slot_item = {
                "service_id": service.id,
                "service_name": service.name,
                "provider_id": provider.id,
                "provider_name": provider.name,
                "service_mode": service_mode,
                "start": s["start"].isoformat(),
                "end": s["end"].isoformat(),
                "display": s["start"].strftime("%A %B %d at %I:%M %p"),
            }
            if "operational_window" in s:
                slot_item["operational_window"] = s["operational_window"]
            all_slots.append(slot_item)
            if len(all_slots) >= 5:
                break
        if len(all_slots) >= 5:
            break

    return all_slots


def find_live_availability(
    db: Session, 
    provider_id: int, 
    service_id: int, 
    search_days: int = 7,
    service_mode: str = "in_call",
    client_suburb: Optional[str] = None,
    service_address: Optional[str] = None,
    client_postcode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query live availability slots using booking domain logic with out-call support."""
    return check_availability(
        db=db,
        provider_id=provider_id,
        service_id=service_id,
        service_mode=service_mode,
        client_suburb=client_suburb,
        service_address=service_address,
        client_postcode=client_postcode,
        search_days=search_days,
    )


async def quote_travel(
    db: Session,
    tenant_id: int,
    provider_id: int,
    suburb: Optional[str] = None,
    service_address: Optional[str] = None,
    postcode: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate or estimate out-call travel distance and fees for AI tool callers."""
    from ...models.tenant import Tenant
    from ..routing.travel_service import TravelCalculationService

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.tenant_id == tenant_id).first()
    if not tenant or not provider:
        raise ValueError("Tenant or Provider not found.")

    travel_svc = TravelCalculationService()
    try:
        if service_address:
            quote = await travel_svc.calculate_chargeable_travel(
                tenant=tenant,
                provider=provider,
                client_destination=service_address,
                is_estimate=False,
            )
        elif suburb:
            quote = await travel_svc.estimate_suburb_travel(
                tenant=tenant,
                provider=provider,
                suburb=suburb,
                postcode=postcode,
            )
        else:
            raise ValueError("Either suburb or service_address must be provided.")

        return {
            "provider_id": provider.id,
            "provider_name": provider.name,
            "suburb": suburb or quote.destination_address,
            "destination": quote.destination_address,
            "chargeable_distance_km": quote.distance_km,
            "chargeable_travel_fee": float(quote.travel_fee),
            "base_surcharge": float(quote.base_surcharge),
            "distance_fee": float(quote.distance_fee),
            "is_estimate": quote.is_estimate,
            "within_radius": quote.within_radius,
            "disclaimer": quote.disclaimer,
        }
    finally:
        await travel_svc.close()


SMS_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check real-time availability slots for a service and provider, supporting both in-call and out-call operational windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "integer", "description": "ID of the service to check."},
                    "provider_id": {"type": "integer", "description": "ID of the provider."},
                    "date": {"type": "string", "description": "Specific date in YYYY-MM-DD format (optional)."},
                    "service_mode": {
                        "type": "string",
                        "enum": ["in_call", "out_call"],
                        "description": "Delivery mode: 'in_call' or 'out_call'. Defaults to 'in_call'."
                    },
                    "client_suburb": {
                        "type": "string",
                        "description": "Client suburb name for out-call transit window resolution."
                    }
                },
                "required": ["service_id", "provider_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quote_travel",
            "description": "Calculate or estimate travel fee and distance for an out-call appointment based on suburb or street address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {"type": "integer", "description": "ID of the provider providing out-call service."},
                    "suburb": {"type": "string", "description": "Client suburb for fee estimation."},
                    "postcode": {"type": "string", "description": "Client postal code (optional)."},
                    "service_address": {"type": "string", "description": "Client exact street address for precise quote (optional)."}
                },
                "required": ["provider_id"]
            }
        }
    }
]

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
        existing = db.query(Booking).filter(
            Booking.tenant_id == tenant_id,
            Booking.idempotency_key == idempotency_key,
        ).first()
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
