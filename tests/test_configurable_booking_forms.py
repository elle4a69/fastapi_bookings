"""Core relationship and fixed-point booking-form behavior."""

from datetime import datetime, time, timedelta, timezone

from app.models import (
    BookingForm,
    Category,
    Client,
    Location,
    LocationService,
    Provider,
    ProviderWorkDay,
    Service,
    ServiceCategory,
    ServiceProvider,
    Tenant,
    User,
)
from app.core.security import create_access_token
from app.services.booking_form_resolver import resolve_booking_form
from app.services.booking_relationship_resolver import pair_allowed


def _form(tenant_id: int, **overrides) -> BookingForm:
    values = {
        "tenant_id": tenant_id,
        "name": "Default booking",
        "slug": "default-booking",
        "active": True,
        "module_order": ["location", "category", "service", "provider", "time"],
        "enabled_modules": {"location": True, "category": True, "service": True, "provider": True, "time": True},
        "predefined_values": {},
        "provider_selection_mode": "required",
        "appearance": {},
        "settings": {},
    }
    values.update(overrides)
    return BookingForm(**values)


def test_symmetric_universal_default_relationships(db_session):
    tenant = Tenant(name="Resolver", subdomain="resolver")
    db_session.add(tenant)
    db_session.flush()
    service_a = Service(tenant_id=tenant.id, name="A", duration=30, active=True)
    service_b = Service(tenant_id=tenant.id, name="B", duration=30, active=True)
    provider_a = Provider(tenant_id=tenant.id, name="A", active=True)
    provider_b = Provider(tenant_id=tenant.id, name="B", active=True)
    db_session.add_all([service_a, service_b, provider_a, provider_b])
    db_session.flush()

    assert pair_allowed(db_session, tenant.id, "service", service_a.id, "provider", provider_a.id)
    db_session.add(ServiceProvider(tenant_id=tenant.id, service_id=service_a.id, provider_id=provider_a.id))
    db_session.flush()

    assert pair_allowed(db_session, tenant.id, "service", service_a.id, "provider", provider_a.id)
    assert not pair_allowed(db_session, tenant.id, "service", service_a.id, "provider", provider_b.id)
    assert not pair_allowed(db_session, tenant.id, "service", service_b.id, "provider", provider_a.id)
    assert pair_allowed(db_session, tenant.id, "service", service_b.id, "provider", provider_b.id)


def test_predefined_service_propagates_to_unique_path(db_session):
    tenant = Tenant(name="Unique", subdomain="unique")
    db_session.add(tenant)
    db_session.flush()
    service = Service(tenant_id=tenant.id, name="Consult", duration=30, active=True)
    provider = Provider(tenant_id=tenant.id, name="Alex", active=True)
    location = Location(tenant_id=tenant.id, name="City")
    category = Category(tenant_id=tenant.id, name="Advice", active=True)
    db_session.add_all([service, provider, location, category])
    db_session.flush()
    db_session.add_all([
        ServiceProvider(tenant_id=tenant.id, service_id=service.id, provider_id=provider.id),
        ServiceCategory(tenant_id=tenant.id, service_id=service.id, category_id=category.id),
        LocationService(tenant_id=tenant.id, location_id=location.id, service_id=service.id),
    ])
    form = _form(tenant.id, predefined_values={"service_id": service.id})
    db_session.add(form)
    db_session.flush()

    result = resolve_booking_form(db_session, form)

    assert result["resolved_context"] == {
        "location_id": location.id,
        "category_id": category.id,
        "service_id": service.id,
        "provider_id": provider.id,
    }
    assert result["resolution_source"]["service"] == "predefined"
    assert result["resolution_source"]["provider"] == "inferred"
    assert result["visible_modules"] == ["time", "client"]


