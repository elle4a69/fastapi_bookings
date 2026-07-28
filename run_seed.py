import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.location import Location
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
from app.core.security import get_password_hash
from app.core.state_machine import BookingStatus

def run():
    db = SessionLocal()
    try:
        print("Truncating existing records to ensure fresh seed...")
        # Clear in reverse order of foreign key dependencies
        db.query(ManagementReviewRequest).delete()
        db.query(AuditLog).delete()
        db.query(Payment).delete()
        db.query(InvoiceLine).delete()
        db.query(Invoice).delete()
        db.query(PaymentProcessorConfig).delete()
        db.query(TaxRate).delete()
        db.query(ReminderRule).delete()
        db.query(NotificationTemplate).delete()
        db.query(WebhookRegistration).delete()
        db.query(AdditionalField).delete()
        db.query(ServiceResourceRequirement).delete()
        db.query(Resource).delete()
        db.query(PackageStep).delete()
        db.query(ServicePackage).delete()
        db.query(ServiceProduct).delete()
        db.query(Product).delete()
        db.query(ServiceAddOn).delete()
        db.query(AddOn).delete()
        db.query(ServiceCategory).delete()
        db.query(Category).delete()
        db.query(Booking).delete()
        db.query(ProviderWorkDay).delete()
        db.query(ServiceProvider).delete()
        db.query(Client).delete()
        db.query(Location).delete()
        db.query(Service).delete()
        db.query(Provider).delete()
        db.query(User).delete()
        db.query(Tenant).delete()
        db.commit()

        print("Seeding fresh demo environment...")

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
        db.commit()
        db.refresh(admin_user)

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
            sp = ServiceProvider(tenant_id=tenant.id, service_id=services[i].id, provider_id=providers[i].id)
            db.add(sp)
            if i > 0:
                sp_all = ServiceProvider(tenant_id=tenant.id, service_id=services[0].id, provider_id=providers[i].id)
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
        bookings = []
        base_start = datetime.now(timezone.utc) + timedelta(days=1)
        base_start = base_start.replace(hour=10, minute=0, second=0, microsecond=0)
        for i in range(6):
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
            bookings.append(booking)
        db.commit()

        for b in bookings:
            db.refresh(b)

        # 10. Seed Categories
        print("Seeding Catalog Categories...")
        cat1 = Category(tenant_id=tenant.id, name="Massage & Bodywork", description="Therapeutic massages and body therapies.", active=True)
        cat2 = Category(tenant_id=tenant.id, name="Facials & Skin Care", description="Rejuvenating facials and skincare routines.", active=True)
        cat3 = Category(tenant_id=tenant.id, name="Hair & Styling", description="Professional haircuts, colors and blowouts.", active=True)
        db.add_all([cat1, cat2, cat3])
        db.commit()
        db.refresh(cat1)
        db.refresh(cat2)
        db.refresh(cat3)

        # Map services to categories
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[0].id, category_id=cat1.id))
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[1].id, category_id=cat1.id))
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[2].id, category_id=cat2.id))
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[3].id, category_id=cat2.id))
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[4].id, category_id=cat3.id))
        db.add(ServiceCategory(tenant_id=tenant.id, service_id=services[5].id, category_id=cat3.id))

        # 11. Seed AddOns
        print("Seeding Service Add-ons...")
        addon1 = AddOn(tenant_id=tenant.id, name="Aromatherapy Essential Oil", description="Premium essential oils added to treatment.", price=Decimal("15.00"), duration=0, active=True)
        addon2 = AddOn(tenant_id=tenant.id, name="Deep Hydration Scalp Mask", description="Soothing scalp masks during session.", price=Decimal("25.00"), duration=15, active=True)
        addon3 = AddOn(tenant_id=tenant.id, name="Extra Massage Time (15 min)", description="Extend massage duration.", price=Decimal("30.00"), duration=15, active=True)
        db.add_all([addon1, addon2, addon3])
        db.commit()
        db.refresh(addon1)
        db.refresh(addon2)
        db.refresh(addon3)

        # Map add-ons to services
        db.add(ServiceAddOn(tenant_id=tenant.id, service_id=services[0].id, add_on_id=addon1.id))
        db.add(ServiceAddOn(tenant_id=tenant.id, service_id=services[0].id, add_on_id=addon3.id))
        db.add(ServiceAddOn(tenant_id=tenant.id, service_id=services[1].id, add_on_id=addon1.id))
        db.add(ServiceAddOn(tenant_id=tenant.id, service_id=services[4].id, add_on_id=addon2.id))

        # 12. Seed Products
        print("Seeding Inventory Products...")
        prod1 = Product(tenant_id=tenant.id, name="Organic Soothing Massage Oil", description="Lavender-infused organic carrier massage oil.", price=Decimal("25.00"), sku="PROD-OIL-001", active=True)
        prod2 = Product(tenant_id=tenant.id, name="Hydrating Herbal Facial Cream", description="Rejuvenates dry and sensitive facial skin.", price=Decimal("45.00"), sku="PROD-CREAM-002", active=True)
        prod3 = Product(tenant_id=tenant.id, name="Tea Tree Shampoo & Conditioner Set", description="Purifying scalp wash set.", price=Decimal("35.00"), sku="PROD-SHAMP-003", active=True)
        db.add_all([prod1, prod2, prod3])
        db.commit()
        db.refresh(prod1)
        db.refresh(prod2)
        db.refresh(prod3)

        # Map products to recommended services
        db.add(ServiceProduct(tenant_id=tenant.id, service_id=services[0].id, product_id=prod1.id))
        db.add(ServiceProduct(tenant_id=tenant.id, service_id=services[2].id, product_id=prod2.id))
        db.add(ServiceProduct(tenant_id=tenant.id, service_id=services[4].id, product_id=prod3.id))

        # 13. Seed ServicePackages
        print("Seeding Service Packages...")
        package1 = ServicePackage(tenant_id=tenant.id, name="Ultimate Wellness Bundle", description="Complete rejuvenation experience: Massage + Facial + Hair Trim.", price=Decimal("220.00"), active=True)
        db.add(package1)
        db.commit()
        db.refresh(package1)

        db.add(PackageStep(package_id=package1.id, service_id=services[0].id, order=1, offset_days=0, price=Decimal("80.00"), active=True))
        db.add(PackageStep(package_id=package1.id, service_id=services[2].id, order=2, offset_days=7, price=Decimal("80.00"), active=True))
        db.add(PackageStep(package_id=package1.id, service_id=services[4].id, order=3, offset_days=14, price=Decimal("60.00"), active=True))

        # 14. Seed Resources
        print("Seeding Room Resources...")
        res1 = Resource(tenant_id=tenant.id, name="Massage Therapy Room A", type="Room", location_id=locations[0].id, capacity=1, active=True)
        res2 = Resource(tenant_id=tenant.id, name="Esthetician Studio B", type="Room", location_id=locations[0].id, capacity=1, active=True)
        res3 = Resource(tenant_id=tenant.id, name="Styling Station 1", type="Chair", location_id=locations[0].id, capacity=1, active=True)
        db.add_all([res1, res2, res3])
        db.commit()
        db.refresh(res1)
        db.refresh(res2)
        db.refresh(res3)

        # Map requirements
        db.add(ServiceResourceRequirement(service_id=services[0].id, resource_type="Room", quantity=1))
        db.add(ServiceResourceRequirement(service_id=services[2].id, resource_type="Room", quantity=1))
        db.add(ServiceResourceRequirement(service_id=services[4].id, resource_type="Chair", quantity=1))

        # 15. Seed Additional Intake Fields
        print("Seeding Intake Custom Fields...")
        db.add(AdditionalField(tenant_id=tenant.id, scope="client", name="Emergency Contact", label="Emergency Contact Name", field_type="text", required=True, active=True, position=1, placeholder="e.g. John Doe"))
        db.add(AdditionalField(tenant_id=tenant.id, scope="client", name="Allergies", label="Allergies & Medical Conditions", field_type="textarea", required=False, active=True, position=2, placeholder="None or list allergies..."))
        db.add(AdditionalField(tenant_id=tenant.id, scope="booking", name="Special Requests", label="Special Requests or Accommodations", field_type="textarea", required=False, active=True, position=3, placeholder="Any special notes for provider..."))

        # 16. Seed Webhooks
        print("Seeding Webhook Integrations...")
        db.add(WebhookRegistration(tenant_id=tenant.id, event="booking.created", target_url="https://example.com/webhooks/booking-created", secret="whsec_booking_secret_123", is_active=True))
        db.add(WebhookRegistration(tenant_id=tenant.id, event="payment.succeeded", target_url="https://example.com/webhooks/payment-completed", secret="whsec_payment_secret_456", is_active=True))

        # 17. Seed Notification Templates
        print("Seeding Notification Templates...")
        temp1 = NotificationTemplate(tenant_id=tenant.id, code="booking_confirm", name="Booking Confirmation Email", channel="email", subject="Appointment Confirmed!", body="Hi {{client_name}},\n\nYour appointment for {{service_name}} on {{booking_time}} is confirmed.", locale="en", active=True)
        temp2 = NotificationTemplate(tenant_id=tenant.id, code="booking_remind", name="Appointment 24hr Reminder", channel="email", subject="Appointment Reminder Tomorrow", body="Hi {{client_name}},\n\nThis is a friendly reminder that you have an appointment tomorrow for {{service_name}} at {{booking_time}}.", locale="en", active=True)
        db.add_all([temp1, temp2])
        db.commit()
        db.refresh(temp1)
        db.refresh(temp2)

        # Seed Reminder Rules
        db.add(ReminderRule(tenant_id=tenant.id, name="24-Hour Email Confirmation Alert", event_type="booking.start", channel="email", audience="client", timing="before", offset_minutes=1440, template_id=temp2.id, active=True))

        # 18. Seed TaxRates & Processor Configs
        print("Seeding Tax Rates & Processor Configs...")
        tax1 = TaxRate(tenant_id=tenant.id, name="Standard GST", rate_percent=Decimal("10.00"), active=True)
        tax2 = TaxRate(tenant_id=tenant.id, name="State VAT", rate_percent=Decimal("15.00"), active=True)
        db.add_all([tax1, tax2])

        db.add(PaymentProcessorConfig(tenant_id=tenant.id, provider="stripe", enabled=True, display_name="Stripe Credit Card Gateway", public_key="pk_test_stripe_simply_demo_123", config_json='{"currency": "USD"}'))
        db.add(PaymentProcessorConfig(tenant_id=tenant.id, provider="paypal", enabled=False, display_name="PayPal Payments Standard", public_key="paypal_client_id_placeholder", config_json='{"currency": "USD"}'))

        # 19. Seed Invoices & InvoicesLines for bookings
        print("Seeding Invoices & Payments...")
        for i in range(6):
            inv = Invoice(
                tenant_id=tenant.id,
                booking_id=bookings[i].id,
                client_id=clients[i].id,
                currency="USD",
                subtotal=Decimal(str(services[i].price)),
                discount_total=Decimal("0.00"),
                tax_total=Decimal(str(services[i].price)) * Decimal("0.10"),
                tip_total=Decimal("0.00"),
                total=Decimal(str(services[i].price)) * Decimal("1.10"),
                amount_paid=Decimal(str(services[i].price)) * Decimal("1.10"),
                status="paid",
                notes=f"Auto-generated invoice for booking {i+1}."
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)

            db.add(InvoiceLine(tenant_id=tenant.id, invoice_id=inv.id, line_type="service", item_id=services[i].id, description=services[i].name, quantity=1, unit_price=Decimal(str(services[i].price)), amount=Decimal(str(services[i].price))))
            db.add(InvoiceLine(tenant_id=tenant.id, invoice_id=inv.id, line_type="tax", description="Standard 10% tax", quantity=1, unit_price=Decimal(str(services[i].price)) * Decimal("0.10"), amount=Decimal(str(services[i].price)) * Decimal("0.10")))

            # Seed Payment logs
            db.add(Payment(tenant_id=tenant.id, booking_id=bookings[i].id, amount=inv.total, currency="USD", status="succeeded"))

        # 20. Seed Audit Logs
        print("Seeding Audit Trail Logs...")
        db.add(AuditLog(tenant_id=tenant.id, user_id=admin_user.id, action="CREATE", target_type="Tenant", target_id=tenant.id, details="Tenant 'SimplyDemo' created during system startup.", timestamp=datetime.utcnow() - timedelta(days=2)))
        db.add(AuditLog(tenant_id=tenant.id, user_id=admin_user.id, action="SEED", target_type="Database", details="Seeded full multi-tenant configuration and demo logs.", timestamp=datetime.utcnow() - timedelta(days=1)))
        db.add(AuditLog(tenant_id=tenant.id, user_id=admin_user.id, action="UPDATE", target_type="User", target_id=admin_user.id, details="Owner user password hashed and updated.", timestamp=datetime.utcnow()))

        # 21. Seed Manual Registration Review Requests
        print("Seeding Client Moderation Reviews...")
        db.add(ManagementReviewRequest(tenant_id=tenant.id, client_id=clients[0].id, service_id=services[0].id, provider_id=providers[0].id, location_id=locations[0].id, preferred_time=datetime.now() + timedelta(days=3), reason="Restricted client requested premium service override.", state="pending", slot_reserved=False, payment_taken=False))
        db.add(ManagementReviewRequest(tenant_id=tenant.id, client_id=clients[1].id, service_id=services[1].id, provider_id=providers[1].id, location_id=locations[1].id, preferred_time=datetime.now() + timedelta(days=4), reason="Client security flag override requested.", state="approved", slot_reserved=True, payment_taken=True, resolution_notes="Verified client ID badge. Approved override.", resolved_by_id=admin_user.id, resolved_at=datetime.utcnow()))

        db.commit()
        print("Database fully seeded with all 22 required entity tables successfully!")

    except Exception as e:
        print(f"Error during seeding: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run()
