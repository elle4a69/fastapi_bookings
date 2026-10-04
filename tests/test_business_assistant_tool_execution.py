"""Comprehensive tests for Business Assistant tool execution and slot availability (WP3).

All tests execute against live database models and real domain scheduling engines.
Mocks are strictly prohibited.
"""

from datetime import datetime, timezone
import pytest

from app.core.security import create_access_token
from app.models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantToolRun,
)
from app.models.location import Location
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import (
    ALL_BUSINESS_ASSISTANT_TOOLS,
    BOOKING_AVAILABILITY_TOOLS,
    PRODUCT_HELP_TOOLS,
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _owner(db_session, suffix: str, *, enabled_modules: list[str] | None = None) -> tuple[Tenant, User]:
    tenant = Tenant(
        name=f"ToolExec Tenant {suffix}",
        subdomain=f"toolexec-{suffix}",
        enabled_modules=enabled_modules,
        timezone="Australia/Sydney",
        country="Australia",
        subscription_tier="growth",
        addon_quota=3,
        allow_in_call=True,
        allow_out_call=True,
        max_advance_days=30,
    )
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id,
        login=f"toolexec-owner-{suffix}",
        password_hash="test",
        role="owner",
    )
    db_session.add(user)
    db_session.flush()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_tool_schemas_and_pack_composition(db_session):
    """Verify tool definitions, JSON schemas, and modular pack selection."""
    tenant, user = _owner(db_session, "schemas")
    adapters = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id)

    # 1. Product Help Pack
    product_registry = BusinessAssistantToolRegistry(adapters, packs=("product_help",))
    product_names = [t["function"]["name"] for t in product_registry.schemas]
    assert product_names == ["read_product_help", "read_onboarding_progress", "read_system_settings"]

    # 2. Booking Availability Pack
    booking_registry = BusinessAssistantToolRegistry(adapters, packs=("booking_availability",))
    booking_names = [t["function"]["name"] for t in booking_registry.schemas]
    assert booking_names == ["list_services", "list_providers", "check_slot_availability"]

    # 3. Default Unified Pack
    unified_registry = BusinessAssistantToolRegistry(adapters)
    unified_names = [t["function"]["name"] for t in unified_registry.schemas]
    assert set(unified_names) == set(product_names + booking_names)
    assert len(unified_registry.schemas) == 6

    # Verify JSON Schema properties on tool definitions
    for schema in unified_registry.schemas:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn and "description" in fn and "parameters" in fn
        assert fn["strict"] is True
        assert fn["parameters"]["type"] == "object"
        assert fn["parameters"]["additionalProperties"] is False


def test_read_system_settings_safe_and_scrubbed(db_session):
    """Verify safe tenant settings read without exposing secrets or credentials."""
    tenant, user = _owner(db_session, "settings", enabled_modules=["calendar", "bookings"])
    tenant.assistant_policy = "Be helpful and direct."
    tenant.chatwoot_account_id = 99999  # Internal / private ID
    db_session.commit()

    adapters = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id)
    registry = BusinessAssistantToolRegistry(adapters)

    # Read all safe settings
    res = registry.execute("read_system_settings", {})
    assert res["status"] == "ok"
    settings_data = res["settings"]
    assert settings_data["name"] == tenant.name
    assert settings_data["subdomain"] == tenant.subdomain
    assert settings_data["timezone"] == "Australia/Sydney"
    assert settings_data["subscription_tier"] == "growth"
    assert "calendar" in settings_data["enabled_modules"]
    assert settings_data["assistant_policy"] == "Be helpful and direct."

    # Verify secrets and internal IDs are NOT present
    assert "chatwoot_account_id" not in settings_data
    assert "password_hash" not in settings_data
    assert "secret" not in settings_data
    assert "api_key" not in settings_data

    # Read specific safe key
    tz_res = registry.execute("read_system_settings", {"setting_key": "timezone"})
    assert tz_res["status"] == "ok"
    assert tz_res["key"] == "timezone"
    assert tz_res["value"] == "Australia/Sydney"

    # Reject non-allowlisted / secret keys
    reject_res = registry.execute("read_system_settings", {"setting_key": "chatwoot_account_id"})
    assert reject_res["status"] == "rejected"
    assert "not accessible" in reject_res["reason"].lower()


