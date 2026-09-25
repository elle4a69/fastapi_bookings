"""Seeding utilities to populate the database with initial data."""

from sqlalchemy.orm import Session
from ..models.tenant import Tenant
from scripts.seed_clean_numbered_data import seed_numbered_mock_data


def seed(db: Session) -> None:
    """Populate the database with initial clean numbered demo data.

    This function creates a demo tenant, numbered providers, numbered services,
    numbered locations, numbered clients, numbered bookings, service-provider assignments,
    and workday schedules.
    """
    if db.query(Tenant).filter(Tenant.subdomain == "simplydemo").first():
        return

    print("Seeding database with clean numbered entities...")
    seed_numbered_mock_data(db=db, reset_existing=False)