"""Idempotent seed script to populate clean numbered traceable entities for SimplyDemo.

Entities:
- Provider 1, Provider 2 (with clear profiles and assigned services)
- Location 1 ("Location 1 - Main Center"), Location 2 ("Location 2 - North Clinic")
- Category 1, Category 2
- Service 1 ("Service 1 - Standard Consultation 60m"), Service 2 ("Service 2 - Express Follow-up 30m"),
  Service 3 ("Service 3 - Premium Assessment 90m"), Service 4 ("Service 4 - Holistic Wellness 45m"),
  Service 5 ("Service 5 - Rapid Triage 15m")
- Add-on 1 ("Add-on 1 - Extended Care (15m)"), Add-on 2, Add-on 3
- Product 1 ("Product 1 - Essential Kit"), Product 2, Product 3
- Client 1 ("Client 1 - Alice Walker", 0411000001), Client 2 ("Client 2 - Bob Taylor", 0411000002),
  Client 3 ("Client 3 - Charlie Evans", 0411000003), Client 4 ("Client 4 - Diana Prince", 0411000004),
  Client 5 ("Client 5 - Evan Wright", 0411000005)
- SMS Accounts for Provider 1 & 2
- Active & Historical Bookings, Invoices, and Arrivals
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any

from app.db.database import SessionLocal, Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.location import Location, LocationProvider, LocationService, LocationCategory, LocationProduct
from app.models.booking import Booking
from app.models.service_provider import ServiceProvider
from app.models.schedule import ProviderWorkDay
from app.models.category import Category, ServiceCategory
from app.models.addon import AddOn, ServiceAddOn
from app.models.product import Product, ServiceProduct
from app.models.package import ServicePackage, PackageStep
from app.models.resource import Resource, ServiceResourceRequirement
from app.models.additional_field import AdditionalField
from app.models.webhook import WebhookRegistration
from app.models.notification import NotificationTemplate, ReminderRule
from app.models.checkout import TaxRate, PaymentProcessorConfig, Invoice, InvoiceLine
from app.models.payment import Payment
from app.models.audit import AuditLog
from app.models.management_review_request import ManagementReviewRequest
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_arrival import SmsArrivalSession
from app.models.sms_outbox import SmsConversationEvent, SmsOutboundJob, SmsAiJob
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.models.sms_quick_tool import SmsQuickTool
from app.models.client_dispute import ClientDispute, init_dispute_tables
from app.core.security import get_password_hash

from app.core.state_machine import BookingStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_clean_numbered_data")


def ensure_database_schema(db):
    """Ensure newly added columns and tables exist in PostgreSQL database."""
    from sqlalchemy import text
    statements = [
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE;",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN NOT NULL DEFAULT FALSE;",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN NOT NULL DEFAULT TRUE;",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS chatwoot_conversation_id INTEGER NULL;",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS chatwoot_contact_id INTEGER NULL;",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'sms';",
        "ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS chatwoot_inbox_id INTEGER NULL;",
        "ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS chatwoot_message_id INTEGER NULL;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS throughput_limit INTEGER NOT NULL DEFAULT 60;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS quiet_hours_start VARCHAR NULL;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS quiet_hours_end VARCHAR NULL;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS autoresponder_enabled BOOLEAN NOT NULL DEFAULT FALSE;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS autoresponder_text TEXT NULL;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN NOT NULL DEFAULT FALSE;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS ai_mode VARCHAR NOT NULL DEFAULT 'off';",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS line_prompt TEXT NULL;",
        "ALTER TABLE sms_accounts ADD COLUMN IF NOT EXISTS catchup_cutoff_days INTEGER NOT NULL DEFAULT 30;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 5;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS error_code VARCHAR NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS lease_owner VARCHAR NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS lease_token VARCHAR NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS dispatch_started_at TIMESTAMPTZ NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS provider_delivery_id VARCHAR NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS terminal_at TIMESTAMPTZ NULL;",
        "ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS webhook_snapshot_at TIMESTAMPTZ NULL;",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR NOT NULL DEFAULT 'starter';",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS addon_quota INTEGER NOT NULL DEFAULT 0;",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS enabled_modules JSON NULL;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_id INTEGER REFERENCES providers(id) ON DELETE SET NULL;",
        """CREATE TABLE IF NOT EXISTS client_disputes (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
            status VARCHAR NOT NULL DEFAULT 'submitted',
            reason VARCHAR NOT NULL,
            description TEXT NOT NULL,
            preferred_resolution VARCHAR NOT NULL DEFAULT 'redo_service',
            resolution_notes TEXT NULL,
            photos JSON NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ NULL
        );""",
        "CREATE INDEX IF NOT EXISTS ix_client_disputes_tenant_id ON client_disputes(tenant_id);",
        "CREATE INDEX IF NOT EXISTS ix_client_disputes_client_id ON client_disputes(client_id);",
        "CREATE INDEX IF NOT EXISTS ix_client_disputes_booking_id ON client_disputes(booking_id);",
    ]
    for stmt in statements:

        try:
            db.execute(text(stmt))
            db.commit()
        except Exception as ex:
            db.rollback()
            logger.debug("Schema alter skipped: %s", ex)

    try:
        Base.metadata.create_all(bind=db.get_bind())
    except Exception as e:
        logger.warning("Base.metadata.create_all note: %s", e)


def seed_numbered_mock_data(db=None, reset_existing: bool = True) -> Dict[str, Any]:
    """Populate clean numbered mock entities idempotently."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Ensure all columns and tables exist
        ensure_database_schema(db)

        # 1. Tenant lookup or create
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
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            logger.info("Created tenant SimplyDemo (subdomain: simplydemo)")
        else:
            tenant.subscription_tier = "unlimited"
            tenant.addon_quota = 999
            tenant.address = "100 Main Street, Suite 100, Sydney NSW 2000"
            tenant.latitude = -33.8688
            tenant.longitude = 151.2093
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            logger.info(f"Found existing tenant SimplyDemo (id: {tenant.id}) - ensured unlimited tier & Sydney coordinates")

        tenant_id = tenant.id

        if reset_existing:
            logger.info("Cleaning previous records for tenant %s to ensure clean numbered data...", tenant_id)

            def safe_delete(model_or_query):
                try:
                    if hasattr(model_or_query, "delete"):
                        model_or_query.delete(synchronize_session=False)
                    else:
                        db.query(model_or_query).filter(model_or_query.tenant_id == tenant_id).delete(synchronize_session=False)
                    db.commit()
                except Exception as ex:
                    db.rollback()
                    logger.debug("safe_delete skipped/failed for query: %s", ex)

            # Delete in reverse foreign key order
            try:
                db.query(SmsArrivalSession).filter(
                    SmsArrivalSession.booking_id.in_(
                        db.query(Booking.id).filter(Booking.tenant_id == tenant_id)
                    )
                ).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()

            safe_delete(db.query(SmsMessage).filter(SmsMessage.tenant_id == tenant_id))
            safe_delete(db.query(SmsAiJob))
            safe_delete(db.query(SmsConversationEvent))
            safe_delete(db.query(SmsOutboundJob))
            safe_delete(db.query(SmsConversation).filter(SmsConversation.tenant_id == tenant_id))
            safe_delete(db.query(SmsQuickTool).filter(SmsQuickTool.tenant_id == tenant_id))
            safe_delete(db.query(SmsKnowledgeEntry).filter(SmsKnowledgeEntry.tenant_id == tenant_id))
            safe_delete(db.query(SmsAccount).filter(SmsAccount.tenant_id == tenant_id))

            safe_delete(ClientDispute)
            safe_delete(ManagementReviewRequest)

            safe_delete(AuditLog)
            safe_delete(Payment)
            safe_delete(InvoiceLine)
            safe_delete(Invoice)
            safe_delete(PaymentProcessorConfig)
            safe_delete(TaxRate)
            safe_delete(ReminderRule)
            safe_delete(NotificationTemplate)
            safe_delete(WebhookRegistration)
            safe_delete(AdditionalField)

            safe_delete(Booking)
            safe_delete(ProviderWorkDay)
            safe_delete(db.query(PackageStep))
            safe_delete(db.query(ServicePackage))
            safe_delete(db.query(ServiceResourceRequirement))
            safe_delete(Resource)

            safe_delete(LocationProvider)
            safe_delete(LocationService)
            safe_delete(LocationCategory)
            safe_delete(LocationProduct)

            safe_delete(ServiceProvider)
            safe_delete(ServiceCategory)
            safe_delete(ServiceAddOn)
            safe_delete(ServiceProduct)

            safe_delete(Client)
            safe_delete(Location)
            safe_delete(Product)
            safe_delete(AddOn)
            safe_delete(Category)
            safe_delete(Service)
            safe_delete(Provider)

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
            logger.info("Admin user ensured: admin / admin123")

        # 3. Locations (Numbered)
        loc1 = Location(
            tenant_id=tenant_id,
            name="Location 1 - Main Center",
            address="100 Main Street, Suite 100, Sydney NSW 2000",
            timezone="Australia/Sydney",
            active=True,
            is_visible=True
        )
        loc2 = Location(
            tenant_id=tenant_id,
            name="Location 2 - North Clinic",
            address="200 Pacific Highway, Suite 200, North Sydney NSW 2060",
            timezone="Australia/Sydney",
            active=True,
            is_visible=True
        )
        db.add_all([loc1, loc2])
        db.commit()
        db.refresh(loc1)
        db.refresh(loc2)
        logger.info("Seeded Location 1 and Location 2")

        # 4. Providers (Numbered)
        prov1 = Provider(
            tenant_id=tenant_id,
            name="Provider 1 - Dr. Sarah Bennett",
            email="provider1@example.com",
            phone="0400000001",
            active=True,
            is_visible=True,
            capacity=1,
            description="Lead Consultant specializing in Standard Consultations and Premium Assessments."
        )
        prov2 = Provider(
            tenant_id=tenant_id,
            name="Provider 2 - Marcus Vance",
            email="provider2@example.com",
            phone="0400000002",
            active=True,
            is_visible=True,
            capacity=1,
            description="Senior Wellness Specialist delivering Holistic Care and Rapid Triage."
        )
        db.add_all([prov1, prov2])
        db.commit()
        db.refresh(prov1)
        db.refresh(prov2)
        logger.info("Seeded Provider 1 and Provider 2")

        # Provider Workdays (Mon-Fri 09:00 - 17:00)
        for prov in [prov1, prov2]:
            for weekday in range(5):  # Mon (0) to Fri (4)
                db.add(ProviderWorkDay(
                    tenant_id=tenant_id,
                    provider_id=prov.id,
                    weekday=weekday,
                    start_time="09:00",
                    end_time="17:00",
                    is_working=True
                ))
        db.commit()

        # 5. SMS Accounts for Providers (Numbered lines)
        sms_acc1 = SmsAccount(
            tenant_id=tenant_id,
            provider_id=prov1.id,
            transport_type="simulator",
            display_name="Provider 1 Line (Dr. Sarah Bennett)",
            sender_address="0400000001",
            is_enabled=True,
            ai_enabled=True,
            ai_mode="draft",
            autoresponder_enabled=True,
            autoresponder_text="Hello from Dr. Sarah Bennett's clinic! We have received your message and will get back to you shortly.",
            throughput_limit=60
        )
        sms_acc2 = SmsAccount(
            tenant_id=tenant_id,
            provider_id=prov2.id,
            transport_type="simulator",
            display_name="Provider 2 Line (Marcus Vance)",
            sender_address="0400000002",
            is_enabled=True,
            ai_enabled=True,
            ai_mode="draft",
            autoresponder_enabled=True,
            autoresponder_text="Hello from Marcus Vance Clinic. We'll be in touch with you right away.",
            throughput_limit=60
        )
        db.add_all([sms_acc1, sms_acc2])
        db.commit()
        db.refresh(sms_acc1)
        db.refresh(sms_acc2)
        logger.info("Seeded SMS Accounts for Provider 1 and Provider 2")

        # 6. Categories (Numbered)
        cat1 = Category(
            tenant_id=tenant_id,
            name="Category 1 - Consultations & Assessments",
            description="Comprehensive consultations and clinical diagnostics.",
            active=True
        )
        cat2 = Category(
            tenant_id=tenant_id,
            name="Category 2 - Wellness & Express Care",
            description="Holistic health sessions and rapid triage treatments.",
            active=True
        )
        db.add_all([cat1, cat2])
        db.commit()
        db.refresh(cat1)
        db.refresh(cat2)

        # 7. Services (Numbered 1 to 5)
        srv1 = Service(
            tenant_id=tenant_id,
            name="Service 1 - Standard Consultation 60m",
            description="Standard 60-minute in-depth consultation with assigned practitioner.",
            duration=60,
            price=Decimal("120.00"),
            buffer_before=10,
            buffer_after=10,
            active=True,
            is_visible=True
        )
        srv2 = Service(
            tenant_id=tenant_id,
            name="Service 2 - Express Follow-up 30m",
            description="Rapid 30-minute follow-up and progress review session.",
            duration=30,
            price=Decimal("65.00"),
            buffer_before=5,
            buffer_after=5,
            active=True,
            is_visible=True
        )
        srv3 = Service(
            tenant_id=tenant_id,
            name="Service 3 - Premium Assessment 90m",
            description="Comprehensive 90-minute full body and diagnostic health evaluation.",
            duration=90,
            price=Decimal("195.00"),
            buffer_before=15,
            buffer_after=15,
            active=True,
            is_visible=True
        )
        srv4 = Service(
            tenant_id=tenant_id,
            name="Service 4 - Holistic Wellness 45m",
            description="Tailored holistic therapy and wellness session with Marcus Vance.",
            duration=45,
            price=Decimal("95.00"),
            buffer_before=10,
            buffer_after=10,
            active=True,
            is_visible=True
        )
        srv5 = Service(
            tenant_id=tenant_id,
            name="Service 5 - Rapid Triage 15m",
            description="15-minute quick check and urgent triage consultation.",
            duration=15,
            price=Decimal("40.00"),
            buffer_before=5,
            buffer_after=5,
            active=True,
            is_visible=True
        )
        db.add_all([srv1, srv2, srv3, srv4, srv5])
        db.commit()
        for s in [srv1, srv2, srv3, srv4, srv5]:
            db.refresh(s)
        logger.info("Seeded Services 1..5")

        # 8. Service Provider Mappings
        # Provider 1: Service 1, Service 2, Service 3
        # Provider 2: Service 1, Service 4, Service 5
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov1.id, service_id=srv1.id))
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov1.id, service_id=srv2.id))
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov1.id, service_id=srv3.id))
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov2.id, service_id=srv1.id))
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov2.id, service_id=srv4.id))
        db.add(ServiceProvider(tenant_id=tenant_id, provider_id=prov2.id, service_id=srv5.id))

        # 9. Service Category Mappings
        db.add(ServiceCategory(tenant_id=tenant_id, service_id=srv1.id, category_id=cat1.id))
        db.add(ServiceCategory(tenant_id=tenant_id, service_id=srv2.id, category_id=cat1.id))
        db.add(ServiceCategory(tenant_id=tenant_id, service_id=srv3.id, category_id=cat1.id))
        db.add(ServiceCategory(tenant_id=tenant_id, service_id=srv4.id, category_id=cat2.id))
        db.add(ServiceCategory(tenant_id=tenant_id, service_id=srv5.id, category_id=cat2.id))

        # 10. Add-ons (Numbered)
        addon1 = AddOn(
            tenant_id=tenant_id,
            name="Add-on 1 - Extended Care (15m)",
            description="Add 15 extra minutes of dedicated practitioner care to your session.",
            price=Decimal("30.00"),
            duration=15,
            active=True
        )
        addon2 = AddOn(
            tenant_id=tenant_id,
            name="Add-on 2 - Premium Diagnostics",
            description="Comprehensive pathology panel & instant digital report.",
            price=Decimal("50.00"),
            duration=0,
            active=True
        )
        addon3 = AddOn(
            tenant_id=tenant_id,
            name="Add-on 3 - Warm Compresses & Oils",
            description="Therapeutic heated herbal compress treatment during session.",
            price=Decimal("25.00"),
            duration=10,
            active=True
        )
        db.add_all([addon1, addon2, addon3])
        db.commit()
        db.refresh(addon1)
        db.refresh(addon2)
        db.refresh(addon3)

        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv1.id, add_on_id=addon1.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv1.id, add_on_id=addon2.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv3.id, add_on_id=addon1.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv3.id, add_on_id=addon2.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv3.id, add_on_id=addon3.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv4.id, add_on_id=addon1.id))
        db.add(ServiceAddOn(tenant_id=tenant_id, service_id=srv4.id, add_on_id=addon3.id))

        # 11. Products (Numbered)
        prod1 = Product(
            tenant_id=tenant_id,
            name="Product 1 - Essential Kit",
            description="Foundational wellness kit for home care and ongoing support.",
            price=Decimal("45.00"),
            sku="PROD-001",
            active=True
        )
        prod2 = Product(
            tenant_id=tenant_id,
            name="Product 2 - Recovery Balm",
            description="Soothing herbal balm for targeted joint & muscle relief.",
            price=Decimal("28.00"),
            sku="PROD-002",
            active=True
        )
        prod3 = Product(
            tenant_id=tenant_id,
            name="Product 3 - Maintenance Pack",
            description="Monthly supply pack for sustained health and immunity.",
            price=Decimal("60.00"),
            sku="PROD-003",
            active=True
        )
        db.add_all([prod1, prod2, prod3])
        db.commit()
        db.refresh(prod1)
        db.refresh(prod2)
        db.refresh(prod3)

        db.add(ServiceProduct(tenant_id=tenant_id, service_id=srv1.id, product_id=prod1.id))
        db.add(ServiceProduct(tenant_id=tenant_id, service_id=srv3.id, product_id=prod1.id))
        db.add(ServiceProduct(tenant_id=tenant_id, service_id=srv3.id, product_id=prod2.id))
        db.add(ServiceProduct(tenant_id=tenant_id, service_id=srv4.id, product_id=prod2.id))
        db.add(ServiceProduct(tenant_id=tenant_id, service_id=srv4.id, product_id=prod3.id))

        # 11b. Packages (Numbered)
        pkg1 = ServicePackage(
            tenant_id=tenant_id,
            name="Package 1 - Care Bundle (Service 1 + 2)",
            description="Initial 60m Standard Consultation plus 30m Follow-up package.",
            price=Decimal("165.00"),
            active=True,
            is_visible=True
        )
        pkg2 = ServicePackage(
            tenant_id=tenant_id,
            name="Package 2 - Wellness Bundle (Service 3 + 4)",
            description="Premium 90m Assessment followed by 45m Holistic Wellness session.",
            price=Decimal("260.00"),
            active=True,
            is_visible=True
        )
        db.add_all([pkg1, pkg2])
        db.commit()
        db.refresh(pkg1)
        db.refresh(pkg2)

        db.add(PackageStep(package_id=pkg1.id, service_id=srv1.id, order=1, offset_days=0, price=Decimal("110.00"), active=True))
        db.add(PackageStep(package_id=pkg1.id, service_id=srv2.id, order=2, offset_days=7, price=Decimal("55.00"), active=True))
        db.add(PackageStep(package_id=pkg2.id, service_id=srv3.id, order=1, offset_days=0, price=Decimal("175.00"), active=True))
        db.add(PackageStep(package_id=pkg2.id, service_id=srv4.id, order=2, offset_days=14, price=Decimal("85.00"), active=True))

        # 11c. Resources (Numbered)
        res1 = Resource(tenant_id=tenant_id, name="Resource 1 - Consultation Suite 101", type="Room", location_id=loc1.id, capacity=1, active=True)
        res2 = Resource(tenant_id=tenant_id, name="Resource 2 - Diagnostic Suite 102", type="Room", location_id=loc1.id, capacity=1, active=True)
        res3 = Resource(tenant_id=tenant_id, name="Resource 3 - Therapy Station 201", type="Chair", location_id=loc2.id, capacity=1, active=True)
        db.add_all([res1, res2, res3])
        db.commit()
        db.refresh(res1)
        db.refresh(res2)
        db.refresh(res3)

        db.add(ServiceResourceRequirement(service_id=srv1.id, resource_type="Room", quantity=1))
        db.add(ServiceResourceRequirement(service_id=srv3.id, resource_type="Room", quantity=1))
        db.add(ServiceResourceRequirement(service_id=srv4.id, resource_type="Chair", quantity=1))

        # 11d. Additional Custom Fields (Numbered)
        db.add(AdditionalField(tenant_id=tenant_id, scope="client", name="Field 1 - Intake Notes", label="Intake Notes", field_type="textarea", required=False, active=True, position=1, placeholder="Enter any medical history or intake notes..."))
        db.add(AdditionalField(tenant_id=tenant_id, scope="booking", name="Field 2 - Special Accommodations", label="Special Accommodations", field_type="textarea", required=False, active=True, position=2, placeholder="Wheelchair access, quiet room, etc."))

        # 11e. Tax Rates & Payment Processors (Numbered)
        tax1 = TaxRate(tenant_id=tenant_id, name="Tax Rate 1 - Standard GST (10%)", rate_percent=Decimal("10.00"), active=True)
        tax2 = TaxRate(tenant_id=tenant_id, name="Tax Rate 2 - Reduced Rate (5%)", rate_percent=Decimal("5.00"), active=True)
        db.add_all([tax1, tax2])

        db.add(PaymentProcessorConfig(
            tenant_id=tenant_id,
            provider="stripe",
            enabled=True,
            display_name="Processor 1 - Stripe Demo",
            public_key="pk_test_stripe_simply_demo_123",
            config_json='{"currency": "AUD"}'
        ))

        # 11f. Notification Templates & Reminders (Numbered)
        tpl1 = NotificationTemplate(tenant_id=tenant_id, code="booking_confirm_1", name="Template 1 - Booking Confirmation", channel="email", subject="Appointment Confirmed!", body="Hi {{client_name}},\n\nYour appointment for {{service_name}} on {{booking_time}} is confirmed.", locale="en", active=True)
        tpl2 = NotificationTemplate(tenant_id=tenant_id, code="booking_remind_2", name="Template 2 - 24hr Reminder", channel="email", subject="Appointment Reminder Tomorrow", body="Hi {{client_name}},\n\nThis is a reminder that your appointment for {{service_name}} is tomorrow at {{booking_time}}.", locale="en", active=True)
        db.add_all([tpl1, tpl2])
        db.commit()
        db.refresh(tpl1)
        db.refresh(tpl2)

        db.add(ReminderRule(tenant_id=tenant_id, name="Reminder Rule 1 - 24hr Alert", event_type="booking.start", channel="email", audience="client", timing="before", offset_minutes=1440, template_id=tpl2.id, active=True))

        # 11g. Webhook Registrations
        db.add(WebhookRegistration(tenant_id=tenant_id, event="booking.created", target_url="https://example.com/webhooks/booking-created", secret="whsec_booking_secret_123", is_active=True))

        # 12. Location Join Mappings
        for p in [prov1, prov2]:
            db.add(LocationProvider(tenant_id=tenant_id, location_id=loc1.id, provider_id=p.id))
        for s in [srv1, srv2, srv3, srv4, srv5]:
            db.add(LocationService(tenant_id=tenant_id, location_id=loc1.id, service_id=s.id))
        for c in [cat1, cat2]:
            db.add(LocationCategory(tenant_id=tenant_id, location_id=loc1.id, category_id=c.id))
        for prod in [prod1, prod2, prod3]:
            db.add(LocationProduct(tenant_id=tenant_id, location_id=loc1.id, product_id=prod.id))

        # 13. Clients (Numbered 1 to 5)
        client1 = Client(
            tenant_id=tenant_id,
            name="Client 1 - Alice Walker",
            phone="0411000001",
            email="client1@example.com",
            city="Sydney",
            state="NSW",
            active=True
        )
        client2 = Client(
            tenant_id=tenant_id,
            name="Client 2 - Bob Taylor",
            phone="0411000002",
            email="client2@example.com",
            city="Sydney",
            state="NSW",
            active=True
        )
        client3 = Client(
            tenant_id=tenant_id,
            name="Client 3 - Charlie Evans",
            phone="0411000003",
            email="client3@example.com",
            city="Sydney",
            state="NSW",
            active=True
        )
        client4 = Client(
            tenant_id=tenant_id,
            name="Client 4 - Diana Prince",
            phone="0411000004",
            email="client4@example.com",
            city="Sydney",
            state="NSW",
            active=True
        )
        client5 = Client(
            tenant_id=tenant_id,
            name="Client 5 - Evan Wright",
            phone="0411000005",
            email="client5@example.com",
            city="Sydney",
            state="NSW",
            active=True
        )
        db.add_all([client1, client2, client3, client4, client5])
        db.commit()
        for cl in [client1, client2, client3, client4, client5]:
            db.refresh(cl)
        logger.info("Seeded Clients 1..5")

        # 14. Bookings (Numbered, spread across today and upcoming days)
        now = datetime.now(timezone.utc)
        today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
        today_2pm = now.replace(hour=14, minute=0, second=0, microsecond=0)
        tomorrow_11am = (now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
        in_2days_9am = (now + timedelta(days=2)).replace(hour=9, minute=30, second=0, microsecond=0)
        in_3days_1pm = (now + timedelta(days=3)).replace(hour=13, minute=0, second=0, microsecond=0)

        # Booking 1: Client 1, Provider 1, Service 1, Location 1 (Today 10:00 AM)
        bk1 = Booking(
            tenant_id=tenant_id,
            client_id=client1.id,
            provider_id=prov1.id,
            service_id=srv1.id,
            location_id=loc1.id,
            start_time=today_10am,
            end_time=today_10am + timedelta(minutes=60),
            status=BookingStatus.CONFIRMED,
            notes="Regular checkup with Provider 1."
        )
        # Booking 2: Client 2, Provider 1, Service 2, Location 1 (Tomorrow 11:00 AM)
        bk2 = Booking(
            tenant_id=tenant_id,
            client_id=client2.id,
            provider_id=prov1.id,
            service_id=srv2.id,
            location_id=loc1.id,
            start_time=tomorrow_11am,
            end_time=tomorrow_11am + timedelta(minutes=30),
            status=BookingStatus.CONFIRMED,
            notes="Follow-up consultation."
        )
        # Booking 3: Client 3, Provider 2, Service 4, Location 1 (Today 2:00 PM)
        bk3 = Booking(
            tenant_id=tenant_id,
            client_id=client3.id,
            provider_id=prov2.id,
            service_id=srv4.id,
            location_id=loc1.id,
            start_time=today_2pm,
            end_time=today_2pm + timedelta(minutes=45),
            status=BookingStatus.CONFIRMED,
            notes="Holistic wellness appointment."
        )
        # Booking 4: Client 4, Provider 2, Service 5, Location 1 (In 2 days 9:30 AM)
        bk4 = Booking(
            tenant_id=tenant_id,
            client_id=client4.id,
            provider_id=prov2.id,
            service_id=srv5.id,
            location_id=loc1.id,
            start_time=in_2days_9am,
            end_time=in_2days_9am + timedelta(minutes=15),
            status=BookingStatus.CONFIRMED,
            notes="Rapid triage check."
        )
        # Booking 5: Client 5, Provider 1, Service 3, Location 1 (In 3 days 1:00 PM)
        bk5 = Booking(
            tenant_id=tenant_id,
            client_id=client5.id,
            provider_id=prov1.id,
            service_id=srv3.id,
            location_id=loc1.id,
            start_time=in_3days_1pm,
            end_time=in_3days_1pm + timedelta(minutes=90),
            status=BookingStatus.CONFIRMED,
            notes="Premium Assessment."
        )
        db.add_all([bk1, bk2, bk3, bk4, bk5])
        db.commit()
        for b in [bk1, bk2, bk3, bk4, bk5]:
            db.refresh(b)
        logger.info("Seeded 5 active Bookings across Client 1..5")

        # 15. Initial SmsArrivalSession for Booking 1 (Client 1) - Arrived & Waiting in Lobby!
        arr_conv1 = SmsConversation(
            tenant_id=tenant_id,
            provider_id=prov1.id,
            sms_account_id=sms_acc1.id,
            customer_address=client1.phone,
            client_id=client1.id,
            state="auto-reply",
            unread_count=0,
            last_activity_at=now
        )
        db.add(arr_conv1)
        db.commit()
        db.refresh(arr_conv1)

        arrival1 = SmsArrivalSession(
            booking_id=bk1.id,
            conversation_id=arr_conv1.id,
            token="arr-token-client1-live",
            arrived_at=now - timedelta(minutes=6),
            acknowledged_at=None,
            created_at=now - timedelta(minutes=30)
        )
        db.add(arrival1)

        # Acknowledged arrival session for Booking 3 (Client 3)
        arr_conv3 = SmsConversation(
            tenant_id=tenant_id,
            provider_id=prov2.id,
            sms_account_id=sms_acc2.id,
            customer_address=client3.phone,
            client_id=client3.id,
            state="auto-reply",
            unread_count=0,
            last_activity_at=now
        )
        db.add(arr_conv3)
        db.commit()
        db.refresh(arr_conv3)

        arrival3 = SmsArrivalSession(
            booking_id=bk3.id,
            conversation_id=arr_conv3.id,
            token="arr-token-client3-done",
            arrived_at=now - timedelta(minutes=45),
            acknowledged_at=now - timedelta(minutes=42),
            created_at=now - timedelta(minutes=90)
        )
        db.add(arrival3)
        db.commit()

        # 16. Invoices and Payments for Bookings
        for i, b in enumerate([bk1, bk2, bk3, bk4, bk5], start=1):
            inv = Invoice(
                tenant_id=tenant_id,
                booking_id=b.id,
                client_id=b.client_id,
                currency="AUD",
                subtotal=Decimal(str(b.service.price)),
                discount_total=Decimal("0.00"),
                tax_total=Decimal(str(b.service.price)) * Decimal("0.10"),
                tip_total=Decimal("0.00"),
                total=Decimal(str(b.service.price)) * Decimal("1.10"),
                amount_paid=Decimal(str(b.service.price)) * Decimal("1.10"),
                status="paid",
                notes=f"Auto-generated invoice for Booking {i}."
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)

            db.add(InvoiceLine(
                tenant_id=tenant_id,
                invoice_id=inv.id,
                line_type="service",
                item_id=b.service_id,
                description=b.service.name,
                quantity=1,
                unit_price=Decimal(str(b.service.price)),
                amount=Decimal(str(b.service.price))
            ))
            db.add(Payment(
                tenant_id=tenant_id,
                booking_id=b.id,
                amount=inv.total,
                currency="AUD",
                status="succeeded"
            ))

        # 17. Knowledge Base Entries & Quick Tools
        kb1 = SmsKnowledgeEntry(
            tenant_id=tenant_id,
            provider_id=prov1.id,
            sms_account_id=sms_acc1.id,
            category="service",
            text="Service 1 is a 60-minute Standard Consultation ($120). Service 2 is a 30-minute Express Follow-up ($65). Service 3 is a 90-minute Premium Assessment ($195).",
            status="approved",
            provenance="manual"
        )
        kb2 = SmsKnowledgeEntry(
            tenant_id=tenant_id,
            provider_id=prov2.id,
            sms_account_id=sms_acc2.id,
            category="service",
            text="Service 4 is Holistic Wellness 45m ($95) and Service 5 is Rapid Triage 15m ($40) provided by Marcus Vance.",
            status="approved",
            provenance="manual"
        )
        kb3 = SmsKnowledgeEntry(
            tenant_id=tenant_id,
            category="location",
            text="Location 1 - Main Center is at 100 Main Street, Suite 100. Customer parking is free at the rear of the building.",
            status="approved",
            provenance="manual"
        )
        kb4 = SmsKnowledgeEntry(
            tenant_id=tenant_id,
            category="policy",
            text="Cancellations and rescheduling are free when requested at least 24 hours prior to the appointment.",
            status="approved",
            provenance="manual"
        )
        db.add_all([kb1, kb2, kb3, kb4])

        for slot, label, content in [
            (0, "ADDR", "Our address is 100 Main Street, Suite 100, Sydney NSW 2000 at Location 1 - Main Center."),
            (1, "HOURS", "We are open Monday to Friday from 9:00 AM to 5:00 PM, with Saturday morning sessions from 9 AM to 1 PM."),
            (2, "PARKING", "Free dedicated customer parking is available at the rear of Location 1 - Main Center."),
            (3, "FEES", "Service 1 (60m): $120 | Service 2 (30m): $65 | Service 3 (90m): $195 | Service 4 (45m): $95 | Service 5 (15m): $40."),
            (4, "POLICY", "Rescheduling or cancellation requires 24 hours notice to avoid late fees."),
        ]:
            db.add(SmsQuickTool(
                tenant_id=tenant_id,
                slot_index=slot,
                label=label,
                content=content
            ))

        # 18. Sample Client Dispute for Client 1
        disp1 = ClientDispute(
            tenant_id=tenant_id,
            client_id=client1.id,
            booking_id=bk1.id,
            status="submitted",
            reason="quality_concern",
            description="The treatment room was chilly and the session started slightly late. Requesting a complimentary follow-up check.",
            preferred_resolution="redo_service",
            resolution_notes=None,
            photos=["https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=400&q=80"],
            created_at=now - timedelta(hours=2),
        )
        db.add(disp1)

        db.commit()
        logger.info("Successfully completed clean numbered mock data seeding for SimplyDemo (including ClientDispute)!")


        return {
            "success": True,
            "tenant_id": tenant_id,
            "providers": [prov1.name, prov2.name],
            "locations": [loc1.name, loc2.name],
            "services": [srv1.name, srv2.name, srv3.name, srv4.name, srv5.name],
            "clients": [client1.name, client2.name, client3.name, client4.name, client5.name],
            "products": [prod1.name, prod2.name, prod3.name],
            "addons": [addon1.name, addon2.name, addon3.name],
            "packages": [pkg1.name, pkg2.name],
            "resources": [res1.name, res2.name, res3.name],
            "bookings_count": 5,
            "sms_accounts": [sms_acc1.display_name, sms_acc2.display_name]
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        raise e
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    result = seed_numbered_mock_data()
    print("\n--- SEEDING COMPLETED SUCCESSFULLY ---")
    for key, val in result.items():
        print(f"  {key}: {val}")
