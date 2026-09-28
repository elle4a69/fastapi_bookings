"""Comprehensive demo catalog and lifecycle booking seeder for FastAPI Bookings.

Target Tenant:
- SimplyDemo (subdomain: simplydemo, tenant_id: 1)

Features:
1. Complete purge of existing tenant catalog, schedules, bookings, slot allocations,
   and financial records ensuring a verified clean slate.
2. Structured Catalog:
   - 2 Locations with 2 Resources each (Suites & Studios)
   - 2 Categories ("Private In-Call Engagements", "Social & Out-Call Accompaniment")
   - 5 Services with precise pricing, buffers, travel outcall settings, and deposit rules
   - 5 Providers with realistic travel surcharges, per-km fees, radiuses, buffers, and weekly schedules
   - 5 Add-ons linked to relevant services
   - 5 Products linked to services and locations
   - 2 Packages with sequenced steps
   - 5 Clients with realistic Sydney residential profiles
3. Full Lifecycle Bookings:
   - 12 Completed historical bookings with financial snapshots and slot allocations
   - 1 In-Progress active booking for today
   - 6 Confirmed upcoming bookings with slot allocations
   - 3 Pending bookings awaiting confirmation/deposit
   - 2 Cancelled bookings with audit trail reasons
   - 2 No-Show historical bookings
   - Accurate 15-minute BookingSlotAllocation records for all active/confirmed/completed appointments
   - Invoices and completed Payments for all completed historical bookings
"""

import sys
import os
from datetime import datetime, timedelta, timezone, date, time
from decimal import Decimal
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal, Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.location import Location, LocationProvider, LocationService, LocationCategory, LocationProduct
from app.models.booking import Booking, ServiceMode
from app.models.booking_slot_allocation import BookingSlotAllocation
from app.models.service_provider import ServiceProvider
from app.models.schedule import ProviderWorkDay, ProviderSpecialDay, BlockedTime, ReservedTime
from app.models.category import Category, ServiceCategory
from app.models.addon import AddOn, ServiceAddOn
from app.models.product import Product, ServiceProduct
from app.models.package import ServicePackage, PackageStep
from app.models.resource import Resource, ServiceResourceRequirement, BookingResourceAllocation
from app.models.checkout import Invoice, InvoiceLine, Tip, PromotionCode, TaxRate
from app.models.payment import Payment
from app.models.audit import AuditLog
from app.models.client_dispute import ClientDispute
from app.models.sms_arrival import SmsArrivalSession
from app.core.security import get_password_hash
from app.core.state_machine import BookingStatus


def purge_existing_demo_data(db, tenant_id: int):
    """Safely and thoroughly clean out all existing records for the given tenant respecting FKs."""
    print(f"\n[1/4] PURGING ALL EXISTING DEMO DATA FOR TENANT {tenant_id}...")
    from sqlalchemy import text

    statements = [
        # Disassociate providers from users and settings first
        "UPDATE users SET provider_id = NULL WHERE tenant_id = :t;",
        "UPDATE sms_accounts SET provider_id = NULL WHERE tenant_id = :t;",
        "UPDATE sms_knowledge_entries SET provider_id = NULL WHERE tenant_id = :t;",
        "UPDATE sms_conversations SET provider_id = NULL WHERE tenant_id = :t;",
        "UPDATE sms_messages SET provider_id = NULL WHERE tenant_id = :t;",
        "UPDATE sms_bootcamp_settings SET provider_id = NULL WHERE tenant_id = :t;",
        
        # Booking sub-allocations and dependents
        "DELETE FROM booking_resource_allocations WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM booking_slot_allocations WHERE tenant_id = :t;",
        "DELETE FROM booking_events WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM additional_field_responses WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM notification_logs WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM notifications WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM sms_arrival_sessions WHERE booking_id IN (SELECT id FROM bookings WHERE tenant_id = :t);",
        "DELETE FROM client_disputes WHERE tenant_id = :t;",
        "DELETE FROM payments WHERE tenant_id = :t;",
        "DELETE FROM invoice_lines WHERE tenant_id = :t;",
        "DELETE FROM tips WHERE tenant_id = :t;",
        "DELETE FROM invoices WHERE tenant_id = :t;",
        "DELETE FROM waitlist_entries WHERE tenant_id = :t;",
        "DELETE FROM management_review_requests WHERE tenant_id = :t;",
        "DELETE FROM bookings WHERE tenant_id = :t;",
        "DELETE FROM booking_series WHERE tenant_id = :t;",
        "DELETE FROM reserved_times WHERE tenant_id = :t;",

        # Package steps and packages
        "DELETE FROM package_steps WHERE package_id IN (SELECT id FROM service_packages WHERE tenant_id = :t);",
        "DELETE FROM service_packages WHERE tenant_id = :t;",

        # Service associations
        "DELETE FROM service_resource_requirements WHERE service_id IN (SELECT id FROM services WHERE tenant_id = :t);",
        "DELETE FROM service_providers WHERE service_id IN (SELECT id FROM services WHERE tenant_id = :t);",
        "DELETE FROM service_categories WHERE service_id IN (SELECT id FROM services WHERE tenant_id = :t);",
        "DELETE FROM service_add_ons WHERE service_id IN (SELECT id FROM services WHERE tenant_id = :t);",
        "DELETE FROM service_products WHERE service_id IN (SELECT id FROM services WHERE tenant_id = :t);",
        "DELETE FROM location_services WHERE tenant_id = :t;",

        # Location associations & resources
        "DELETE FROM location_providers WHERE tenant_id = :t;",
        "DELETE FROM location_categories WHERE tenant_id = :t;",
        "DELETE FROM location_products WHERE tenant_id = :t;",
        "DELETE FROM resources WHERE tenant_id = :t;",
        "DELETE FROM provider_workdays WHERE tenant_id = :t;",
        "DELETE FROM provider_special_days WHERE tenant_id = :t;",
        "DELETE FROM blocked_times WHERE tenant_id = :t;",
        "DELETE FROM calendar_notes WHERE tenant_id = :t;",

        # Provider SMS/Bootcamp dependents
        "DELETE FROM assistant_channel_bindings WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM curated_memories WHERE tenant_id = :t;",
        "DELETE FROM provider_categories WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM sms_chatwoot_bindings WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM sms_prompt_profiles WHERE tenant_id = :t;",
        "DELETE FROM sms_bootcamp_conversations WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM sms_bootcamp_runs WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM knowledge_proposals WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM knowledge_graph_projections WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",
        "DELETE FROM learning_events WHERE provider_id IN (SELECT id FROM providers WHERE tenant_id = :t);",

        # Core catalog entities
        "DELETE FROM services WHERE tenant_id = :t;",
        "DELETE FROM providers WHERE tenant_id = :t;",
        "DELETE FROM locations WHERE tenant_id = :t;",
        "DELETE FROM categories WHERE tenant_id = :t;",
        "DELETE FROM add_ons WHERE tenant_id = :t;",
        "DELETE FROM products WHERE tenant_id = :t;",

        # Client dependents and clients
        "DELETE FROM device_tokens WHERE client_id IN (SELECT id FROM clients WHERE tenant_id = :t);",
        "DELETE FROM gdpr_consents WHERE client_id IN (SELECT id FROM clients WHERE tenant_id = :t);",
        "DELETE FROM notification_preferences WHERE client_id IN (SELECT id FROM clients WHERE tenant_id = :t);",
        "DELETE FROM clients WHERE tenant_id = :t;",
    ]

    for stmt in statements:
        try:
            db.execute(text(stmt), {"t": tenant_id})
            db.commit()
        except Exception as ex:
            db.rollback()
            print(f"  [purge debug] skipped/handled: {ex}")

    # Verify purge
    remaining_bookings = db.query(Booking).filter(Booking.tenant_id == tenant_id).count()
    remaining_services = db.query(Service).filter(Service.tenant_id == tenant_id).count()
    remaining_providers = db.query(Provider).filter(Provider.tenant_id == tenant_id).count()
    remaining_locations = db.query(Location).filter(Location.tenant_id == tenant_id).count()
    remaining_resources = db.query(Resource).filter(Resource.tenant_id == tenant_id).count()

    print(f"  Purge verified: Bookings={remaining_bookings}, Services={remaining_services}, "
          f"Providers={remaining_providers}, Locations={remaining_locations}, Resources={remaining_resources}")
    assert remaining_bookings == 0 and remaining_services == 0 and remaining_providers == 0, "Purge incomplete!"
    print("  => Clean slate verified successfully.\n")


