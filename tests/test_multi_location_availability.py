"""Comprehensive tests for multi-location relational topology and location-aware availability."""

from datetime import datetime, date, time, timezone
import pytest
from fastapi import HTTPException

from app.models.tenant import Tenant
from app.models.location import Location, LocationProvider
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.schedule import ProviderWorkDay, ProviderSpecialDay, BlockedTime
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.services.booking.availability_service import get_available_slots
from app.services.sms.chatwoot_service import resolve_chatwoot_binding, process_chatwoot_webhook


@pytest.fixture
def multi_loc_setup(db_session):
    """Seed multi-location topology for Tenant 1 and an isolated Tenant 2."""
    # Tenant 1: Premier Healthcare
    t1 = Tenant(name="Premier Healthcare", subdomain="premier-health")
    db_session.add(t1)
    db_session.commit()
    db_session.refresh(t1)

    # Locations for Tenant 1
    loc_a = Location(tenant_id=t1.id, name="City Central Clinic", active=True, is_visible=True)
    loc_b = Location(tenant_id=t1.id, name="North Shore Branch", active=True, is_visible=True)
    loc_c = Location(tenant_id=t1.id, name="South Shore Annex", active=True, is_visible=True)
    loc_inactive = Location(tenant_id=t1.id, name="Closed Location", active=False, is_visible=False)
    db_session.add_all([loc_a, loc_b, loc_c, loc_inactive])
    db_session.commit()

    # Providers for Tenant 1
    alice = Provider(tenant_id=t1.id, name="Dr. Alice", active=True)
    bob = Provider(tenant_id=t1.id, name="Dr. Bob", active=True)
    charlie = Provider(tenant_id=t1.id, name="Dr. Charlie", active=True)
    db_session.add_all([alice, bob, charlie])
    db_session.commit()

    # Link Providers to Locations:
    # Alice -> Location A only
    # Bob -> Location B only
    # Charlie -> Location A and Location B
    # (Location C has no providers assigned)
    lp_alice_a = LocationProvider(tenant_id=t1.id, location_id=loc_a.id, provider_id=alice.id)
    lp_bob_b = LocationProvider(tenant_id=t1.id, location_id=loc_b.id, provider_id=bob.id)
    lp_charlie_a = LocationProvider(tenant_id=t1.id, location_id=loc_a.id, provider_id=charlie.id)
    lp_charlie_b = LocationProvider(tenant_id=t1.id, location_id=loc_b.id, provider_id=charlie.id)
    db_session.add_all([lp_alice_a, lp_bob_b, lp_charlie_a, lp_charlie_b])

    # Service for Tenant 1 (60 minutes duration)
    svc = Service(tenant_id=t1.id, name="Consultation", duration=60, active=True, is_visible=True)
    db_session.add(svc)
    db_session.commit()

    # Link service to all three providers
    db_session.add_all([
        ServiceProvider(tenant_id=t1.id, service_id=svc.id, provider_id=alice.id),
        ServiceProvider(tenant_id=t1.id, service_id=svc.id, provider_id=bob.id),
        ServiceProvider(tenant_id=t1.id, service_id=svc.id, provider_id=charlie.id),
    ])

    # Weekly schedules: Monday (0) through Friday (4), 09:00 - 17:00 for Alice, Bob, Charlie
    for prov in [alice, bob, charlie]:
        for day in range(5):
            db_session.add(
                ProviderWorkDay(
                    tenant_id=t1.id,
                    provider_id=prov.id,
                    weekday=day,
                    start_time="09:00",
                    end_time="17:00",
                    is_working=True,
                )
            )

    # Isolated Tenant 2: Apex Medical
    t2 = Tenant(name="Apex Medical", subdomain="apex-med")
    db_session.add(t2)
    db_session.commit()

    loc_t2 = Location(tenant_id=t2.id, name="Apex West", active=True, is_visible=True)
    prov_t2 = Provider(tenant_id=t2.id, name="Dr. Dana", active=True)
    db_session.add_all([loc_t2, prov_t2])
    db_session.commit()

    lp_t2 = LocationProvider(tenant_id=t2.id, location_id=loc_t2.id, provider_id=prov_t2.id)
    db_session.add(lp_t2)
    db_session.commit()

    return {
        "t1": t1,
        "loc_a": loc_a,
        "loc_b": loc_b,
        "loc_c": loc_c,
        "loc_inactive": loc_inactive,
        "alice": alice,
        "bob": bob,
        "charlie": charlie,
        "svc": svc,
        "t2": t2,
        "loc_t2": loc_t2,
        "prov_t2": prov_t2,
    }


