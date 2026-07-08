"""Seeding utilities to populate the database with initial data."""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from ..core.security import get_password_hash
from ..core.state_machine import BookingStatus
from ..models.tenant import Tenant
from ..models.user import User
from ..models.provider import Provider
from ..models.service import Service
from ..models.client import Client
from ..models.location import Location
from ..models.booking import Booking
from ..models.service_provider import ServiceProvider
from ..models.schedule import ProviderWorkDay


def seed(db: Session) -> None:
    """Populate the database with initial demo data.

    This function creates a demo tenant, six providers, six services,
    six locations, six clients, six bookings, service-provider assignments,
    and workday schedules.
    """
    # Check if already seeded by checking Tenant table
    if db.query(Tenant).first():
        return

    print("Seeding multi-tenant databases with 6+ entities...")

    # 1. Create Tenant
    tenant = Tenant(name="SimplyDemo", subdomain="simplydemo")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # 2. Create Owner User
    admin_user = User(
        tenant_id=tenant.id,
        login="admin",
        password_hash=get_password_hash("admin123"),
        role="owner",
    )
    db.add(admin_user)

    # 3. Create 6 Providers
    providers = []
    for i in range(1, 7):
        p = Provider(
            tenant_id=tenant.id,
            name=f"Demo Provider {i}",
            email=f"provider{i}@example.com",
            phone=f"555-010{i}",
            active=True,
            is_visible=True,
            capacity=1
        )
        db.add(p)
        providers.append(p)

    # 4. Create 6 Services
    services = []
    durations = [30, 45, 60, 90, 30, 45]
    prices = [50.0, 75.0, 100.0, 150.0, 60.0, 80.0]
    for i in range(1, 7):
        s = Service(
            tenant_id=tenant.id,
            name=f"Service Option {i}",
            description=f"Description for service option {i}",
            duration=durations[i-1],
            price=prices[i-1],
            active=True,
            buffer_before=15,
            buffer_after=15,
            is_visible=True
        )
        db.add(s)
        services.append(s)

    # 5. Create 6 Locations
    locations = []
    for i in range(1, 7):
        l = Location(
            tenant_id=tenant.id,
            name=f"Location Branch {i}",
            address=f"{i * 100} Main Street, Suite {i}",
            timezone="UTC"
        )
        db.add(l)
        locations.append(l)

    # 6. Create 6 Clients
    clients = []
    for i in range(1, 7):
        c = Client(
            tenant_id=tenant.id,
            name=f"Client Customer {i}",
            email=f"client{i}@example.com",
            phone=f"555-020{i}",
            active=True
        )
        db.add(c)
        clients.append(c)

    db.commit()

    # Refresh seeded entries to ensure IDs are assigned
    for p in providers:
        db.refresh(p)
    for s in services:
        db.refresh(s)
    for l in locations:
        db.refresh(l)
    for c in clients:
        db.refresh(c)

    # 7. Map Services to Providers (ServiceProvider relationships)
    for i in range(6):
        # Let's map each service to its corresponding provider index, and service 1 to all providers
        sp = ServiceProvider(service_id=services[i].id, provider_id=providers[i].id)
        db.add(sp)
        if i > 0:
            sp_all = ServiceProvider(service_id=services[0].id, provider_id=providers[i].id)
            db.add(sp_all)

    # 8. Setup Provider Workdays (Monday - Friday, 09:00 - 17:00)
    for p in providers:
        for day in range(5):  # Mon (0) to Fri (4)
            workday = ProviderWorkDay(
                tenant_id=tenant.id,
                provider_id=p.id,
                weekday=day,
                start_time="09:00",
                end_time="17:00",
                is_working=True
            )
            db.add(workday)

    # 9. Create 6 Bookings
    base_start = datetime.now(timezone.utc) + timedelta(days=1)
    base_start = base_start.replace(hour=10, minute=0, second=0, microsecond=0)
    for i in range(6):
        # Distribute bookings over the next 6 days
        b_start = base_start + timedelta(days=i)
        b_end = b_start + timedelta(minutes=services[i].duration)
        booking = Booking(
            tenant_id=tenant.id,
            client_id=clients[i].id,
            provider_id=providers[i].id,
            service_id=services[i].id,
            location_id=locations[i].id,
            start_time=b_start,
            end_time=b_end,
            status=BookingStatus.CONFIRMED
        )
        db.add(booking)

    db.commit()
    print("Database seeding completed successfully!")