def test_optional_provider_stays_visible_with_anyone(db_session):
    tenant = Tenant(name="Optional", subdomain="optional")
    db_session.add(tenant)
    db_session.flush()
    service = Service(tenant_id=tenant.id, name="Consult", duration=30, active=True)
    provider = Provider(tenant_id=tenant.id, name="Alex", active=True)
    location = Location(tenant_id=tenant.id, name="City")
    category = Category(tenant_id=tenant.id, name="Advice", active=True)
    db_session.add_all([service, provider, location, category])
    db_session.flush()
    form = _form(tenant.id, predefined_values={"service_id": service.id}, provider_selection_mode="optional")
    db_session.add(form)
    db_session.flush()

    result = resolve_booking_form(db_session, form)

    assert "provider" in result["visible_modules"]
    assert result["options"]["provider"][0] == {"id": None, "name": "Anyone available"}


def test_automatic_provider_is_hidden(db_session):
    tenant = Tenant(name="Auto", subdomain="auto")
    db_session.add(tenant)
    db_session.flush()
    service = Service(tenant_id=tenant.id, name="Consult", duration=30, active=True)
    provider = Provider(tenant_id=tenant.id, name="Alex", active=True)
    location = Location(tenant_id=tenant.id, name="City")
    category = Category(tenant_id=tenant.id, name="Advice", active=True)
    db_session.add_all([service, provider, location, category])
    db_session.flush()
    form = _form(tenant.id, predefined_values={"service_id": service.id}, provider_selection_mode="automatic")
    db_session.add(form)
    db_session.flush()

    result = resolve_booking_form(db_session, form)

    assert result["resolution_source"]["provider"] == "automatic"
    assert "provider" not in result["visible_modules"]