def test_availability_filtering_by_location(db_session, multi_loc_setup):
    """Slots at Location A must contain only Alice and Charlie; Bob must never appear."""
    data = multi_loc_setup
    test_date = datetime(2026, 10, 5, 0, 0, 0, tzinfo=timezone.utc)  # Monday

    # 1. Query for Location A
    slots_a = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_a"].id,
    )
    assert len(slots_a) > 0
    prov_ids_a = {s["provider_id"] for s in slots_a}
    assert prov_ids_a == {data["alice"].id, data["charlie"].id}
    assert data["bob"].id not in prov_ids_a

    # 2. Query for Location B
    slots_b = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_b"].id,
    )
    assert len(slots_b) > 0
    prov_ids_b = {s["provider_id"] for s in slots_b}
    assert prov_ids_b == {data["bob"].id, data["charlie"].id}
    assert data["alice"].id not in prov_ids_b

    # 3. Query for Location C (no providers assigned) -> 0 slots
    slots_c = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_c"].id,
    )
    assert len(slots_c) == 0

    # 4. Query with mismatched provider_id at Location A (asking for Bob at Location A)
    mismatched_slots = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=data["bob"].id,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_a"].id,
    )
    assert len(mismatched_slots) == 0


def test_location_specific_working_hours_and_special_closures(db_session, multi_loc_setup):
    """Verify that location-level workday closures and special day overrides are strictly respected."""
    data = multi_loc_setup
    test_date = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc)  # Tuesday

    # 1. Add a Location-level closure for Location A on Tuesday (2026-10-06)
    special_closure = ProviderSpecialDay(
        tenant_id=data["t1"].id,
        location_id=data["loc_a"].id,
        provider_id=None,
        date=test_date.date(),
        is_working=False,
        reason="Facility maintenance at Location A",
    )
    db_session.add(special_closure)
    db_session.commit()

    # Location A on Tuesday: 0 slots
    slots_a = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_a"].id,
    )
    assert len(slots_a) == 0

    # Location B on that same Tuesday: still available for Bob and Charlie
    slots_b = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_b"].id,
    )
    assert len(slots_b) > 0
    prov_ids_b = {s["provider_id"] for s in slots_b}
    assert prov_ids_b == {data["bob"].id, data["charlie"].id}

    # 2. Location constrained weekly working hours:
    # Location B on Wednesday (weekday 2) is only open 10:00 to 12:00
    wednesday_date = datetime(2026, 10, 7, 0, 0, 0, tzinfo=timezone.utc)
    loc_b_hours = ProviderWorkDay(
        tenant_id=data["t1"].id,
        location_id=data["loc_b"].id,
        provider_id=None,
        weekday=2,
        start_time="10:00",
        end_time="12:00",
        is_working=True,
    )
    db_session.add(loc_b_hours)
    db_session.commit()

    slots_wed = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=wednesday_date,
        service_id=data["svc"].id,
        location_id=data["loc_b"].id,
    )
    assert len(slots_wed) > 0
    # Every slot must start >= 10:00 and end <= 12:00
    for s in slots_wed:
        assert s["start"].time() >= time(10, 0)
        assert s["end"].time() <= time(12, 0)

    # 3. Inactive location produces 0 slots immediately
    slots_inactive = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_inactive"].id,
    )
    assert len(slots_inactive) == 0