def test_list_services_tool_with_filters_and_tenant_isolation(db_session):
    """Verify listing services with active filtering, bounds, and strict tenant isolation."""
    tenant_a, user_a = _owner(db_session, "svc-a")
    tenant_b, user_b = _owner(db_session, "svc-b")

    svc_active = Service(
        tenant_id=tenant_a.id,
        name="Deep Tissue Massage",
        description="Relaxing 60m session",
        duration=60,
        price=120.0,
        active=True,
        allow_in_call=True,
        allow_out_call=False,
    )
    svc_inactive = Service(
        tenant_id=tenant_a.id,
        name="Old Swedish Massage",
        duration=45,
        price=90.0,
        active=False,
    )
    svc_other = Service(
        tenant_id=tenant_b.id,
        name="Secret Tenant B Service",
        duration=30,
        price=50.0,
        active=True,
    )
    db_session.add_all([svc_active, svc_inactive, svc_other])
    db_session.commit()

    registry_a = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant_a.id, user_id=user_a.id)
    )

    # Active only (default)
    res_active = registry_a.execute("list_services", {})
    assert res_active["status"] == "ok"
    assert len(res_active["services"]) == 1
    assert res_active["services"][0]["name"] == "Deep Tissue Massage"
    assert res_active["services"][0]["duration"] == 60
    assert res_active["services"][0]["price"] == 120.0

    # Include inactive
    res_all = registry_a.execute("list_services", {"active_only": False})
    assert res_all["status"] == "ok"
    assert len(res_all["services"]) == 2
    svc_names = [s["name"] for s in res_all["services"]]
    assert "Deep Tissue Massage" in svc_names
    assert "Old Swedish Massage" in svc_names
    assert "Secret Tenant B Service" not in svc_names

    # Bounds validation
    bad_limit = registry_a.execute("list_services", {"limit": 999})
    assert bad_limit["status"] == "rejected"


def test_list_providers_tool_with_service_filter_and_role_bounds(db_session):
    """Verify listing providers with qualification filtering and provider-role bounds."""
    tenant, user_owner = _owner(db_session, "prov")

    prov_1 = Provider(tenant_id=tenant.id, name="Dr. Alice Smith", active=True, email="alice@test.local")
    prov_2 = Provider(tenant_id=tenant.id, name="Dr. Bob Jones", active=True, email="bob@test.local")
    service = Service(tenant_id=tenant.id, name="Chiropractic Care", duration=30, active=True)
    db_session.add_all([prov_1, prov_2, service])
    db_session.flush()

    # Link only prov_1 to service
    db_session.add(ServiceProvider(tenant_id=tenant.id, provider_id=prov_1.id, service_id=service.id))
    db_session.commit()

    # Owner lists all providers
    owner_registry = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user_owner.id)
    )
    all_provs = owner_registry.execute("list_providers", {})
    assert all_provs["status"] == "ok"
    assert len(all_provs["providers"]) == 2

    # Filter by service_id
    svc_provs = owner_registry.execute("list_providers", {"service_id": service.id})
    assert svc_provs["status"] == "ok"
    assert len(svc_provs["providers"]) == 1
    assert svc_provs["providers"][0]["name"] == "Dr. Alice Smith"

    # Cross-tenant service filter fails safely
    tenant_other, _ = _owner(db_session, "prov-other")
    other_svc = Service(tenant_id=tenant_other.id, name="Other Service", duration=30, active=True)
    db_session.add(other_svc)
    db_session.commit()
    cross_res = owner_registry.execute("list_providers", {"service_id": other_svc.id})
    assert cross_res["status"] == "rejected"

    # Provider user: role-aware self-scoping
    user_prov = User(
        tenant_id=tenant.id,
        login="provider-bob",
        password_hash="test",
        role="provider",
        provider_id=prov_2.id,
    )
    db_session.add(user_prov)
    db_session.commit()

    prov_registry = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user_prov.id)
    )
    prov_res = prov_registry.execute("list_providers", {})
    assert prov_res["status"] == "ok"
    assert len(prov_res["providers"]) == 1
    assert prov_res["providers"][0]["id"] == prov_2.id


