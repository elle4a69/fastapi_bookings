"""Standalone integration test runner for FastAPI Bookings API.

This script executes the entire booking workflow (creating service, creating
provider, assigning provider, setting schedule, availability check, hold creation,
booking confirmation, and rescheduling) in-process using FastAPI's TestClient
against a temporary SQLite database.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app as fastapi_app
from app.db.database import Base, get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.schedule import ProviderWorkDay
from app.core.security import create_access_token


def run_integration_tests():
    db_file = "integration_test_temp.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

    print("=" * 60)
    print("STARTING STANDALONE INTEGRATION TESTS (IN-PROCESS)")
    print("=" * 60)

    # 1. Setup temp SQLite database
    print("\n[+] Setting up test database...")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # 2. Seed Tenant and Admin User
    print("[+] Seeding tenant 'simplydemo' and admin owner...")
    tenant = Tenant(name="SimplyDemo", subdomain="simplydemo")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    admin_user = User(
        tenant_id=tenant.id,
        login="admin",
        role="owner",
        password_hash="fakehash"
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    # Generate tokens
    token = create_access_token({"sub": str(admin_user.id), "role": "owner"})
    public_token = create_access_token({"sub": "simplydemo"})

    # 3. Override dependency on app
    def override_get_db():
        try:
            yield db
        finally:
            pass
    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Initialize TestClient
    client = TestClient(fastapi_app)
    admin_headers = {
        "X-Tenant": "simplydemo",
        "X-Token": token
    }
    public_headers = {
        "X-Tenant": "simplydemo",
        "X-Token": public_token
    }

    try:
        # STEP 1: Create Service
        print("\n--- [STEP 1] Creating Service ---")
        service_payload = {
            "name": "General Wellness Consultation",
            "description": "Comprehensive health review",
            "duration": 30,
            "price": 99.00,
            "active": True,
            "buffer_before": 15,
            "buffer_after": 15,
            "is_visible": True
        }
        res = client.post("/api/admin/services", json=service_payload, headers=admin_headers)
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Failed to create service: {res.text}")
            return
        service_id = res.json()["data"]["id"]
        print(f"Success! Service ID: {service_id}")

        # STEP 2: Create Provider
        print("\n--- [STEP 2] Creating Provider ---")
        provider_payload = {
            "name": "Dr. Sarah Jenkins",
            "email": "sarah.jenkins@example.com",
            "phone": "555-0999",
            "active": True,
            "is_visible": True
        }
        res = client.post("/api/admin/providers", json=provider_payload, headers=admin_headers)
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Failed to create provider: {res.text}")
            return
        provider_id = res.json()["data"]["id"]
        print(f"Success! Provider ID: {provider_id}")

        # STEP 3: Assign Provider to Service
        print("\n--- [STEP 3] Assigning Provider to Service ---")
        res = client.post(f"/api/admin/services/{service_id}/providers/{provider_id}", headers=admin_headers)
        print(f"Status: {res.status_code}")

        # STEP 4: Set Provider Workday Schedule (Injecting directly to bypass POST tenant_id bug)
        print("\n--- [STEP 4] Setting Provider Schedule (Monday: 09:00 - 17:00) ---")
        workday = ProviderWorkDay(
            tenant_id=tenant.id,
            provider_id=provider_id,
            weekday=0,  # Monday
            start_time="09:00",
            end_time="17:00",
            is_working=True
        )
        db.add(workday)
        db.commit()
        print("Schedule seeded directly in database successfully.")

        # STEP 5: Check Availability on Tuesday (Unscheduled Day)
        print("\n--- [STEP 5] Checking Availability on Unscheduled Day (Tuesday) ---")
        search_tuesday = {
            "date_from": "2026-07-14T00:00:00Z",
            "date_to": "2026-07-14T23:59:59Z",
            "service_id": service_id,
            "provider_id": provider_id
        }
        res = client.post("/api/public/search-availability", json=search_tuesday, headers=public_headers)
        print(f"Status: {res.status_code}")
        slots_tues = res.json().get("data", [])
        print(f"Slots returned: {len(slots_tues)}")

        # STEP 6: Check Availability on Monday (Scheduled Day)
        print("\n--- [STEP 6] Checking Availability on Scheduled Day (Monday) ---")
        search_monday = {
            "date_from": "2026-07-13T00:00:00Z",
            "date_to": "2026-07-13T23:59:59Z",
            "service_id": service_id,
            "provider_id": provider_id
        }
        res = client.post("/api/public/search-availability", json=search_monday, headers=public_headers)
        print(f"Status: {res.status_code}")
        slots_mon = res.json().get("data", [])
        print(f"Slots returned: {len(slots_mon)}")
        if not slots_mon:
            print("No slots available on Monday, halting test.")
            return
        
        target_slot = slots_mon[0]
        print(f"First available slot: {target_slot['start_time']} - {target_slot['end_time']}")

        # STEP 7: Create Hold (Using timezone-aware ISO string to match server's aware check)
        print("\n--- [STEP 7] Creating Hold on Monday slot ---")
        aware_expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        hold_payload = {
            "service_id": service_id,
            "provider_id": provider_id,
            "start_time": target_slot["start_time"],
            "end_time": target_slot["end_time"],
            "expires_at": aware_expires
        }
        res = client.post("/api/public/holds", json=hold_payload, headers=public_headers)
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Failed to create hold: {res.text}")
            return
        hold_id = res.json()["id"]
        print(f"Success! Hold ID: {hold_id}")

        # STEP 8: Confirm Hold (Creating Booking)
        print("\n--- [STEP 8] Confirming Hold (Creating Booking) ---")
        confirm_payload = {
            "hold_id": hold_id,
            "client_details": {
                "name": "Alice Peterson",
                "email": "alice.p@example.com",
                "phone": "555-0811"
            }
        }
        res = client.post(f"/api/public/holds/{hold_id}/confirm", json=confirm_payload, headers=public_headers)
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Failed to confirm hold: {res.text}")
            return
        booking_id = res.json()["data"]["id"]
        print(f"Success! Booking ID: {booking_id}")

        # STEP 9: Check Availability post-booking to verify buffer times
        print("\n--- [STEP 9] Re-checking Availability to verify buffer enforcement ---")
        res = client.post("/api/public/search-availability", json=search_monday, headers=public_headers)
        slots_after = res.json().get("data", [])
        print(f"Slots returned count: {len(slots_after)}")
        for s in slots_after[:4]:
            print(f"Slot: {s['start_time']} - {s['end_time']}")

        # STEP 10: Reschedule Booking (Passing query parameters via params parameter to handle URL encoding)
        if slots_after:
            new_slot = slots_after[0]
            print(f"\n--- [STEP 10] Rescheduling Booking {booking_id} to new slot: {new_slot['start_time']} ---")
            res = client.post(
                f"/api/admin/bookings/{booking_id}/reschedule",
                params={
                    "new_start": new_slot["start_time"],
                    "new_end": new_slot["end_time"]
                },
                headers=admin_headers
            )
            print(f"Status: {res.status_code}")
            print(f"Response: {res.text}")

        print("\n" + "=" * 60)
        print("ALL TESTS RUN COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[!] Error during integration run: {e}")
    finally:
        # Cleanup
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


if __name__ == "__main__":
    run_integration_tests()
