"""Tests for the demo structured catalog and public bootstrap endpoint."""

import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.service import Service
from app.models.provider import Provider
from app.models.location import Location
from app.models.resource import Resource
from app.models.category import Category
from app.models.booking import Booking
from app.models.booking_slot_allocation import BookingSlotAllocation
from app.models.addon import AddOn
from app.models.product import Product
from app.models.package import ServicePackage
from app.core.state_machine import BookingStatus


class TestDemoStructuredCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.tenant = cls.db.query(Tenant).filter(Tenant.subdomain == "simplydemo").first()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_tenant_configuration(self):
        self.assertIsNotNone(self.tenant)
        self.assertEqual(self.tenant.subdomain, "simplydemo")
        self.assertEqual(self.tenant.subscription_tier, "unlimited")
        self.assertTrue(self.tenant.allow_in_call)
        self.assertTrue(self.tenant.allow_out_call)

    def test_public_bootstrap_endpoint(self):
        response = self.client.get("/api/public/bootstrap", headers={"X-Tenant": "simplydemo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        payload = data.get("data", {})
        self.assertEqual(payload.get("company"), "simplydemo")
        self.assertEqual(payload.get("timezone"), "Australia/Melbourne")
        self.assertGreaterEqual(len(payload.get("services", [])), 5)
        self.assertGreaterEqual(len(payload.get("providers", [])), 5)
        self.assertEqual(len(payload.get("locations", [])), 2)

    def test_structured_catalog_counts(self):
        tid = self.tenant.id
        loc_count = self.db.query(Location).filter(Location.tenant_id == tid).count()
        res_count = self.db.query(Resource).filter(Resource.tenant_id == tid).count()
        cat_count = self.db.query(Category).filter(Category.tenant_id == tid).count()
        svc_count = self.db.query(Service).filter(Service.tenant_id == tid).count()
        prov_count = self.db.query(Provider).filter(Provider.tenant_id == tid).count()
        addon_count = self.db.query(AddOn).filter(AddOn.tenant_id == tid).count()
        prod_count = self.db.query(Product).filter(Product.tenant_id == tid).count()
        pkg_count = self.db.query(ServicePackage).filter(ServicePackage.tenant_id == tid).count()

        self.assertEqual(loc_count, 2)
        self.assertEqual(res_count, 4)
        self.assertEqual(cat_count, 2)
        self.assertEqual(svc_count, 5)
        self.assertGreaterEqual(prov_count, 5)
        self.assertEqual(addon_count, 5)
        self.assertEqual(prod_count, 5)
        self.assertEqual(pkg_count, 2)

    def test_lifecycle_bookings(self):
        tid = self.tenant.id
        total_bookings = self.db.query(Booking).filter(Booking.tenant_id == tid).count()
        self.assertEqual(total_bookings, 26)

        completed = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.COMPLETED).count()
        in_progress = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.IN_PROGRESS).count()
        confirmed = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.CONFIRMED).count()
        pending = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.PENDING).count()
        cancelled = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.CANCELLED).count()
        no_show = self.db.query(Booking).filter(Booking.tenant_id == tid, Booking.status == BookingStatus.NO_SHOW).count()

        self.assertEqual(completed, 12)
        self.assertEqual(in_progress, 1)
        self.assertEqual(confirmed, 6)
        self.assertEqual(pending, 3)
        self.assertEqual(cancelled, 2)
        self.assertEqual(no_show, 2)

        # Slot allocations present for active, confirmed, completed
        slots_count = self.db.query(BookingSlotAllocation).filter(BookingSlotAllocation.tenant_id == tid).count()
        self.assertGreater(slots_count, 100)


if __name__ == "__main__":
    unittest.main()