def test_admin_crud_and_public_resolve_contract(client, db_session):
    tenant = Tenant(name="API", subdomain="forms-api")
    db_session.add(tenant)
    db_session.flush()
    admin = User(tenant_id=tenant.id, login="forms-admin", password_hash="hash", role="admin")
    service = Service(tenant_id=tenant.id, name="Consult", duration=30, active=True)
    provider = Provider(tenant_id=tenant.id, name="Alex", active=True)
    location = Location(tenant_id=tenant.id, name="City")
    category = Category(tenant_id=tenant.id, name="Advice", active=True)
    db_session.add_all([admin, service, provider, location, category])
    db_session.commit()
    admin_token = create_access_token({"sub": str(admin.id)})
    public_token = create_access_token({"sub": tenant.subdomain})
    admin_headers = {"X-Tenant": tenant.subdomain, "X-Token": admin_token}
    public_headers = {"X-Tenant": tenant.subdomain, "X-Token": public_token}
    payload = {
        "name": "Website",
        "slug": "website",
        "module_order": ["location", "category", "service", "provider", "time"],
        "enabled_modules": {"location": True, "category": True, "service": True, "provider": True, "time": True},
        "predefined_values": {"service_id": service.id},
        "provider_selection_mode": "required",
    }

    created = client.post("/api/admin/booking-forms", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    preview = client.get(f"/api/admin/booking-forms/{form_id}/preview", headers=admin_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["visible_modules"] == ["time", "client"]

    public = client.post(
        "/api/public/booking-forms/website/resolve",
        headers=public_headers,
        json={"selections": {}},
    )
    assert public.status_code == 200, public.text
    assert public.json()["data"]["resolution_source"]["service"] == "predefined"

    duplicate = client.post(
        f"/api/admin/booking-forms/{form_id}/duplicate",
        headers=admin_headers,
        json={},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["active"] is False

    inline = client.post(
        f"/api/admin/relationships/provider/{provider.id}/service/create-and-connect",
        headers=admin_headers,
        json={"record": {"name": "Inline service", "duration": 45, "active": True}},
    )
    assert inline.status_code == 201, inline.text
    inline_service_id = inline.json()["data"]["record"]["id"]
    inline_service = db_session.query(Service).filter(Service.id == inline_service_id).one()
    assert inline_service.tenant_id == tenant.id

    editor = client.get(f"/api/admin/providers/{provider.id}/editor", headers=admin_headers)
    assert editor.status_code == 200, editor.text
    linked_ids = {row["id"] for row in editor.json()["data"]["relationships"]["service"]["linked"]}
    assert inline_service_id in linked_ids


def test_cross_tenant_preset_is_rejected(client, db_session):
    tenant_a = Tenant(name="Tenant A forms", subdomain="forms-a")
    tenant_b = Tenant(name="Tenant B forms", subdomain="forms-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()
    admin = User(tenant_id=tenant_a.id, login="forms-a-admin", password_hash="hash", role="admin")
    foreign_service = Service(tenant_id=tenant_b.id, name="Foreign", duration=30, active=True)
    db_session.add_all([admin, foreign_service])
    db_session.commit()
    headers = {"X-Tenant": tenant_a.subdomain, "X-Token": create_access_token({"sub": str(admin.id)})}

    response = client.post(
        "/api/admin/booking-forms",
        headers=headers,
        json={
            "name": "Invalid",
            "slug": "invalid",
            "predefined_values": {"service_id": foreign_service.id},
        },
    )
    assert response.status_code == 422, response.text


def test_widget_end_to_end_automatic_assignment_and_stale_slot(client, db_session):
    tenant = Tenant(name="E2E forms", subdomain="forms-e2e")
    other_tenant = Tenant(name="E2E other", subdomain="forms-e2e-other")
    db_session.add_all([tenant, other_tenant])
    db_session.flush()
    admin = User(tenant_id=tenant.id, login="forms-e2e-admin", password_hash="hash", role="admin")
    customer = Client(tenant_id=tenant.id, name="Booking customer", email="e2e@example.com")
    service = Service(tenant_id=tenant.id, name="Automatic consult", duration=30, active=True)
    provider_a = Provider(tenant_id=tenant.id, name="Provider A", active=True)
    provider_b = Provider(tenant_id=tenant.id, name="Provider B", active=True)
    db_session.add_all([admin, customer, service, provider_a, provider_b])
    db_session.flush()

    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    slot_start = datetime.combine(target_date, time(hour=9), tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(minutes=30)
    for provider in (provider_a, provider_b):
        db_session.add(ProviderWorkDay(
            tenant_id=tenant.id,
            provider_id=provider.id,
            weekday=target_date.weekday(),
            start_time="09:00",
            end_time="09:30",
            is_working=True,
        ))
    db_session.commit()

    admin_headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(admin.id)}),
    }
    public_headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": tenant.subdomain}),
    }
    created = client.post(
        "/api/admin/booking-forms",
        headers=admin_headers,
        json={
            "name": "Automatic widget",
            "slug": "automatic-widget",
            "enabled_modules": {
                "location": False,
                "category": False,
                "service": True,
                "provider": True,
                "time": True,
            },
            "predefined_values": {"service_id": service.id},
            "provider_selection_mode": "automatic",
        },
    )
    assert created.status_code == 201, created.text

    availability_payload = {
        "selections": {},
        "date_from": slot_start.isoformat(),
        "date_to": slot_end.isoformat(),
    }
    availability = client.post(
        "/api/public/booking-forms/automatic-widget/availability",
        headers=public_headers,
        json=availability_payload,
    )
    assert availability.status_code == 200, availability.text
    slots = availability.json()["data"]["slots"]
    assert len(slots) == 1
    assert slots[0]["provider_id"] == min(provider_a.id, provider_b.id)

    booking_payload = {
        "client_id": customer.id,
        "selections": {},
        "start_time": slot_start.isoformat(),
        "end_time": slot_end.isoformat(),
    }
    first = client.post(
        "/api/public/booking-forms/automatic-widget/bookings",
        headers=public_headers,
        json=booking_payload,
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["provider_id"] == min(provider_a.id, provider_b.id)

    second = client.post(
        "/api/public/booking-forms/automatic-widget/bookings",
        headers=public_headers,
        json=booking_payload,
    )
    assert second.status_code == 201, second.text
    assert second.json()["data"]["provider_id"] == max(provider_a.id, provider_b.id)

    stale = client.post(
        "/api/public/booking-forms/automatic-widget/bookings",
        headers=public_headers,
        json=booking_payload,
    )
    assert stale.status_code == 409, stale.text

    cross_tenant = client.post(
        "/api/public/booking-forms/automatic-widget/resolve",
        headers={
            "X-Tenant": other_tenant.subdomain,
            "X-Token": create_access_token({"sub": other_tenant.subdomain}),
        },
        json={"selections": {}},
    )
    assert cross_tenant.status_code == 404, cross_tenant.text