def test_check_slot_availability_real_scheduling_engine(db_session):
    """Verify live slot calculation using real database records and scheduling engine."""
    tenant, user = _owner(db_session, "avail")
    service = Service(
        tenant_id=tenant.id,
        name="Physiotherapy Initial",
        duration=30,
        price=100.0,
        active=True,
        buffer_before=0,
        buffer_after=0,
    )
    provider = Provider(
        tenant_id=tenant.id,
        name="Sarah Connor",
        active=True,
    )
    db_session.add_all([service, provider])
    db_session.flush()

    # Link provider to service
    db_session.add(ServiceProvider(tenant_id=tenant.id, provider_id=provider.id, service_id=service.id))

    # Add ProviderWorkDay for Monday (weekday=0) from 09:00 to 11:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id,
        provider_id=provider.id,
        weekday=0,
        start_time="09:00",
        end_time="11:00",
        is_working=True,
    )
    db_session.add(workday)
    db_session.commit()

    registry = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id)
    )

    # 2026-10-05 is a Monday
    monday_date = "2026-10-05"
    slots_res = registry.execute(
        "check_slot_availability",
        {
            "service_id": service.id,
            "start_date": monday_date,
            "provider_id": provider.id,
        },
    )

    assert slots_res["status"] == "ok"
    avail = slots_res["availability"]
    assert avail["service_id"] == service.id
    assert avail["service_name"] == "Physiotherapy Initial"
    assert avail["total_available_slots"] > 0
    # Slots within 09:00 to 11:00 for 30m appointment: 09:00, 09:15, 09:30, 09:45, 10:00, 10:15, 10:30
    assert len(avail["slots"]) >= 1
    first_slot = avail["slots"][0]
    assert "09:00" in first_slot["start_time"]
    assert first_slot["provider_id"] == provider.id
    assert first_slot["provider_name"] == "Sarah Connor"

    # Sunday 2026-10-04 has no workdays configured -> returns 0 slots cleanly
    sunday_res = registry.execute(
        "check_slot_availability",
        {
            "service_id": service.id,
            "start_date": "2026-10-04",
            "provider_id": provider.id,
        },
    )
    assert sunday_res["status"] == "ok"
    assert sunday_res["availability"]["total_available_slots"] == 0
    assert len(sunday_res["availability"]["slots"]) == 0


def test_check_slot_availability_validation_and_security_bounds(db_session):
    """Verify input validation, date range bounds, and cross-tenant rejections."""
    tenant_a, user_a = _owner(db_session, "sec-a")
    tenant_b, user_b = _owner(db_session, "sec-b")

    svc_a = Service(tenant_id=tenant_a.id, name="Service A", duration=30, active=True)
    svc_b = Service(tenant_id=tenant_b.id, name="Service B", duration=30, active=True)
    db_session.add_all([svc_a, svc_b])
    db_session.commit()

    registry_a = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant_a.id, user_id=user_a.id)
    )

    # 1. Invalid date format
    bad_date = registry_a.execute("check_slot_availability", {"service_id": svc_a.id, "start_date": "not-a-date"})
    assert bad_date["status"] == "rejected"
    assert "invalid start_date" in bad_date["reason"].lower()

    # 2. Date range exceeding 7 days
    range_err = registry_a.execute(
        "check_slot_availability",
        {"service_id": svc_a.id, "start_date": "2026-10-01", "end_date": "2026-10-15"},
    )
    assert range_err["status"] == "rejected"
    assert "cannot exceed 7 days" in range_err["reason"].lower()

    # 3. Cross-tenant service lookup rejected
    cross_svc = registry_a.execute(
        "check_slot_availability",
        {"service_id": svc_b.id, "start_date": "2026-10-05"},
    )
    assert cross_svc["status"] == "rejected"

    # 4. Role-awareness: Provider user cannot check slots for another provider
    prov_1 = Provider(tenant_id=tenant_a.id, name="Prov 1", active=True)
    prov_2 = Provider(tenant_id=tenant_a.id, name="Prov 2", active=True)
    db_session.add_all([prov_1, prov_2])
    db_session.flush()

    user_prov = User(
        tenant_id=tenant_a.id,
        login="provider-user",
        password_hash="test",
        role="provider",
        provider_id=prov_1.id,
    )
    db_session.add(user_prov)
    db_session.commit()

    prov_reg = BusinessAssistantToolRegistry(
        BusinessAssistantReadAdapters(db_session, tenant_id=tenant_a.id, user_id=user_prov.id)
    )
    tamper_res = prov_reg.execute(
        "check_slot_availability",
        {"service_id": svc_a.id, "start_date": "2026-10-05", "provider_id": prov_2.id},
    )
    assert tamper_res["status"] == "rejected"
    assert "own schedule" in tamper_res["reason"].lower()


