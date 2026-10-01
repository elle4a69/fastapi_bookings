"""Tests for Chatwoot Industry Automation, Custom Attributes & Macro Provisioning."""

import json
import pytest
from unittest.mock import MagicMock, patch
import httpx

from app.models.tenant import Tenant
from app.models.tenant_translation import TenantTranslation
from app.services.sms.chatwoot_industry_service import (
    INDUSTRY_CUSTOM_ATTRIBUTES,
    INDUSTRY_CANNED_RESPONSES,
    detect_tenant_industry,
    provision_industry_custom_attributes,
    provision_industry_canned_responses,
    sync_industry_presets,
)
from app.services.sms.chatwoot_provisioning_service import provision_tenant_chatwoot


def test_industry_dictionaries_structure():
    """Verify all 4 industry presets define expected custom attributes and canned responses."""
    expected_industries = ["allied_health", "automotive", "wellness_salon", "professional_services"]

    for ind in expected_industries:
        assert ind in INDUSTRY_CUSTOM_ATTRIBUTES
        assert ind in INDUSTRY_CANNED_RESPONSES

        attrs = INDUSTRY_CUSTOM_ATTRIBUTES[ind]
        assert len(attrs) == 3
        for attr in attrs:
            assert "key" in attr
            assert "display_name" in attr
            assert "display_type" in attr
            assert "model" in attr
            assert attr["model"] == "conversation_attribute"

        canned = INDUSTRY_CANNED_RESPONSES[ind]
        assert len(canned) >= 4
        for c in canned:
            assert "short_code" in c
            assert "content" in c
            assert len(c["short_code"]) >= 2
            assert len(c["content"]) > 10

    # Specific attribute key assertions per Phase 4 specification
    allied_keys = {a["key"] for a in INDUSTRY_CUSTOM_ATTRIBUTES["allied_health"]}
    assert {"gp_referral_number", "health_fund", "injury_type"}.issubset(allied_keys)

    auto_keys = {a["key"] for a in INDUSTRY_CUSTOM_ATTRIBUTES["automotive"]}
    assert {"vehicle_vin", "vehicle_rego", "service_mileage"}.issubset(auto_keys)

    salon_keys = {a["key"] for a in INDUSTRY_CUSTOM_ATTRIBUTES["wellness_salon"]}
    assert {"preferred_practitioner", "hair_length", "patch_test_date"}.issubset(salon_keys)

    prof_keys = {a["key"] for a in INDUSTRY_CUSTOM_ATTRIBUTES["professional_services"]}
    assert {"client_company", "case_reference", "billing_reference"}.issubset(prof_keys)


def test_detect_tenant_industry(db_session):
    """Verify tenant industry detection from terminology profile."""
    # 1. Allied Health
    tenant1 = Tenant(name="Clinic A", subdomain="clinic-a")
    db_session.add(tenant1)
    db_session.commit()
    t1 = TenantTranslation(tenant_id=tenant1.id, terminology={"client": "Patient", "provider": "Practitioner"})
    db_session.add(t1)
    db_session.commit()
    db_session.refresh(tenant1)
    assert detect_tenant_industry(tenant1, db_session) == "allied_health"

    # 2. Automotive
    tenant2 = Tenant(name="Auto B", subdomain="auto-b")
    db_session.add(tenant2)
    db_session.commit()
    t2 = TenantTranslation(tenant_id=tenant2.id, terminology={"client": "Customer", "provider": "Technician"})
    db_session.add(t2)
    db_session.commit()
    db_session.refresh(tenant2)
    assert detect_tenant_industry(tenant2, db_session) == "automotive"

    # 3. Wellness / Salon
    tenant3 = Tenant(name="Salon C", subdomain="salon-c")
    db_session.add(tenant3)
    db_session.commit()
    t3 = TenantTranslation(tenant_id=tenant3.id, terminology={"client": "Client", "provider": "Stylist"})
    db_session.add(t3)
    db_session.commit()
    db_session.refresh(tenant3)
    assert detect_tenant_industry(tenant3, db_session) == "wellness_salon"

    # 4. Professional Services
    tenant4 = Tenant(name="Law D", subdomain="law-d")
    db_session.add(tenant4)
    db_session.commit()
    t4 = TenantTranslation(tenant_id=tenant4.id, terminology={"client": "Client", "provider": "Consultant"})
    db_session.add(t4)
    db_session.commit()
    db_session.refresh(tenant4)
    assert detect_tenant_industry(tenant4, db_session) == "professional_services"

    # 5. Default fallback
    tenant5 = Tenant(name="Default E", subdomain="default-e")
    db_session.add(tenant5)
    db_session.commit()
    db_session.refresh(tenant5)
    assert detect_tenant_industry(tenant5, db_session) == "allied_health"


