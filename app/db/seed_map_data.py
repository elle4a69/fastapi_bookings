"""Seeding script to add discovery map mock data for independent companions."""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from ..core.security import get_password_hash
from ..core.state_machine import BookingStatus
from ..db.database import SessionLocal
from ..models.tenant import Tenant
from ..models.user import User
from ..models.provider import Provider
from ..models.service import Service
from ..models.service_provider import ServiceProvider
from ..models.schedule import ProviderWorkDay
from ..models.booking import Booking
from ..models.client import Client
from ..models.location import Location


def seed_map_data(db: Session) -> None:
    print("Seeding Discovery Map mock companions...")

    # Clear existing mock data from previous seeds to prevent subdomain collisions
    subdomains_to_clean = ["bella-companion", "sarah-hostess", "sophie-elite", "gigi-companion", "chloe-private", "mia-companion", "mane-attraction", "shag-shed", "curl-dye", "whiskeys-waves"]
    for sub in subdomains_to_clean:
        existing = db.query(Tenant).filter(Tenant.subdomain == sub).first()
        if existing:
            db.delete(existing)
    db.commit()

    # Data definition for new companion tenants
    mock_tenants = [
        {
            "name": "Bella - Independent Companion",
            "subdomain": "bella-companion",
            "address": "150 Collins St, Melbourne VIC 3000",
            "latitude": -37.8136,
            "longitude": 144.9665,
            "logo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80",
            "availability": "today"  # Has slots today (Green)
        },
        {
            "name": "Sarah - Premium Hostess",
            "subdomain": "sarah-hostess",
            "address": "300 St Kilda Rd, Southbank VIC 3006",
            "latitude": -37.8250,
            "longitude": 144.9700,
            "logo_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=200&auto=format&fit=crop&q=80",
            "availability": "later"  # Slots later this week (Orange)
        },
        {
            "name": "Sophie - Elite Companion",
            "subdomain": "sophie-elite",
            "address": "100 Lygon St, Carlton VIC 3053",
            "latitude": -37.8000,
            "longitude": 144.9680,
            "logo_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=200&auto=format&fit=crop&q=80",
            "availability": "unavailable"  # No upcoming availability (Red)
        },
        {
            "name": "Gigi - Independent Companion",
            "subdomain": "gigi-companion",
            "address": "600 Chapel St, South Yarra VIC 3141",
            "latitude": -37.8390,
            "longitude": 144.9950,
            "logo_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&auto=format&fit=crop&q=80",
            "availability": "today"  # Has slots today (Green)
        },
        {
            "name": "Chloe - Private Escort",
            "subdomain": "chloe-private",
            "address": "120 Fitzroy St, St Kilda VIC 3182",
            "latitude": -37.8610,
            "longitude": 144.9780,
            "logo_url": "https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?w=200&auto=format&fit=crop&q=80",
            "availability": "later"  # Slots later this week (Orange)
        },
        {
            "name": "Mia - Independent Companion",
            "subdomain": "mia-companion",
            "address": "200 Brunswick St, Fitzroy VIC 3065",
            "latitude": -37.8030,
            "longitude": 144.9790,
            "logo_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200&auto=format&fit=crop&q=80",
            "availability": "today"  # Has slots today (Green)
        }
    ]

    for t_data in mock_tenants:
        # Create Tenant
        tenant = Tenant(
            name=t_data["name"],
            subdomain=t_data["subdomain"],
            address=t_data["address"],
            latitude=t_data["latitude"],
            longitude=t_data["longitude"],
            logo_url=t_data["logo_url"],
            timezone="UTC",
            max_advance_days=30
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        # Create Admin
        admin_user = User(
            tenant_id=tenant.id,
            login=f"admin_{t_data['subdomain']}",
            password_hash=get_password_hash("admin123"),
            role="owner"
        )
        db.add(admin_user)

        # Create Location
        location = Location(
            tenant_id=tenant.id,
            name="Private Suite",
            address=t_data["address"],
            timezone="UTC"
        )
        db.add(location)
        db.commit()
        db.refresh(location)

        # Create Provider
        provider = Provider(
            tenant_id=tenant.id,
            name=t_data["name"].split(" - ")[0],
            email=f"contact@{t_data['subdomain']}.com",
            phone="555-8888",
            active=True,
            is_visible=True,
            capacity=1
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        # Create Services
        svc_outcall = Service(
            tenant_id=tenant.id,
            name="Outcall Companionship",
            description="Private outcall companionship and dinner hosting",
            duration=60,
            price=250.0,
            active=True,
            is_visible=True
        )
        svc_incall = Service(
            tenant_id=tenant.id,
            name="Incall Booking",
            description="Private incall booking in central Melbourne suite",
            duration=60,
            price=200.0,
            active=True,
            is_visible=True
        )
        db.add(svc_outcall)
        db.add(svc_incall)
        db.commit()
        db.refresh(svc_outcall)
        db.refresh(svc_incall)

        # Map services to provider
        db.add(ServiceProvider(tenant_id=tenant.id, service_id=svc_outcall.id, provider_id=provider.id))
        db.add(ServiceProvider(tenant_id=tenant.id, service_id=svc_incall.id, provider_id=provider.id))

        # Setup Schedule (Mon-Fri 09:00 - 17:00)
        # If the tenant is "unavailable", we do NOT add working hours so they have no slots (Red)
        if t_data["availability"] != "unavailable":
            for weekday in range(5):
                db.add(ProviderWorkDay(
                    tenant_id=tenant.id,
                    provider_id=provider.id,
                    weekday=weekday,
                    start_time="10:00",
                    end_time="22:00",
                    is_working=True
                ))
            db.commit()

            # Setup a client for this tenant
            tenant_client = Client(
                tenant_id=tenant.id,
                name="Companion Client",
                email=f"client@{t_data['subdomain']}.com",
                phone="555-3333",
                active=True
            )
            db.add(tenant_client)
            db.commit()
            db.refresh(tenant_client)

            # Book slots based on desired availability state
            now_utc = datetime.now(timezone.utc)
            
            if t_data["availability"] == "later":
                # Fully booked today: book all slots today
                for hour in range(10, 22):
                    b_start = now_utc.replace(hour=hour, minute=0, second=0, microsecond=0)
                    b_end = b_start + timedelta(minutes=60)
                    db.add(Booking(
                        tenant_id=tenant.id,
                        client_id=tenant_client.id,
                        provider_id=provider.id,
                        service_id=svc_incall.id,
                        location_id=location.id,
                        start_time=b_start,
                        end_time=b_end,
                        status=BookingStatus.CONFIRMED
                    ))
                db.commit()
                print(f"Tenant {t_data['name']} fully booked today. First slot tomorrow.")

            elif t_data["availability"] == "today":
                # Open today: book only one morning slot, leave afternoon free
                b_start = now_utc.replace(hour=10, minute=0, second=0, microsecond=0)
                b_end = b_start + timedelta(minutes=60)
                db.add(Booking(
                    tenant_id=tenant.id,
                    client_id=tenant_client.id,
                    provider_id=provider.id,
                    service_id=svc_haircut if 'svc_haircut' in locals() else svc_incall.id,
                    location_id=location.id,
                    start_time=b_start,
                    end_time=b_end,
                    status=BookingStatus.CONFIRMED
                ))
                db.commit()
                print(f"Tenant {t_data['name']} has open slots today.")
        else:
            print(f"Tenant {t_data['name']} set to unavailable (no workday schedules).")

    db.commit()
    print("Database seeding completed successfully!")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed_map_data(db_session)
    finally:
        db_session.close()