def test_conversation_tool_execution_and_telemetry_audit(db_session):
    """Verify tool execution via BusinessAssistantService records structural telemetry."""
    tenant, user = _owner(db_session, "audit")
    svc = Service(tenant_id=tenant.id, name="Audit Service", duration=30, active=True)
    db_session.add(svc)
    db_session.commit()

    service = BusinessAssistantService(db_session, tenant.id, user.id)
    conversation = service.create_conversation(title="Tool Audit Test")

    # Execute tool via service
    result = service.execute_tool(
        conversation_id=conversation.id,
        name="list_services",
        arguments={},
    )
    assert result["status"] == "ok"
    assert len(result["services"]) == 1

    # Check structural telemetry in business_assistant_tool_runs
    tool_runs = (
        db_session.query(BusinessAssistantToolRun)
        .filter(
            BusinessAssistantToolRun.conversation_id == conversation.id,
            BusinessAssistantToolRun.tenant_id == tenant.id,
        )
        .all()
    )
    assert len(tool_runs) == 1
    assert tool_runs[0].tool_name == "list_services"
    assert tool_runs[0].status == "ok"
    assert tool_runs[0].duration_ms is not None
    assert tool_runs[0].duration_ms >= 0


def test_api_tool_execution_endpoint_and_realtime_tools_endpoint(client, db_session):
    """Verify HTTP tool execution endpoints with authentication and tenant boundaries."""
    tenant_a, user_a = _owner(db_session, "api-a")
    tenant_b, user_b = _owner(db_session, "api-b")
    headers_a = _headers(tenant_a, user_a)
    headers_b = _headers(tenant_b, user_b)

    service_a = BusinessAssistantService(db_session, tenant_a.id, user_a.id)
    conv_a = service_a.create_conversation(title="API Tool Exec Conv")

    # 1. Execute tool via POST /conversations/{id}/tools
    res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_a.id}/tools",
        headers=headers_a,
        json={"name": "read_product_help", "arguments": {}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "product_help" in data["result"]

    # 2. Execute tool via POST /conversations/{id}/realtime/tools
    res_rt = client.post(
        f"/api/admin/business-assistant/conversations/{conv_a.id}/realtime/tools",
        headers=headers_a,
        json={"name": "read_system_settings", "arguments": {"setting_key": "timezone"}},
    )
    assert res_rt.status_code == 200
    data_rt = res_rt.json()
    assert data_rt["status"] == "ok"
    assert data_rt["result"]["value"] == "Australia/Sydney"

    # 3. Cross-tenant access fails with 404
    cross_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_a.id}/tools",
        headers=headers_b,
        json={"name": "read_product_help", "arguments": {}},
    )
    assert cross_res.status_code == 404

    # 4. Unknown tool returns rejected status cleanly
    unknown_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_a.id}/tools",
        headers=headers_a,
        json={"name": "unknown_tool", "arguments": {}},
    )
    assert unknown_res.status_code == 200
    assert unknown_res.json()["status"] == "rejected"