def ensure_database_schema(db):
    """Ensure database schema and enum values match runtime expectations."""
    from sqlalchemy import text
    try:
        bind = db.get_bind()
        # Query existing enum values for bookingstatus
        res = db.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'bookingstatus';")).fetchall()
        existing_labels = {r[0] for r in res}
        if "IN_PROGRESS" not in existing_labels:
            with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("ALTER TYPE bookingstatus ADD VALUE 'IN_PROGRESS';"))
            print("  Added 'IN_PROGRESS' to PostgreSQL bookingstatus enum.")
    except Exception as e:
        print(f"  [ensure_database_schema note] {e}")


def seed_demo_structured_catalog(db=None) -> Dict[str, Any]:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        ensure_database_schema(db)
        # 1. Ensure Tenant
        tenant = db.query(Tenant).filter(Tenant.subdomain == "simplydemo").first()
        if not tenant:
            tenant = Tenant(
                name="SimplyDemo",
                subdomain="simplydemo",
                subscription_tier="unlimited",
                addon_quota=999,
                address="100 Main Street, Suite 100, Sydney NSW 2000",
                latitude=-33.8688,
                longitude=151.2093,
                timezone="Australia/Sydney",
                allow_in_call=True,
                allow_out_call=True,
                travel_charge_origin="ALWAYS_FROM_BASE"
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        else:
            tenant.name = "SimplyDemo"
            tenant.subscription_tier = "unlimited"
            tenant.addon_quota = 999
            tenant.address = "100 Main Street, Suite 100, Sydney NSW 2000"
            tenant.latitude = -33.8688
            tenant.longitude = 151.2093
            tenant.timezone = "Australia/Sydney"
            tenant.allow_in_call = True
            tenant.allow_out_call = True
            tenant.travel_charge_origin = "ALWAYS_FROM_BASE"
            db.commit()
            db.refresh(tenant)

        tenant_id = tenant.id
        print(f"Target Tenant: id={tenant.id}, name='{tenant.name}', subdomain='{tenant.subdomain}'")

        # Purge existing data
        purge_existing_demo_data(db, tenant_id)

        print("[2/4] SEEDING STRUCTURED CATALOG...")

        # 2. Owner User
        admin_user = db.query(User).filter(User.tenant_id == tenant_id, User.login == "admin").first()
        if not admin_user:
            admin_user = User(
                tenant_id=tenant_id,
                login="admin",
                password_hash=get_password_hash("admin123"),
                role="owner",
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # 3. Locations (2 Locations)
        loc1 = Location(
            tenant_id=tenant_id,
            name="Location 1 - Central Executive Suites",
            address="100 Main Street, Suite 100, Sydney NSW 2000",
            timezone="Australia/Sydney",
            active=True,
            is_visible=True,
            is_client_hidden=False,
        )
        loc2 = Location(
            tenant_id=tenant_id,
            name="Location 2 - Harbourview Private Studios",
            address="200 Pacific Highway, Suite 200, North Sydney NSW 2060",
            timezone="Australia/Sydney",
            active=True,
            is_visible=True,
            is_client_hidden=False,
        )
        db.add_all([loc1, loc2])
        db.commit()
        db.refresh(loc1)
        db.refresh(loc2)

        # Resources (2 per Location: 4 Total)
        res_loc1_1 = Resource(
            tenant_id=tenant_id,
            location_id=loc1.id,
            name="Resource 1 - Executive Suite A",
            type="suite",
            capacity=1,
            active=True,
        )
        res_loc1_2 = Resource(
            tenant_id=tenant_id,
            location_id=loc1.id,
            name="Resource 2 - Executive Suite B",
            type="suite",
            capacity=1,
            active=True,
        )
        res_loc2_1 = Resource(
            tenant_id=tenant_id,
            location_id=loc2.id,
            name="Resource 1 - Private Studio 1",
            type="studio",
            capacity=1,
            active=True,
        )
        res_loc2_2 = Resource(
            tenant_id=tenant_id,
            location_id=loc2.id,
            name="Resource 2 - Private Studio 2",
            type="studio",
            capacity=1,
            active=True,
        )
        db.add_all([res_loc1_1, res_loc1_2, res_loc2_1, res_loc2_2])
        db.commit()
        for r in [res_loc1_1, res_loc1_2, res_loc2_1, res_loc2_2]:
            db.refresh(r)

        # 4. Categories (2 Categories)
        cat1 = Category(
            tenant_id=tenant_id,
            name="Category 1 - Private In-Call Engagements",
            description="Exclusive appointments hosted at our premier private suites and studios.",
            active=True,
            is_visible=True,
        )
        cat2 = Category(
            tenant_id=tenant_id,
            name="Category 2 - Social & Out-Call Accompaniment",
            description="Bespoke accompaniment for fine dining, corporate galas, social events, and travel.",
            active=True,
            is_visible=True,
        )
        db.add_all([cat1, cat2])
        db.commit()
        db.refresh(cat1)
        db.refresh(cat2)

        # 5. Services (5 Services)
        svc1 = Service(
            tenant_id=tenant_id,
            name="Service 1 - VIP In-Call Session",
            description="An intimate 60-minute private consultation at our dedicated luxury suite.",
            duration=60,
            price=Decimal("300.00"),
            outcall_price=Decimal("350.00"),
            buffer_before=15,
            buffer_after=15,
            outcall_buffer_before=30,
            outcall_buffer_after=30,
            allow_in_call=True,
            allow_out_call=True,
            deposit_amount=Decimal("100.00"),
            is_visible=True,
            active=True,
        )
        svc2 = Service(
            tenant_id=tenant_id,
            name="Service 2 - Standard Social Accompaniment / Dinner Date",
            description="A polished 2-hour dining and social accompaniment engagement.",
            duration=120,
            price=Decimal("500.00"),
            outcall_price=Decimal("550.00"),
            buffer_before=15,
            buffer_after=30,
            outcall_buffer_before=45,
            outcall_buffer_after=45,
            allow_in_call=True,
            allow_out_call=True,
            deposit_amount=Decimal("150.00"),
            is_visible=True,
            active=True,
        )
        svc3 = Service(
            tenant_id=tenant_id,
            name="Service 3 - Executive Out-Call Appointment",
            description="90-minute mobile executive appointment delivered at your private hotel or residence.",
            duration=90,
            price=Decimal("450.00"),
            outcall_price=Decimal("450.00"),
            buffer_before=0,
            buffer_after=15,
            outcall_buffer_before=30,
            outcall_buffer_after=45,
            allow_in_call=False,
            allow_out_call=True,
            deposit_amount=Decimal("150.00"),
            is_visible=True,
            active=True,
        )
        svc4 = Service(
            tenant_id=tenant_id,
            name="Service 4 - Extended Evening Companion",
            description="Comprehensive 4-hour evening social or gala accompaniment with complete discretion.",
            duration=240,
            price=Decimal("900.00"),
            outcall_price=Decimal("1000.00"),
            buffer_before=30,
            buffer_after=30,
            outcall_buffer_before=60,
            outcall_buffer_after=60,
            allow_in_call=True,
            allow_out_call=True,
            deposit_amount=Decimal("0.00"),
            is_visible=True,
            active=True,
        )
        svc5 = Service(
            tenant_id=tenant_id,
            name="Service 5 - Day / Travel Accompaniment",
            description="Full-day 8-hour executive travel or VIP event attendance.",
            duration=480,
            price=Decimal("1800.00"),
            outcall_price=Decimal("2000.00"),
            buffer_before=30,
            buffer_after=60,
            outcall_buffer_before=60,
            outcall_buffer_after=120,
            allow_in_call=True,
            allow_out_call=True,
            deposit_amount=Decimal("0.00"),
            is_visible=True,
            active=True,
        )
        db.add_all([svc1, svc2, svc3, svc4, svc5])
        db.commit()
        for s in [svc1, svc2, svc3, svc4, svc5]:
            db.refresh(s)

        # Service Resource Requirements (In-Call requirements)
        req_svc1 = ServiceResourceRequirement(service_id=svc1.id, resource_type="suite", quantity=1)
        req_svc2 = ServiceResourceRequirement(service_id=svc2.id, resource_type="suite", quantity=1)
        req_svc4 = ServiceResourceRequirement(service_id=svc4.id, resource_type="studio", quantity=1)
        db.add_all([req_svc1, req_svc2, req_svc4])
        db.commit()

        # Service Categories
        sc_map = [
            (svc1.id, cat1.id),
            (svc2.id, cat2.id),
            (svc3.id, cat2.id),
            (svc4.id, cat2.id),
            (svc5.id, cat2.id),
        ]
        db.add_all([ServiceCategory(tenant_id=tenant_id, service_id=sid, category_id=cid) for sid, cid in sc_map])
        db.commit()

        # 6. Providers (5 Providers)
        prov1 = Provider(
            tenant_id=tenant_id,
            name="Provider 1 - Elena Rostova",
            email="provider1@simplydemo.com",
            phone="0400000001",
            description="Senior companion specialising in VIP In-Call sessions and social dinner accompaniment.",
            active=True,
            is_visible=True,
            allow_in_call=True,
            allow_out_call=True,
            in_call_address="100 Main Street, Suite 100, Sydney NSW 2000",
            base_outcall_surcharge=Decimal("50.00"),
            per_km_fee=Decimal("3.00"),
            out_call_radius_km=30.0,
            turnaround_buffer_mins=20,
        )
        prov2 = Provider(
            tenant_id=tenant_id,
            name="Provider 2 - Alexander Vance",
            email="provider2@simplydemo.com",
            phone="0400000002",
            description="Accomplished conversationalist and travel companion for executive galas and corporate functions.",
            active=True,
            is_visible=True,
            allow_in_call=True,
            allow_out_call=True,
            in_call_address="100 Main Street, Suite 100, Sydney NSW 2000",
            base_outcall_surcharge=Decimal("50.00"),
            per_km_fee=Decimal("3.00"),
            out_call_radius_km=35.0,
            turnaround_buffer_mins=25,
        )
        prov3 = Provider(
            tenant_id=tenant_id,
            name="Provider 3 - Chloe Dupont",
            email="provider3@simplydemo.com",
            phone="0400000003",
            description="Dedicated out-call specialist for hotel visits, social events, and bespoke day tours.",
            active=True,
            is_visible=True,
            allow_in_call=False,
            allow_out_call=True,
            in_call_address=None,
            base_outcall_surcharge=Decimal("50.00"),
            per_km_fee=Decimal("3.00"),
            out_call_radius_km=40.0,
            turnaround_buffer_mins=30,
        )
        prov4 = Provider(
            tenant_id=tenant_id,
            name="Provider 4 - Marcus Sterling",
            email="provider4@simplydemo.com",
            phone="0400000004",
            description="North Sydney resident host offering relaxed studio appointments and executive dinner bookings.",
            active=True,
            is_visible=True,
            allow_in_call=True,
            allow_out_call=True,
            in_call_address="200 Pacific Highway, Suite 200, North Sydney NSW 2060",
            base_outcall_surcharge=Decimal("50.00"),
            per_km_fee=Decimal("3.00"),
            out_call_radius_km=25.0,
            turnaround_buffer_mins=15,
        )
        prov5 = Provider(
            tenant_id=tenant_id,
            name="Provider 5 - Sophia Loren",
            email="provider5@simplydemo.com",
            phone="0400000005",
            description="International cultural escort and travel accompaniment specialist.",
            active=True,
            is_visible=True,
            allow_in_call=True,
            allow_out_call=True,
            in_call_address="200 Pacific Highway, Suite 200, North Sydney NSW 2060",
            base_outcall_surcharge=Decimal("50.00"),
            per_km_fee=Decimal("3.00"),
            out_call_radius_km=30.0,
            turnaround_buffer_mins=20,
        )
        db.add_all([prov1, prov2, prov3, prov4, prov5])
        db.commit()
        for p in [prov1, prov2, prov3, prov4, prov5]:
            db.refresh(p)

        # Service-Provider Linkages
        sp_links = [
            # Provider 1: Services 1, 2, 4
            (prov1.id, svc1.id), (prov1.id, svc2.id), (prov1.id, svc4.id),
            # Provider 2: Services 1, 2, 3, 5
            (prov2.id, svc1.id), (prov2.id, svc2.id), (prov2.id, svc3.id), (prov2.id, svc5.id),
            # Provider 3: Services 2, 3, 4, 5 (Out-Call eligible)
            (prov3.id, svc2.id), (prov3.id, svc3.id), (prov3.id, svc4.id), (prov3.id, svc5.id),
            # Provider 4: Services 1, 2, 3
            (prov4.id, svc1.id), (prov4.id, svc2.id), (prov4.id, svc3.id),
            # Provider 5: Services 1, 2, 4, 5
            (prov5.id, svc1.id), (prov5.id, svc2.id), (prov5.id, svc4.id), (prov5.id, svc5.id),
        ]
        db.add_all([ServiceProvider(tenant_id=tenant_id, provider_id=pid, service_id=sid) for pid, sid in sp_links])
        db.commit()

        # Location Links (LocationProvider & LocationService)
        # Location 1: Providers 1, 2, 3; Services 1, 2, 3, 4, 5; Categories 1, 2
        for pid in [prov1.id, prov2.id, prov3.id]:
            db.add(LocationProvider(tenant_id=tenant_id, location_id=loc1.id, provider_id=pid))
        for sid in [svc1.id, svc2.id, svc3.id, svc4.id, svc5.id]:
            db.add(LocationService(tenant_id=tenant_id, location_id=loc1.id, service_id=sid))
        for cid in [cat1.id, cat2.id]:
            db.add(LocationCategory(tenant_id=tenant_id, location_id=loc1.id, category_id=cid))

        # Location 2: Providers 4, 5; Services 1, 2, 4, 5; Categories 1, 2
        for pid in [prov4.id, prov5.id]:
            db.add(LocationProvider(tenant_id=tenant_id, location_id=loc2.id, provider_id=pid))
        for sid in [svc1.id, svc2.id, svc4.id, svc5.id]:
            db.add(LocationService(tenant_id=tenant_id, location_id=loc2.id, service_id=sid))
        for cid in [cat1.id, cat2.id]:
            db.add(LocationCategory(tenant_id=tenant_id, location_id=loc2.id, category_id=cid))
        db.commit()

        # Provider Work Days (Realistic weekly schedules)
        # Weekdays: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        workdays = [
            # Provider 1: Mon-Fri, 10:00 - 18:00
            *[(prov1.id, loc1.id, w, "10:00", "18:00") for w in [0, 1, 2, 3, 4]],
            # Provider 2: Tue-Sat, 12:00 - 20:00
            *[(prov2.id, loc1.id, w, "12:00", "20:00") for w in [1, 2, 3, 4, 5]],
            # Provider 3: Thu-Sun, 14:00 - 22:00 (Outcall specialist)
            *[(prov3.id, None, w, "14:00", "22:00") for w in [3, 4, 5, 6]],
            # Provider 4: Mon, Wed, Fri, 10:00 - 18:00
            *[(prov4.id, loc2.id, w, "10:00", "18:00") for w in [0, 2, 4]],
            # Provider 5: Wed-Sun, 12:00 - 20:00
            *[(prov5.id, loc2.id, w, "12:00", "20:00") for w in [2, 3, 4, 5, 6]],
        ]
        for pid, lid, wday, start, end in workdays:
            db.add(ProviderWorkDay(
                tenant_id=tenant_id,
                provider_id=pid,
                location_id=lid,
                weekday=wday,
                start_time=start,
                end_time=end,
                is_working=True,
            ))
        db.commit()

        # 7. Add-Ons (5 Add-ons)
        addon1 = AddOn(tenant_id=tenant_id, name="Add-on 1 - Extended Time (+1 hr)", description="Add an additional hour to your booking.", price=Decimal("200.00"), duration=60, active=True, is_visible=True)
        addon2 = AddOn(tenant_id=tenant_id, name="Add-on 2 - Out-Call Travel Buffer", description="Extended travel radius coverage up to 50km.", price=Decimal("50.00"), duration=30, active=True, is_visible=True)
        addon3 = AddOn(tenant_id=tenant_id, name="Add-on 3 - Formal Evening Attire", description="Black-tie or formal dress code styling.", price=Decimal("75.00"), duration=0, active=True, is_visible=True)
        addon4 = AddOn(tenant_id=tenant_id, name="Add-on 4 - Priority Booking Fee", description="Guaranteed short-notice lock-in.", price=Decimal("100.00"), duration=0, active=True, is_visible=True)
        addon5 = AddOn(tenant_id=tenant_id, name="Add-on 5 - Discretion / Privacy Screen", description="Confidential non-disclosure documentation and enhanced privacy measures.", price=Decimal("50.00"), duration=0, active=True, is_visible=True)
        db.add_all([addon1, addon2, addon3, addon4, addon5])
        db.commit()
        for a in [addon1, addon2, addon3, addon4, addon5]:
            db.refresh(a)

        # Service Add-on linkages
        sa_links = [
            (svc1.id, addon1.id), (svc1.id, addon4.id), (svc1.id, addon5.id),
            (svc2.id, addon1.id), (svc2.id, addon2.id), (svc2.id, addon3.id), (svc2.id, addon4.id), (svc2.id, addon5.id),
            (svc3.id, addon1.id), (svc3.id, addon2.id), (svc3.id, addon3.id), (svc3.id, addon4.id), (svc3.id, addon5.id),
            (svc4.id, addon1.id), (svc4.id, addon3.id), (svc4.id, addon4.id), (svc4.id, addon5.id),
            (svc5.id, addon1.id), (svc5.id, addon2.id), (svc5.id, addon3.id), (svc5.id, addon4.id), (svc5.id, addon5.id),
        ]
        for sid, aid in sa_links:
            db.add(ServiceAddOn(tenant_id=tenant_id, service_id=sid, add_on_id=aid))
        db.commit()

        # 8. Products (5 Products)
        prod1 = Product(tenant_id=tenant_id, name="Product 1 - Session Extension Voucher", sku="PROD-EXT-01", description="1-hour voucher redeemable on future bookings.", price=Decimal("150.00"), active=True, is_visible=True)
        prod2 = Product(tenant_id=tenant_id, name="Product 2 - Travel Accompaniment Retainer", sku="PROD-RET-02", description="Retainer credit for domestic travel assignments.", price=Decimal("300.00"), active=True, is_visible=True)
        prod3 = Product(tenant_id=tenant_id, name="Product 3 - Client Verification Pass", sku="PROD-VER-03", description="Fast-track identity clearance and verified member badge.", price=Decimal("25.00"), active=True, is_visible=True)
        prod4 = Product(tenant_id=tenant_id, name="Product 4 - Standard Travel Fee", sku="PROD-TRV-04", description="Pre-calculated zone travel compensation.", price=Decimal("50.00"), active=True, is_visible=True)
        prod5 = Product(tenant_id=tenant_id, name="Product 5 - Beverage / Hospitality Package", sku="PROD-BEV-05", description="Premium curated champagne and refreshment service.", price=Decimal("80.00"), active=True, is_visible=True)
        db.add_all([prod1, prod2, prod3, prod4, prod5])
        db.commit()
        for pr in [prod1, prod2, prod3, prod4, prod5]:
            db.refresh(pr)

        # Service-Product & Location-Product associations
        for p in [prod1, prod2, prod3, prod4, prod5]:
            db.add(ServiceProduct(tenant_id=tenant_id, service_id=svc2.id, product_id=p.id))
            db.add(LocationProduct(tenant_id=tenant_id, location_id=loc1.id, product_id=p.id))
        db.commit()

        # 9. Packages (2 Packages)
        pkg1 = ServicePackage(
            tenant_id=tenant_id,
            name="Package 1 - Weekend Social Package",
            description="Curated weekend bundle: Dinner date followed by extended companion engagement.",
            price=Decimal("1200.00"),
            active=True,
            is_visible=True,
        )
        pkg2 = ServicePackage(
            tenant_id=tenant_id,
            name="Package 2 - Executive Dinner & Accompaniment Package",
            description="VIP private session followed by an executive outcall dinner engagement.",
            price=Decimal("750.00"),
            active=True,
            is_visible=True,
        )
        db.add_all([pkg1, pkg2])
        db.commit()
        db.refresh(pkg1)
        db.refresh(pkg2)

        # Package Steps
        db.add_all([
            PackageStep(package_id=pkg1.id, service_id=svc2.id, order=1, offset_days=0, price=Decimal("500.00")),
            PackageStep(package_id=pkg1.id, service_id=svc4.id, order=2, offset_days=1, price=Decimal("700.00")),
            PackageStep(package_id=pkg2.id, service_id=svc1.id, order=1, offset_days=0, price=Decimal("300.00")),
            PackageStep(package_id=pkg2.id, service_id=svc3.id, order=2, offset_days=7, price=Decimal("450.00")),
        ])
        db.commit()

        # 10. Clients (5 Clients)
        clients_data = [
            ("Client 1 - Julian Hayes", "julian.hayes@example.com", "0411000001", "12 Ocean Avenue", "Double Bay", "2028"),
            ("Client 2 - Victoria Sterling", "victoria.sterling@example.com", "0411000002", "45 Raglan Street", "Mosman", "2088"),
            ("Client 3 - David Kensington", "david.kensington@example.com", "0411000003", "88 Barangaroo Avenue", "Barangaroo", "2000"),
            ("Client 4 - Eleanor Vance", "eleanor.vance@example.com", "0411000004", "15 Belgrave Street", "Manly", "2095"),
            ("Client 5 - Harrison Forde", "harrison.forde@example.com", "0411000005", "24 New South Head Road", "Rose Bay", "2029"),
        ]
        clients = []
        for name, email, phone, addr, suburb, postcode in clients_data:
            c = Client(
                tenant_id=tenant_id,
                name=name,
                email=email,
                phone=phone,
                address_line1=addr,
                city=suburb,
                state="NSW",
                postcode=postcode,
                country="Australia",
                timezone="Australia/Sydney",
                active=True,
            )
            db.add(c)
            clients.append(c)
        db.commit()
        for c in clients:
            db.refresh(c)

        print("[3/4] SEEDING REALISTIC LIFECYCLE BOOKINGS & ALLOCATIONS...")

        # Current benchmark time (Sydney 2026-09-27 16:30 AEST / UTC 06:30)
        # Using aware UTC timestamps
        ref_now = datetime(2026, 9, 27, 6, 30, tzinfo=timezone.utc)

        # Helper to create slots and invoices
        def create_booking_with_records(
            provider, service, client, start_dt, end_dt, status,
            service_mode=ServiceMode.IN_CALL.value, location=None, resource=None,
            notes=None, travel_distance=None, travel_fee=None, suburb=None, postcode=None, address=None
        ) -> Booking:
            b = Booking(
                tenant_id=tenant_id,
                client_id=client.id,
                provider_id=provider.id,
                service_id=service.id,
                location_id=location.id if location else None,
                start_time=start_dt,
                end_time=end_dt,
                status=status,
                service_mode=service_mode,
                service_address=address or (location.address if location else None),
                client_suburb=suburb,
                client_postcode=postcode,
                chargeable_travel_distance_km=travel_distance,
                chargeable_travel_fee=Decimal(str(travel_fee)) if travel_fee is not None else None,
                notes=notes,
            )
            db.add(b)
            db.commit()
            db.refresh(b)

            # 15-minute slot allocations for active, confirmed, in-progress, completed
            if status in [BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED]:
                cur_slot = start_dt
                while cur_slot < end_dt:
                    db.add(BookingSlotAllocation(
                        tenant_id=tenant_id,
                        booking_id=b.id,
                        provider_id=provider.id,
                        slot_start=cur_slot
                    ))
                    cur_slot += timedelta(minutes=15)
                db.commit()

            # Resource allocation for In-Call
            if service_mode == ServiceMode.IN_CALL.value and resource:
                db.add(BookingResourceAllocation(
                    booking_id=b.id,
                    resource_id=resource.id,
                    quantity=1
                ))
                db.commit()

            # Invoices & Payments for completed bookings
            if status == BookingStatus.COMPLETED:
                svc_price = service.price if service_mode == ServiceMode.IN_CALL.value else (service.outcall_price or service.price)
                fee = Decimal(str(travel_fee or 0.00))
                total = Decimal(str(svc_price)) + fee

                inv = Invoice(
                    tenant_id=tenant_id,
                    booking_id=b.id,
                    client_id=client.id,
                    currency="AUD",
                    subtotal=total,
                    total=total,
                    amount_paid=total,
                    status="paid",
                    notes=f"Tax invoice for booking #{b.id} - {service.name}",
                )
                db.add(inv)
                db.commit()
                db.refresh(inv)

                # Line item
                db.add(InvoiceLine(
                    tenant_id=tenant_id,
                    invoice_id=inv.id,
                    line_type="service",
                    item_id=service.id,
                    description=f"{service.name} ({service.duration} mins)",
                    quantity=1,
                    unit_price=svc_price,
                    amount=svc_price,
                ))
                if fee > 0:
                    db.add(InvoiceLine(
                        tenant_id=tenant_id,
                        invoice_id=inv.id,
                        line_type="fee",
                        description=f"Out-Call Travel Fee ({travel_distance} km)",
                        quantity=1,
                        unit_price=fee,
                        amount=fee,
                    ))
                db.commit()

                # Payment record
                db.add(Payment(
                    tenant_id=tenant_id,
                    booking_id=b.id,
                    amount=total,
                    currency="AUD",
                    status="completed",
                ))
                db.commit()

            elif status == BookingStatus.CONFIRMED:
                # Add deposit invoice if service requires deposit
                if service.deposit_amount and service.deposit_amount > 0:
                    inv = Invoice(
                        tenant_id=tenant_id,
                        booking_id=b.id,
                        client_id=client.id,
                        currency="AUD",
                        subtotal=service.deposit_amount,
                        total=service.deposit_amount,
                        amount_paid=service.deposit_amount,
                        status="partially_paid",
                        notes=f"Deposit invoice for booking #{b.id}",
                    )
                    db.add(inv)
                    db.commit()
                    db.refresh(inv)
                    db.add(Payment(
                        tenant_id=tenant_id,
                        booking_id=b.id,
                        amount=service.deposit_amount,
                        currency="AUD",
                        status="completed",
                    ))
                    db.commit()

            return b

        # -------------------------------------------------------------------------
        # Seed 12 COMPLETED Bookings (Historical: Sept 1 - Sept 25, 2026)
        # Note: Sydney time AEST is UTC+10.
        # e.g., 10:00 Sydney = 00:00 UTC. 14:00 Sydney = 04:00 UTC. 18:00 Sydney = 08:00 UTC.
        # -------------------------------------------------------------------------
        completed_bookings = [
            # 1. Prov 1 In-call VIP Session (Sept 2, 2026 Wed 11:00-12:00 Sydney / 01:00-02:00 UTC)
            (prov1, svc1, clients[0], datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc), datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_1, "Smooth inaugural consultation", None, None, None, None, None),

            # 2. Prov 1 In-call Social Date (Sept 4, 2026 Fri 14:00-16:00 Sydney / 04:00-06:00 UTC)
            (prov1, svc2, clients[1], datetime(2026, 9, 4, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_2, "Executive dinner briefing", None, None, None, None, None),

            # 3. Prov 2 Out-call Executive Appt (Sept 5, 2026 Sat 13:00-14:30 Sydney / 03:00-04:30 UTC)
            (prov2, svc3, clients[2], datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc), datetime(2026, 9, 5, 4, 30, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Barangaroo penthouse appointment", 8.5, 75.50, "Barangaroo", "2000", "88 Barangaroo Ave"),

            # 4. Prov 2 In-call VIP Session (Sept 8, 2026 Tue 15:00-16:00 Sydney / 05:00-06:00 UTC)
            (prov2, svc1, clients[3], datetime(2026, 9, 8, 5, 0, tzinfo=timezone.utc), datetime(2026, 9, 8, 6, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_1, "Excellent feedback received", None, None, None, None, None),

            # 5. Prov 3 Out-call Social Accompaniment (Sept 10, 2026 Thu 18:00-20:00 Sydney / 08:00-10:00 UTC)
            (prov3, svc2, clients[4], datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc), datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Bennelong Restaurant dinner date", 12.0, 86.00, "Sydney CBD", "2000", "Bennelong, Sydney Opera House"),

            # 6. Prov 4 In-call VIP Session (Sept 11, 2026 Fri 11:00-12:00 Sydney / 01:00-02:00 UTC)
            (prov4, svc1, clients[0], datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc), datetime(2026, 9, 11, 2, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc2, res_loc2_1, "North Sydney studio session", None, None, None, None, None),

            # 7. Prov 5 Out-call Evening Companion (Sept 12, 2026 Sat 16:00-20:00 Sydney / 06:00-10:00 UTC)
            (prov5, svc4, clients[1], datetime(2026, 9, 12, 6, 0, tzinfo=timezone.utc), datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Balmoral beachside charity gala", 14.2, 92.60, "Mosman", "2088", "45 Raglan Street"),

            # 8. Prov 1 Out-call Social Date (Sept 15, 2026 Tue 12:00-14:00 Sydney / 02:00-04:00 UTC)
            (prov1, svc2, clients[2], datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc), datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Crown Sydney lunch accompaniment", 6.0, 68.00, "Barangaroo", "2000", "Crown Sydney, Barangaroo"),

            # 9. Prov 3 Out-call Executive Appt (Sept 18, 2026 Fri 15:00-16:30 Sydney / 05:00-06:30 UTC)
            (prov3, svc3, clients[3], datetime(2026, 9, 18, 5, 0, tzinfo=timezone.utc), datetime(2026, 9, 18, 6, 30, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Manly Pacific Hotel suite visit", 16.5, 99.50, "Manly", "2095", "55 North Steyne"),

            # 10. Prov 2 In-call VIP Session (Sept 22, 2026 Tue 13:00-14:00 Sydney / 03:00-04:00 UTC)
            (prov2, svc1, clients[4], datetime(2026, 9, 22, 3, 0, tzinfo=timezone.utc), datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_2, "Repeat client booking", None, None, None, None, None),

            # 11. Prov 4 In-call Social Date (Sept 23, 2026 Wed 14:00-16:00 Sydney / 04:00-06:00 UTC)
            (prov4, svc2, clients[0], datetime(2026, 9, 23, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc2, res_loc2_2, "Afternoon corporate function prep", None, None, None, None, None),

            # 12. Prov 5 In-call Studio Session (Sept 25, 2026 Fri 14:00-15:00 Sydney / 04:00-05:00 UTC)
            (prov5, svc1, clients[1], datetime(2026, 9, 25, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 25, 5, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc2, res_loc2_1, "Studio session completed", None, None, None, None, None),
        ]

        for prov, svc, cli, s_dt, e_dt, mode, loc, res, notes, dist, fee, sub, post, addr in completed_bookings:
            create_booking_with_records(
                prov, svc, cli, s_dt, e_dt, BookingStatus.COMPLETED,
                service_mode=mode, location=loc, resource=res, notes=notes,
                travel_distance=dist, travel_fee=fee, suburb=sub, postcode=post, address=addr
            )

        # -------------------------------------------------------------------------
        # Seed 1 IN-PROGRESS Active Booking (Today: Sept 27, 2026 15:30-17:30 Sydney / 05:30-07:30 UTC)
        # -------------------------------------------------------------------------
        in_prog_start = datetime(2026, 9, 27, 5, 30, tzinfo=timezone.utc)
        in_prog_end = datetime(2026, 9, 27, 7, 30, tzinfo=timezone.utc)
        create_booking_with_records(
            prov1, svc2, clients[2], in_prog_start, in_prog_end, BookingStatus.IN_PROGRESS,
            service_mode=ServiceMode.IN_CALL.value, location=loc1, resource=res_loc1_1,
            notes="Active appointment currently in session at Executive Suite A."
        )

        # -------------------------------------------------------------------------
        # Seed 6 CONFIRMED Upcoming Bookings (Next 1-2 weeks: Sept 28 - Oct 8, 2026)
        # -------------------------------------------------------------------------
        confirmed_bookings = [
            # 1. Prov 1 VIP Session (Sept 28, 2026 Mon 11:00-12:00 Sydney / 01:00-02:00 UTC)
            (prov1, svc1, clients[3], datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc), datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_1, "Confirmed - deposit received", None, None, None, None, None),

            # 2. Prov 2 Out-call Executive Appt (Sept 29, 2026 Tue 14:00-15:30 Sydney / 04:00-05:30 UTC)
            (prov2, svc3, clients[4], datetime(2026, 9, 29, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 29, 5, 30, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Confirmed outcall - The Langham Sydney", 5.5, 66.50, "Millers Point", "2000", "89 Kent Street"),

            # 3. Prov 3 Out-call Social Date (Oct 1, 2026 Thu 18:00-20:00 Sydney / 08:00-10:00 UTC)
            (prov3, svc2, clients[0], datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc), datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Dinner at Quay Restaurant confirmed", 7.0, 71.00, "The Rocks", "2000", "Upper Level, Overseas Passenger Terminal"),

            # 4. Prov 4 In-call VIP Session (Oct 2, 2026 Fri 10:30-11:30 Sydney / 00:30-01:30 UTC)
            (prov4, svc1, clients[1], datetime(2026, 10, 2, 0, 30, tzinfo=timezone.utc), datetime(2026, 10, 2, 1, 30, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc2, res_loc2_1, "Private studio booking confirmed", None, None, None, None, None),

            # 5. Prov 5 Out-call Travel Accompaniment (Oct 4, 2026 Sun 12:00-20:00 Sydney / 02:00-10:00 UTC)
            (prov5, svc5, clients[2], datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc), datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Full day Hunter Valley private tour accompaniment", 45.0, 185.00, "Hunter Valley", "2320", "Private Pick-up"),

            # 6. Prov 1 In-call Evening Companion (Oct 7, 2026 Wed 13:00-17:00 Sydney / 03:00-07:00 UTC)
            (prov1, svc4, clients[3], datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc), datetime(2026, 10, 7, 7, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, res_loc1_2, "Extended afternoon suite engagement confirmed", None, None, None, None, None),
        ]

        for prov, svc, cli, s_dt, e_dt, mode, loc, res, notes, dist, fee, sub, post, addr in confirmed_bookings:
            create_booking_with_records(
                prov, svc, cli, s_dt, e_dt, BookingStatus.CONFIRMED,
                service_mode=mode, location=loc, resource=res, notes=notes,
                travel_distance=dist, travel_fee=fee, suburb=sub, postcode=post, address=addr
            )

        # -------------------------------------------------------------------------
        # Seed 3 PENDING Bookings (Awaiting confirmation / deposit)
        # -------------------------------------------------------------------------
        pending_bookings = [
            (prov2, svc2, clients[0], datetime(2026, 9, 30, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, None, "Pending - awaiting client confirmation via SMS"),
            (prov3, svc3, clients[1], datetime(2026, 10, 2, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 2, 7, 30, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, None, "Pending outcall - awaiting address verification"),
            (prov5, svc1, clients[4], datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc), datetime(2026, 10, 3, 5, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc2, None, "Pending - client requested custom catering"),
        ]
        for prov, svc, cli, s_dt, e_dt, mode, loc, res, notes in pending_bookings:
            create_booking_with_records(
                prov, svc, cli, s_dt, e_dt, BookingStatus.PENDING,
                service_mode=mode, location=loc, resource=res, notes=notes
            )

        # -------------------------------------------------------------------------
        # Seed 2 CANCELLED Bookings (With audit reasons)
        # -------------------------------------------------------------------------
        cancelled_bookings = [
            (prov1, svc1, clients[4], datetime(2026, 9, 14, 2, 0, tzinfo=timezone.utc), datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, "Client called 48 hours prior to cancel due to interstate flight delay."),
            (prov4, svc3, clients[2], datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc), datetime(2026, 9, 21, 4, 30, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, "Cancelled by staff - severe weather warning impacting regional travel."),
        ]
        for prov, svc, cli, s_dt, e_dt, mode, loc, notes in cancelled_bookings:
            create_booking_with_records(
                prov, svc, cli, s_dt, e_dt, BookingStatus.CANCELLED,
                service_mode=mode, location=loc, notes=notes
            )

        # -------------------------------------------------------------------------
        # Seed 2 NO-SHOW Bookings (Historical)
        # -------------------------------------------------------------------------
        noshow_bookings = [
            (prov2, svc1, clients[3], datetime(2026, 9, 7, 4, 0, tzinfo=timezone.utc), datetime(2026, 9, 7, 5, 0, tzinfo=timezone.utc),
             ServiceMode.IN_CALL.value, loc1, "Client failed to attend. Non-responsive to reminder phone calls and SMS."),
            (prov3, svc2, clients[0], datetime(2026, 9, 17, 7, 0, tzinfo=timezone.utc), datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc),
             ServiceMode.OUT_CALL.value, None, "Out-call destination hotel concierge reported guest had checked out early."),
        ]
        for prov, svc, cli, s_dt, e_dt, mode, loc, notes in noshow_bookings:
            create_booking_with_records(
                prov, svc, cli, s_dt, e_dt, BookingStatus.NO_SHOW,
                service_mode=mode, location=loc, notes=notes
            )

        print("[4/4] VERIFYING SEEDED DATABASE COUNTS...")
        counts = {
            "locations": db.query(Location).filter(Location.tenant_id == tenant_id).count(),
            "resources": db.query(Resource).filter(Resource.tenant_id == tenant_id).count(),
            "categories": db.query(Category).filter(Category.tenant_id == tenant_id).count(),
            "services": db.query(Service).filter(Service.tenant_id == tenant_id).count(),
            "providers": db.query(Provider).filter(Provider.tenant_id == tenant_id).count(),
            "provider_workdays": db.query(ProviderWorkDay).filter(ProviderWorkDay.tenant_id == tenant_id).count(),
            "add_ons": db.query(AddOn).filter(AddOn.tenant_id == tenant_id).count(),
            "products": db.query(Product).filter(Product.tenant_id == tenant_id).count(),
            "packages": db.query(ServicePackage).filter(ServicePackage.tenant_id == tenant_id).count(),
            "clients": db.query(Client).filter(Client.tenant_id == tenant_id).count(),
            "bookings_total": db.query(Booking).filter(Booking.tenant_id == tenant_id).count(),
            "bookings_completed": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.COMPLETED).count(),
            "bookings_in_progress": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.IN_PROGRESS).count(),
            "bookings_confirmed": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.CONFIRMED).count(),
            "bookings_pending": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.PENDING).count(),
            "bookings_cancelled": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.CANCELLED).count(),
            "bookings_no_show": db.query(Booking).filter(Booking.tenant_id == tenant_id, Booking.status == BookingStatus.NO_SHOW).count(),
            "slot_allocations": db.query(BookingSlotAllocation).filter(BookingSlotAllocation.tenant_id == tenant_id).count(),
            "invoices": db.query(Invoice).filter(Invoice.tenant_id == tenant_id).count(),
            "payments": db.query(Payment).filter(Payment.tenant_id == tenant_id).count(),
        }

        print("\n=== SEED RESULTS SUMMARY ===")
        for k, v in counts.items():
            print(f"  {k:24s}: {v}")

        return counts

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_demo_structured_catalog()