def test_provision_industry_custom_attributes_success_and_idempotency():
    """Verify custom attribute provisioning with real mock transport and idempotency."""
    stored_attributes = []

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if request.method == "GET" and "/custom_attribute_definitions" in url:
            return httpx.Response(200, json=stored_attributes)
        elif request.method == "POST" and "/custom_attribute_definitions" in url:
            payload = json.loads(request.content.decode("utf-8"))
            new_item = dict(payload)
            new_item["id"] = len(stored_attributes) + 1
            stored_attributes.append(new_item)
            return httpx.Response(201, json=new_item)
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    # First call: provisions all 3 attributes
    results = provision_industry_custom_attributes(
        account_id=10,
        industry="automotive",
        client=client,
        base_url="http://mock-chatwoot:4000",
        api_token="test-api-token",
    )
    assert len(results) == 3
    for r in results:
        assert r["status"] == "created"
        assert "details" in r

    assert len(stored_attributes) == 3
    assert {a["attribute_key"] for a in stored_attributes} == {"vehicle_vin", "vehicle_rego", "service_mileage"}

    # Second call: idempotent, skips already existing attributes
    results2 = provision_industry_custom_attributes(
        account_id=10,
        industry="automotive",
        client=client,
        base_url="http://mock-chatwoot:4000",
        api_token="test-api-token",
    )
    assert len(results2) == 3
    for r in results2:
        assert r["status"] == "already_exists"

    # Stored attributes count did not change
    assert len(stored_attributes) == 3


def test_provision_industry_canned_responses_success_and_idempotency():
    """Verify canned responses provisioning with mock transport and idempotency."""
    stored_canned = []

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if request.method == "GET" and "/canned_responses" in url:
            return httpx.Response(200, json=stored_canned)
        elif request.method == "POST" and "/canned_responses" in url:
            payload = json.loads(request.content.decode("utf-8"))
            new_item = dict(payload)
            new_item["id"] = len(stored_canned) + 1
            stored_canned.append(new_item)
            return httpx.Response(201, json=new_item)
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    # First call: provisions all canned responses for allied_health
    results = provision_industry_canned_responses(
        account_id=20,
        industry="allied_health",
        client=client,
        base_url="http://mock-chatwoot:4000",
        api_token="test-api-token",
    )
    assert len(results) >= 4
    for r in results:
        assert r["status"] == "created"

    assert len(stored_canned) == len(results)

    # Second call: idempotently skips existing
    results2 = provision_industry_canned_responses(
        account_id=20,
        industry="allied_health",
        client=client,
        base_url="http://mock-chatwoot:4000",
        api_token="test-api-token",
    )
    for r in results2:
        assert r["status"] == "already_exists"

    assert len(stored_canned) == len(results)


