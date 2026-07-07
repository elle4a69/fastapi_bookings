"""Seeding utilities to populate the database with initial data."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..core.security import get_password_hash
from ..models.user import User
from ..models.provider import Provider
from ..models.service import Service
from ..models.client import Client
from ..models.location import Location
from ..models.booking import Booking


def seed(db: Session) -> None:
    """Populate the database with initial demo data.

    This function creates a demo company with an admin user, a provider,
    a service, a location, a client and a booking. It can be
    invoked manually after database initialization.
    """
    # Check if already seeded
    if db.query(User).first():
        return
    # Create admin user
    admin_user = User(
        company="simplydemo",
        login="admin",
        password_hash=get_password_hash("admin123"),
        role="owner",
    )
    db.add(admin_user)

    # Create provider
    provider = Provider(name="Demo Provider", email="provider@example.com", phone="1234567890")
    db.add(provider)

    # Create service (30 minutes)
    service = Service(name="Consultation", description="Initial consultation", duration=30, price=50.0)
    db.add(service)

    # Create location
    location = Location(name="Main Office", address="123 Example St", timezone="UTC")
    db.add(location)

    # Create client
    client = Client(name="John Doe", email="john@example.com", phone="555-1234")
    db.add(client)

    db.commit()
    db.refresh(provider)
    db.refresh(service)
    db.refresh(location)
    db.refresh(client)
    db.refresh(admin_user)

    # Create booking tomorrow at 10:00 for 30 minutes
    start_time = datetime.utcnow() + timedelta(days=1)
    start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=service.duration)
    booking = Booking(
        client_id=client.id,
        provider_id=provider.id,
        service_id=service.id,
        location_id=location.id,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(booking)
    db.commit()