def test_location_blocked_time(db_session, multi_loc_setup):
    """Blocked time applied to Location A prevents bookings during that window at Location A only."""
    data = multi_loc_setup
    test_date = datetime(2026, 10, 8, 0, 0, 0, tzinfo=timezone.utc)  # Thursday

    # Block 10:00 - 12:00 at Location A
    block = BlockedTime(
        tenant_id=data["t1"].id,
        location_id=data["loc_a"].id,
        provider_id=None,
        start_time=datetime(2026, 10, 8, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
        active=True,
        reason="Fire alarm inspection",
    )
    db_session.add(block)
    db_session.commit()

    slots_a = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_a"].id,
    )
    for s in slots_a:
        # No slot starts at 10:00 or 11:00
        assert s["start"].time() != time(10, 0)
        assert s["start"].time() != time(11, 0)

    # Location B on the same date has 10:00 and 11:00 available
    slots_b = get_available_slots(
        db=db_session,
        service_duration=60,
        provider_id=None,
        date=test_date,
        service_id=data["svc"].id,
        location_id=data["loc_b"].id,
    )
    b_start_times = {s["start"].time() for s in slots_b}
    assert time(10, 0) in b_start_times


def test_public_availability_api(client, multi_loc_setup):
    """Test GET and POST /api/public/availability with location_id filter and tenant isolation."""
    data = multi_loc_setup
    headers = {"X-Tenant": data["t1"].subdomain}

    # 1. GET /api/public/availability with location_id
    resp = client.get(
        "/api/public/availability",
        params={
            "service_id": data["svc"].id,
            "location_id": data["loc_a"].id,
            "date": "2026-10-05T00:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["ok"] is True
    prov_ids = {s["provider_id"] for s in res_data["data"]}
    assert data["alice"].id in prov_ids
    assert data["charlie"].id in prov_ids
    assert data["bob"].id not in prov_ids

    # 2. POST /api/public/availability with structured body
    resp_post = client.post(
        "/api/public/availability",
        json={
            "service_id": data["svc"].id,
            "location_id": data["loc_b"].id,
            "date": "2026-10-05T00:00:00Z",
        },
        headers=headers,
    )
    assert resp_post.status_code == 200
    post_data = resp_post.json()
    prov_ids_b = {s["provider_id"] for s in post_data["data"]}
    assert data["bob"].id in prov_ids_b
    assert data["charlie"].id in prov_ids_b
    assert data["alice"].id not in prov_ids_b

    # 3. Cross-tenant isolation: Requesting Tenant 2's location under Tenant 1 header -> 404
    resp_cross = client.get(
        "/api/public/availability",
        params={
            "service_id": data["svc"].id,
            "location_id": data["loc_t2"].id,
            "date": "2026-10-05T00:00:00Z",
        },
        headers=headers,
    )
    assert resp_cross.status_code == 404


def test_chatwoot_inbox_binding_resolution_granularities(db_session, multi_loc_setup):
    """Verify 3 distinct Chatwoot binding granularities: Tenant Default, Provider-Dedicated, Location-Dedicated."""
    data = multi_loc_setup
    t1 = data["t1"]
    alice = data["alice"]
    loc_a = data["loc_a"]

    # 1. Tenant Default Inbox (provider_id IS NULL, location_id IS NULL)
    binding_default = SmsChatwootBinding(
        tenant_id=t1.id,
        provider_id=None,
        location_id=None,
        chatwoot_account_id=100,
        chatwoot_inbox_id=10,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="token-default",
        webhook_secret="secret-default",
        is_enabled=True,
    )
    # 2. Location-Dedicated Inbox (location_id IS NOT NULL, provider_id IS NULL)
    binding_loc = SmsChatwootBinding(
        tenant_id=t1.id,
        provider_id=None,
        location_id=loc_a.id,
        chatwoot_account_id=100,
        chatwoot_inbox_id=20,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="token-loc-a",
        webhook_secret="secret-loc-a",
        is_enabled=True,
    )
    # 3. Provider-Dedicated Inbox (provider_id IS NOT NULL)
    binding_prov = SmsChatwootBinding(
        tenant_id=t1.id,
        provider_id=alice.id,
        location_id=None,
        chatwoot_account_id=100,
        chatwoot_inbox_id=30,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="token-alice",
        webhook_secret="secret-alice",
        is_enabled=True,
    )
    db_session.add_all([binding_default, binding_loc, binding_prov])
    db_session.commit()

    # Resolution test 1: Provider-dedicated match takes precedence
    resolved_prov = resolve_chatwoot_binding(db_session, tenant_id=t1.id, provider_id=alice.id)
    assert resolved_prov is not None
    assert resolved_prov.chatwoot_inbox_id == 30

    # Resolution test 2: Location-dedicated match takes precedence when no provider binding
    resolved_loc = resolve_chatwoot_binding(db_session, tenant_id=t1.id, location_id=loc_a.id)
    assert resolved_loc is not None
    assert resolved_loc.chatwoot_inbox_id == 20

    # Resolution test 3: Fallback to Tenant Default Inbox when neither provider nor location matches
    resolved_default = resolve_chatwoot_binding(db_session, tenant_id=t1.id, provider_id=data["bob"].id)
    assert resolved_default is not None
    assert resolved_default.chatwoot_inbox_id == 10

    # Webhook intake for Location-Dedicated Inbox:
    payload_loc = {
        "id": 9991,
        "content": "Hello location reception!",
        "message_type": "incoming",
        "inbox": {"id": 20},
        "conversation": {
            "id": 4001,
            "contact": {
                "id": 888,
                "phone_number": "+61411222333",
            },
        },
    }
    wh_result = process_chatwoot_webhook(db_session, payload_loc, token="secret-loc-a")
    assert wh_result["status"] == "success"

    # Verify conversation was assigned to Alice (active provider at Location A)
    conv = db_session.query(SmsConversation).filter(SmsConversation.chatwoot_conversation_id == 4001).first()
    assert conv is not None
    assert conv.provider_id in {alice.id, data["charlie"].id}
    assert conv.tenant_id == t1.id

    # Verify cross-tenant isolation on webhook:
    # A binding configured with Tenant 2's location under Tenant 1's binding fails scoping validation
    bad_binding = SmsChatwootBinding(
        tenant_id=t1.id,
        provider_id=None,
        location_id=data["loc_t2"].id,  # Belongs to Tenant 2!
        chatwoot_account_id=100,
        chatwoot_inbox_id=40,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="token-bad",
        webhook_secret="secret-bad",
        is_enabled=True,
    )
    db_session.add(bad_binding)
    db_session.commit()

    payload_bad = {
        "id": 9992,
        "content": "Infiltrating webhook",
        "message_type": "incoming",
        "inbox": {"id": 40},
        "conversation": {
            "id": 4002,
            "contact": {"id": 889, "phone_number": "+61411222444"},
        },
    }
    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(db_session, payload_bad, token="secret-bad")
    assert exc_info.value.status_code == 403
    assert "Location scoping validation failed" in exc_info.value.detail


def test_cross_tenant_location_provider_link_rejection(client, db_session, multi_loc_setup):
    """Attempting to link Tenant 2's location to Tenant 1's provider or vice-versa must fail with 404."""
    from app.models.user import User
    from app.core.security import create_access_token

    data = multi_loc_setup
    admin_t1 = User(
        tenant_id=data["t1"].id,
        login="admin_t1@premier.com",
        password_hash="testhash",
        role="admin",
    )
    db_session.add(admin_t1)
    db_session.commit()

    token_t1 = create_access_token({"sub": str(admin_t1.id)})
    headers = {"X-Tenant": data["t1"].subdomain, "X-Token": token_t1}

    # 1. Attempt to link Tenant 2's location (loc_t2) to Tenant 1's provider (alice) under Tenant 1 admin
    resp1 = client.post(
        f"/api/admin/locations/{data['loc_t2'].id}/providers/{data['alice'].id}",
        headers=headers,
    )
    assert resp1.status_code == 404

    # 2. Attempt to link Tenant 1's location (loc_a) to Tenant 2's provider (prov_t2) under Tenant 1 admin
    resp2 = client.post(
        f"/api/admin/locations/{data['loc_a'].id}/providers/{data['prov_t2'].id}",
        headers=headers,
    )
    assert resp2.status_code == 404