def test_sync_industry_presets_combined():
    """Verify sync_industry_presets executes both custom attributes and macros."""
    stored_attributes = []
    stored_canned = []

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if request.method == "GET" and "/custom_attribute_definitions" in url:
            return httpx.Response(200, json=stored_attributes)
        elif request.method == "POST" and "/custom_attribute_definitions" in url:
            payload = json.loads(request.content.decode("utf-8"))
            payload["id"] = len(stored_attributes) + 1
            stored_attributes.append(payload)
            return httpx.Response(201, json=payload)
        elif request.method == "GET" and "/canned_responses" in url:
            return httpx.Response(200, json=stored_canned)
        elif request.method == "POST" and "/canned_responses" in url:
            payload = json.loads(request.content.decode("utf-8"))
            payload["id"] = len(stored_canned) + 1
            stored_canned.append(payload)
            return httpx.Response(201, json=payload)
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    res = sync_industry_presets(
        account_id=30,
        industry="professional_services",
        client=client,
        base_url="http://mock-chatwoot:4000",
        api_token="test-api-token",
    )

    assert res["account_id"] == 30
    assert res["industry"] == "professional_services"
    assert len(res["custom_attributes"]) == 3
    assert len(res["canned_responses"]) >= 4
    assert len(stored_attributes) == 3
    assert len(stored_canned) >= 4


def test_invalid_industry_raises():
    """Verify unknown industry presets raise ValueError."""
    with pytest.raises(ValueError, match="Unknown industry 'spaceship_repairs'"):
        provision_industry_custom_attributes(account_id=1, industry="spaceship_repairs")

    with pytest.raises(ValueError, match="Unknown industry 'spaceship_repairs'"):
        provision_industry_canned_responses(account_id=1, industry="spaceship_repairs")


def test_provision_tenant_chatwoot_triggers_industry_provisioning(db_session):
    """Verify tenant provisioning triggers Phase 7 industry custom attribute and macro provisioning."""
    tenant = Tenant(name="Holistic Wellness", subdomain="holistic-wellness", chatwoot_account_id=50)
    db_session.add(tenant)
    db_session.commit()

    translation = TenantTranslation(tenant_id=tenant.id, terminology={"client": "Client", "provider": "Stylist"})
    db_session.add(translation)
    db_session.commit()

    captured_requests = []

    def mock_chatwoot(request: httpx.Request):
        url = str(request.url)
        captured_requests.append((request.method, url))

        if "/inboxes" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        elif "/inboxes" in url and request.method == "POST":
            return httpx.Response(201, json={"id": 101, "name": "Test Inbox"})
        elif "/webhooks" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        elif "/webhooks" in url and request.method == "POST":
            return httpx.Response(201, json={"id": 201, "url": "http://webhook"})
        elif "/agents" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        elif "/custom_attribute_definitions" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        elif "/custom_attribute_definitions" in url and request.method == "POST":
            return httpx.Response(201, json={"id": 301, "attribute_key": "patch_test_date"})
        elif "/canned_responses" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        elif "/canned_responses" in url and request.method == "POST":
            return httpx.Response(201, json={"id": 401, "short_code": "patch_test"})
        return httpx.Response(200, json={})

    with patch("httpx.Client", return_value=httpx.Client(transport=httpx.MockTransport(mock_chatwoot))):
        result = provision_tenant_chatwoot(
            db=db_session,
            tenant_id=tenant.id,
            chatwoot_base_url="http://mock-chatwoot:4000",
            api_token="test-token",
            platform_token="test-platform-token",
        )

    assert result.success is True
    assert result.industry_provisioning is not None
    assert result.industry_provisioning["industry"] == "wellness_salon"
    assert len(result.industry_provisioning["custom_attributes"]) == 3
    assert len(result.industry_provisioning["canned_responses"]) >= 4

    # Verify custom_attribute_definitions and canned_responses endpoints were called
    attr_posts = [req for req in captured_requests if req[0] == "POST" and "custom_attribute_definitions" in req[1]]
    canned_posts = [req for req in captured_requests if req[0] == "POST" and "canned_responses" in req[1]]
    assert len(attr_posts) == 3
    assert len(canned_posts) >= 4
