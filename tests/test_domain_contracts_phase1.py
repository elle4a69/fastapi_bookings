"""Comprehensive tests for Phase 1: Domain Contracts & Backward-Compatible Schema.

Tests:
1. Capability hierarchy validation (valid & invalid cases).
2. Service outcall_price defaulting and independent modification.
3. Out-call buffers persistence.
4. Travel-charge policy (ALWAYS_FROM_BASE vs ACTUAL_ORIGIN).
5. Location privacy field (is_client_hidden).
6. Booking service-mode & travel snapshot fields.
7. Verification that derived operational scheduling fields are not persisted in Booking.
8. Migration upgrade and downgrade execution test.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.capability_validator import (
    validate_child_not_broader,
    validate_provider_capability_against_tenant,
    validate_service_capability_against_provider,
    validate_service_capability_against_tenant,
    validate_capability_hierarchy,
    validate_booking_service_mode,
    CapabilityHierarchyError,
    ServiceModeValidationError,
)
from app.models.tenant import Tenant, TravelChargeOrigin
from app.models.provider import Provider
from app.models.service import Service
from app.models.location import Location
from app.models.booking import Booking, ServiceMode
from app.models.client import Client
from app.core.state_machine import BookingStatus
from app.schemas.tenant import TenantBase, TenantCreate, TenantUpdate
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.schemas.location import LocationBase, LocationCreate
from app.schemas.booking import BookingBase, BookingCreate


@pytest.fixture
def sample_tenant(db_session):
    """Create a sample tenant for tests."""
    tenant = Tenant(
        name="Test Tenant",
        subdomain="testtenant",
        allow_in_call=True,
        allow_out_call=True,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# 1. Capability Hierarchy Tests
# ---------------------------------------------------------------------------

def test_hierarchy_valid_both_enabled():
    """Child matching parent capabilities is valid."""
    tenant = {"allow_in_call": True, "allow_out_call": True}
    provider = {"allow_in_call": True, "allow_out_call": True}
    service = {"allow_in_call": True, "allow_out_call": True}

    # Should not raise
    validate_capability_hierarchy(tenant=tenant, provider=provider, service=service)


def test_hierarchy_valid_child_more_restrictive():
    """Child may be more restrictive than parent."""
    # Tenant allows both, Provider only allows in-call, Service only allows in-call
    tenant = {"allow_in_call": True, "allow_out_call": True}
    provider = {"allow_in_call": True, "allow_out_call": False}
    service = {"allow_in_call": True, "allow_out_call": False}
    validate_capability_hierarchy(tenant=tenant, provider=provider, service=service)

    # Provider allows both, Service only allows out-call
    provider2 = {"allow_in_call": True, "allow_out_call": True}
    service2 = {"allow_in_call": False, "allow_out_call": True}
    validate_capability_hierarchy(tenant=tenant, provider=provider2, service=service2)


def test_hierarchy_invalid_provider_broader_than_tenant_outcall():
    """Provider cannot enable out-call when tenant disables it."""
    tenant = {"allow_in_call": True, "allow_out_call": False}
    provider = {"allow_in_call": True, "allow_out_call": True}

    with pytest.raises(CapabilityHierarchyError, match="cannot enable out-call capability"):
        validate_provider_capability_against_tenant(tenant, provider)


def test_hierarchy_invalid_provider_broader_than_tenant_incall():
    """Provider cannot enable in-call when tenant disables it."""
    tenant = {"allow_in_call": False, "allow_out_call": True}
    provider = {"allow_in_call": True, "allow_out_call": True}

    with pytest.raises(CapabilityHierarchyError, match="cannot enable in-call capability"):
        validate_provider_capability_against_tenant(tenant, provider)


def test_hierarchy_invalid_service_broader_than_provider():
    """Service cannot enable out-call when provider disables it."""
    provider = {"allow_in_call": True, "allow_out_call": False}
    service = {"allow_in_call": True, "allow_out_call": True}

    with pytest.raises(CapabilityHierarchyError, match="cannot enable out-call capability"):
        validate_service_capability_against_provider(provider, service)


def test_hierarchy_invalid_service_broader_than_tenant():
    """Service cannot enable in-call when tenant disables it."""
    tenant = {"allow_in_call": False, "allow_out_call": True}
    service = {"allow_in_call": True, "allow_out_call": True}

    with pytest.raises(CapabilityHierarchyError, match="cannot enable in-call capability"):
        validate_service_capability_against_tenant(tenant, service)


# ---------------------------------------------------------------------------
# 2. Service Outcall Price Defaulting & Independent Modification
# ---------------------------------------------------------------------------

def test_service_outcall_price_defaulting_pydantic():
    """Pydantic schema defaults outcall_price to price if allow_out_call is True."""
    svc_in = ServiceCreate(
        name="Haircut",
        duration=30,
        price=Decimal("50.00"),
        allow_out_call=True,
    )
    assert svc_in.outcall_price == Decimal("50.00")


def test_service_outcall_price_explicit_preserved():
    """Explicit outcall_price is preserved and not overwritten by price."""
    svc_in = ServiceCreate(
        name="Mobile Massage",
        duration=60,
        price=Decimal("100.00"),
        outcall_price=Decimal("140.00"),
        allow_out_call=True,
    )
    assert svc_in.outcall_price == Decimal("140.00")
    assert svc_in.price == Decimal("100.00")


def test_service_outcall_price_orm_defaulting_and_modification(db_session, sample_tenant):
    """ORM model defaults outcall_price to price on insert and supports independent modification."""
    # 1. Defaulting on insert
    svc = Service(
        tenant_id=sample_tenant.id,
        name="Physiotherapy",
        duration=45,
        price=Decimal("120.00"),
        allow_in_call=True,
        allow_out_call=True,
        outcall_price=None,  # Not explicitly set
    )
    db_session.add(svc)
    db_session.commit()
    db_session.refresh(svc)

    assert svc.outcall_price == Decimal("120.00")
    assert svc.effective_outcall_price == Decimal("120.00")

    # 2. Independent modification
    svc.outcall_price = Decimal("165.00")
    db_session.commit()
    db_session.refresh(svc)

    assert svc.outcall_price == Decimal("165.00")
    assert svc.price == Decimal("120.00")
    assert svc.effective_outcall_price == Decimal("165.00")


# ---------------------------------------------------------------------------
# 3. Out-Call Buffers Persistence
# ---------------------------------------------------------------------------

def test_service_outcall_buffers_persistence(db_session, sample_tenant):
    """Service persists outcall_buffer_before and outcall_buffer_after."""
    svc = Service(
        tenant_id=sample_tenant.id,
        name="Home Inspection",
        duration=90,
        price=Decimal("200.00"),
        allow_in_call=False,
        allow_out_call=True,
        outcall_buffer_before=30,
        outcall_buffer_after=45,
    )
    db_session.add(svc)
    db_session.commit()
    db_session.refresh(svc)

    assert svc.outcall_buffer_before == 30
    assert svc.outcall_buffer_after == 45
    assert svc.buffer_before == 0  # in-call buffer remains distinct default
    assert svc.buffer_after == 0


# ---------------------------------------------------------------------------
# 4. Travel-Charge Policy
# ---------------------------------------------------------------------------

def test_tenant_travel_charge_policy_defaults_and_updates(db_session):
    """Tenant default travel_charge_origin is ALWAYS_FROM_BASE and can be updated to ACTUAL_ORIGIN."""
    tenant = Tenant(
        name="Mobile Services Corp",
        subdomain="mobilesvc",
        allow_in_call=True,
        allow_out_call=True,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.travel_charge_origin == TravelChargeOrigin.ALWAYS_FROM_BASE.value

    # Update to ACTUAL_ORIGIN
    tenant.travel_charge_origin = TravelChargeOrigin.ACTUAL_ORIGIN.value
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.travel_charge_origin == "ACTUAL_ORIGIN"


# ---------------------------------------------------------------------------
# 5. Location Privacy Field
# ---------------------------------------------------------------------------

def test_location_privacy_is_client_hidden(db_session, sample_tenant):
    """Location privacy field defaults to False and can be hidden."""
    loc = Location(
        tenant_id=sample_tenant.id,
        name="Private Studio Suite",
        address="Secret Street 42",
    )
    db_session.add(loc)
    db_session.commit()
    db_session.refresh(loc)

    assert loc.is_client_hidden is False

    loc.is_client_hidden = True
    db_session.commit()
    db_session.refresh(loc)

    assert loc.is_client_hidden is True


# ---------------------------------------------------------------------------
# 6. Booking Service Mode & Travel Snapshot Fields
# ---------------------------------------------------------------------------

def test_booking_service_mode_validation():
    """Validate booking service mode against service capability."""
    incall_only_svc = Service(name="Studio Only", duration=30, allow_in_call=True, allow_out_call=False)
    outcall_only_svc = Service(name="Mobile Only", duration=30, allow_in_call=False, allow_out_call=True)

    # Valid in-call
    validate_booking_service_mode("in_call", service=incall_only_svc)

    # Invalid out-call on in-call only service
    with pytest.raises(ServiceModeValidationError, match="does not permit out-call"):
        validate_booking_service_mode("out_call", service=incall_only_svc)

    # Valid out-call
    validate_booking_service_mode("out_call", service=outcall_only_svc)

    # Invalid in-call on out-call only service
    with pytest.raises(ServiceModeValidationError, match="does not permit in-call"):
        validate_booking_service_mode("in_call", service=outcall_only_svc)


def test_booking_persistence_with_travel_snapshot(db_session, sample_tenant):
    """Booking persists service_mode, client_suburb, postcode, address, and chargeable travel fields."""
    provider = Provider(tenant_id=sample_tenant.id, name="Travel Doc", allow_out_call=True)
    service = Service(tenant_id=sample_tenant.id, name="Home Visit", duration=60, price=Decimal("150.00"), allow_out_call=True)
    client = Client(tenant_id=sample_tenant.id, name="Alice Client", email="alice@test.com")
    db_session.add_all([provider, service, client])
    db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    booking = Booking(
        tenant_id=sample_tenant.id,
        client_id=client.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start,
        end_time=end,
        service_mode=ServiceMode.OUT_CALL.value,
        client_suburb="Surry Hills",
        client_postcode="2010",
        service_address="123 Crown St, Surry Hills NSW 2010",
        chargeable_travel_distance_km=14.5,
        chargeable_travel_fee=Decimal("25.00"),
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    assert booking.service_mode == "out_call"
    assert booking.client_suburb == "Surry Hills"
    assert booking.client_postcode == "2010"
    assert booking.service_address == "123 Crown St, Surry Hills NSW 2010"
    assert booking.chargeable_travel_distance_km == 14.5
    assert booking.chargeable_travel_fee == Decimal("25.00")


def test_booking_does_not_persist_derived_scheduling_windows():
    """Verify that derived operational scheduling windows are NOT columns in the Booking model."""
    derived_fields = [
        "operational_window_start",
        "operational_window_end",
        "operational_travel_inbound_minutes",
        "operational_travel_outbound_minutes",
    ]
    for field in derived_fields:
        assert not hasattr(Booking, field), f"Derived field {field} must NOT be persisted in Booking!"


# ---------------------------------------------------------------------------
# 7. Migration Upgrade and Downgrade Execution Test
# ---------------------------------------------------------------------------

def test_migration_upgrade_and_downgrade_execution(tmp_path):
    """Test the Alembic migration upgrade and downgrade against an isolated SQLite database."""
    db_file = tmp_path / "test_migration.db"
    engine = create_engine(f"sqlite:///{db_file}")

    # Create baseline tables with original schema (without new columns)
    ddl_statements = [
        """
        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            subdomain VARCHAR NOT NULL,
            created_at DATETIME
        )
        """,
        """
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            name VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE services (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            price NUMERIC(10, 2),
            allow_in_call BOOLEAN DEFAULT 1,
            allow_out_call BOOLEAN DEFAULT 1
        )
        """,
        """
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            name VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL
        )
        """,
    ]
    with engine.begin() as conn:
        for ddl in ddl_statements:
            conn.execute(text(ddl))
        # Insert a sample service with price to test backfill
        conn.execute(
            text(
                "INSERT INTO services (id, tenant_id, name, price, allow_in_call, allow_out_call) "
                "VALUES (1, 1, 'Pre-existing Service', 85.00, 1, 1)"
            )
        )

    # Load the migration module
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "c5e6f7a8b9c0_add_incall_outcall_and_service_mode_schema.py"
    )
    spec = importlib.util.spec_from_file_location("phase1_migration", migration_path)
    migration_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_mod)

    # Mock op context bound to our test engine connection
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op_obj = Operations(ctx)

        # Patch alembic.op
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(migration_mod, "op", op_obj)

            # 1. Run upgrade
            migration_mod.upgrade()

            # Inspect columns after upgrade
            insp = inspect(conn)
            tenant_cols = {c["name"] for c in insp.get_columns("tenants")}
            assert "allow_in_call" in tenant_cols
            assert "allow_out_call" in tenant_cols
            assert "travel_charge_origin" in tenant_cols

            provider_cols = {c["name"] for c in insp.get_columns("providers")}
            assert "allow_in_call" in provider_cols
            assert "allow_out_call" in provider_cols

            service_cols = {c["name"] for c in insp.get_columns("services")}
            assert "outcall_price" in service_cols
            assert "outcall_buffer_before" in service_cols
            assert "outcall_buffer_after" in service_cols

            location_cols = {c["name"] for c in insp.get_columns("locations")}
            assert "is_client_hidden" in location_cols

            booking_cols = {c["name"] for c in insp.get_columns("bookings")}
            assert "service_mode" in booking_cols
            assert "client_suburb" in booking_cols
            assert "client_postcode" in booking_cols
            assert "service_address" in booking_cols
            assert "chargeable_travel_distance_km" in booking_cols
            assert "chargeable_travel_fee" in booking_cols

            # Verify backfill on pre-existing service
            row = conn.execute(text("SELECT outcall_price FROM services WHERE id = 1")).fetchone()
            assert row[0] == 85.00

            # 2. Run downgrade
            migration_mod.downgrade()

            # Inspect columns after downgrade
            insp2 = inspect(conn)
            tenant_cols_downgraded = {c["name"] for c in insp2.get_columns("tenants")}
            assert "allow_in_call" not in tenant_cols_downgraded
            assert "travel_charge_origin" not in tenant_cols_downgraded

            service_cols_downgraded = {c["name"] for c in insp2.get_columns("services")}
            assert "outcall_price" not in service_cols_downgraded
            assert "outcall_buffer_before" not in service_cols_downgraded

            booking_cols_downgraded = {c["name"] for c in insp2.get_columns("bookings")}
            assert "service_mode" not in booking_cols_downgraded
            assert "chargeable_travel_fee" not in booking_cols_downgraded
