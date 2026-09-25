"""Automated tests for Website Builder Module.

Verifies:
- Default starter website retrieval and initialization
- Draft configuration updates (template, theme, custom colors, sections, SEO)
- Publish and unpublish toggle behavior
- AI content and copy generation
- Public website endpoint behavior (unpublished 404, preview mode, published 200)
"""

from datetime import datetime, timezone
import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.tenant_website import TenantWebsite
from app.models.user import User


@pytest.fixture
def website_test_env(db_session):
    """Creates a test tenant and admin user with auth headers."""
    tenant = Tenant(
        name="Serenity Wellness Spa",
        subdomain="serenity-spa",
        email="info@serenityspa.com",
        phone="+1 555-987-6543",
        address="789 Blossom Avenue, Suite 10",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login="admin_user",
        password_hash="fake_hash",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }
    return {
        "tenant": tenant,
        "user": user,
        "headers": headers,
    }


def test_get_admin_website_creates_default_starter(client, website_test_env):
    """GET /api/admin/website should create and return default starter content if empty."""
    headers = website_test_env["headers"]
    response = client.get("/api/admin/website", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["template_id"] == "minimalist"
    assert data["theme_id"] == "ocean_slate"
    assert data["is_published"] is False
    assert "hero" in data["sections_data"]
    assert "Serenity Wellness Spa" in data["sections_data"]["hero"]["headline"]
    assert data["sections_data"]["contact"]["address"] == "789 Blossom Avenue, Suite 10"


def test_update_admin_website_draft(client, website_test_env):
    """PUT /api/admin/website should persist draft modifications."""
    headers = website_test_env["headers"]

    # First initialize
    client.get("/api/admin/website", headers=headers)

    update_payload = {
        "template_id": "wellness",
        "theme_id": "emerald_oasis",
        "custom_colors": {"primary": "#10B981", "secondary": "#064E3B"},
        "seo_title": "Serenity Wellness Spa - Organic Treatments",
        "seo_description": "Award-winning organic treatments and massages in Suite 10.",
        "sections_data": {
            "hero": {
                "headline": "Reclaim Your Inner Harmony",
                "subhead": "Deep tissue, aromatherapy, and mindfulness sessions.",
                "cta_text": "Book Session Now",
                "enabled": True,
            }
        },
    }

    put_resp = client.put("/api/admin/website", json=update_payload, headers=headers)
    assert put_resp.status_code == status.HTTP_200_OK
    data = put_resp.json()["data"]
    assert data["template_id"] == "wellness"
    assert data["theme_id"] == "emerald_oasis"
    assert data["custom_colors"]["primary"] == "#10B981"
    assert data["seo_title"] == "Serenity Wellness Spa - Organic Treatments"
    assert data["sections_data"]["hero"]["headline"] == "Reclaim Your Inner Harmony"


def test_publish_and_unpublish_website(client, website_test_env):
    """POST /api/admin/website/publish toggles live publication status."""
    headers = website_test_env["headers"]

    # Publish
    pub_resp = client.post("/api/admin/website/publish", json={"is_published": True}, headers=headers)
    assert pub_resp.status_code == status.HTTP_200_OK
    pub_data = pub_resp.json()["data"]
    assert pub_data["is_published"] is True
    assert pub_data["published_at"] is not None

    # Verify via get
    get_resp = client.get("/api/admin/website", headers=headers)
    assert get_resp.json()["data"]["is_published"] is True

    # Unpublish
    unpub_resp = client.post("/api/admin/website/publish", json={"is_published": False}, headers=headers)
    assert unpub_resp.status_code == status.HTTP_200_OK
    unpub_data = unpub_resp.json()["data"]
    assert unpub_data["is_published"] is False
    assert unpub_data["published_at"] is None


def test_ai_generate_endpoint(client, website_test_env):
    """POST /api/admin/website/ai-generate generates intelligent suggestions and copy."""
    headers = website_test_env["headers"]

    # 1. Full generation for wellness spa
    payload_wellness = {
        "prompt": "We are a serene luxury massage and wellness spa offering holistic rejuvenation",
        "action": "generate_full",
    }
    resp1 = client.post("/api/admin/website/ai-generate", json=payload_wellness, headers=headers)
    assert resp1.status_code == status.HTTP_200_OK
    data1 = resp1.json()
    assert data1["ok"] is True
    assert data1["suggested_template"] in ["wellness", "luxury"]
    assert data1["suggested_theme"] in ["emerald_oasis", "rose_gold"]
    assert "hero" in data1["generated_sections"]
    assert len(data1["generated_sections"]["testimonials"]["items"]) > 0

    # 2. Section rewrite
    payload_rewrite = {
        "prompt": "Rewrite about section for our clinic",
        "action": "rewrite_section",
        "section_key": "about",
    }
    resp2 = client.post("/api/admin/website/ai-generate", json=payload_rewrite, headers=headers)
    assert resp2.status_code == status.HTTP_200_OK
    data2 = resp2.json()
    assert data2["rewritten_text"] is not None
    assert len(data2["rewritten_text"]) > 10

    # 3. Suggest theme
    payload_theme = {
        "prompt": "A modern medical clinic with board-certified physicians",
        "action": "suggest_theme",
    }
    resp3 = client.post("/api/admin/website/ai-generate", json=payload_theme, headers=headers)
    assert resp3.status_code == status.HTTP_200_OK
    assert resp3.json()["suggested_template"] == "clinical"
    assert resp3.json()["suggested_theme"] == "royal_indigo"


def test_public_website_endpoint(client, website_test_env):
    """GET /api/public/website enforces published status while supporting preview mode."""
    tenant = website_test_env["tenant"]
    admin_headers = website_test_env["headers"]
    public_headers = {"X-Tenant": tenant.subdomain}

    # Unpublished site without preview -> 404
    resp_404 = client.get("/api/public/website", headers=public_headers)
    assert resp_404.status_code == status.HTTP_404_NOT_FOUND

    # Unpublished site with preview=true -> 200
    resp_preview = client.get("/api/public/website?preview=true", headers=public_headers)
    assert resp_preview.status_code == status.HTTP_200_OK
    data_preview = resp_preview.json()["data"]
    assert data_preview["tenant_name"] == tenant.name
    assert data_preview["config"]["is_published"] is False

    # Publish site via admin
    client.post("/api/admin/website/publish", json={"is_published": True}, headers=admin_headers)

    # Published site -> 200
    resp_live = client.get("/api/public/website", headers=public_headers)
    assert resp_live.status_code == status.HTTP_200_OK
    data_live = resp_live.json()["data"]
    assert data_live["tenant_name"] == tenant.name
    assert data_live["config"]["is_published"] is True


def test_chat_widget_configuration_and_defaults(client, website_test_env):
    """Verifies default chat_widget configuration and updates via admin builder."""
    headers = website_test_env["headers"]

    # Initial get creates default starter config
    resp = client.get("/api/admin/website", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    sections = resp.json()["data"]["sections_data"]
    assert "chat_widget" in sections
    widget_conf = sections["chat_widget"]
    assert widget_conf["enabled"] is True
    assert "booking" in widget_conf["invitation_title"].lower()
    assert widget_conf["invitation_delay_seconds"] == 3
    assert widget_conf["show_sms_fallback"] is True

    # Update chat widget settings
    update_payload = {
        "sections_data": {
            **sections,
            "chat_widget": {
                "enabled": True,
                "invitation_title": "Have questions about our treatments?",
                "invitation_message": "Our spa specialists are here to assist you live!",
                "invitation_delay_seconds": 5,
                "show_sms_fallback": False,
            },
        },
    }
    put_resp = client.put("/api/admin/website", json=update_payload, headers=headers)
    assert put_resp.status_code == status.HTTP_200_OK
    updated_widget = put_resp.json()["data"]["sections_data"]["chat_widget"]
    assert updated_widget["invitation_title"] == "Have questions about our treatments?"
    assert updated_widget["invitation_delay_seconds"] == 5
    assert updated_widget["show_sms_fallback"] is False


def test_public_website_chat_endpoint(client, website_test_env, db_session):
    """POST /api/public/website/chat creates conversation with source 'web_chat' and returns assistant reply."""
    from app.models.sms_conversation import SmsConversation
    from app.models.service import Service

    tenant = website_test_env["tenant"]
    public_headers = {"X-Tenant": tenant.subdomain}

    # Add an active service for the tenant
    service = Service(
        tenant_id=tenant.id,
        name="Aromatherapy Massage",
        duration=60,
        price=120.0,
        active=True,
    )
    db_session.add(service)
    db_session.commit()

    # 1. Ask about opening hours
    chat_payload_1 = {
        "visitor_name": "Sarah Connor",
        "visitor_contact": "+15552349999",
        "message": "What are your opening hours?",
    }
    resp1 = client.post("/api/public/website/chat", json=chat_payload_1, headers=public_headers)
    assert resp1.status_code == status.HTTP_200_OK
    data1 = resp1.json()
    assert data1["ok"] is True
    assert data1["conversation_id"] > 0
    assert len(data1["reply"]) > 0
    assert any("hour" in data1["reply"].lower() or "open" in data1["reply"].lower() for _ in [1])
    assert len(data1["messages"]) >= 2  # Inbound visitor msg + Outbound AI reply

    conv_id = data1["conversation_id"]

    # Verify conversation in database has source 'web_chat'
    conv = db_session.query(SmsConversation).filter(SmsConversation.id == conv_id).first()
    assert conv is not None
    assert conv.source == "web_chat"
    assert conv.customer_address == "+15552349999"

    # 2. Continue conversation: ask about pricing/services
    chat_payload_2 = {
        "conversation_id": conv_id,
        "visitor_name": "Sarah Connor",
        "message": "What are your prices and services?",
    }
    resp2 = client.post("/api/public/website/chat", json=chat_payload_2, headers=public_headers)
    assert resp2.status_code == status.HTTP_200_OK
    data2 = resp2.json()
    assert data2["conversation_id"] == conv_id
    assert "Aromatherapy Massage" in data2["reply"] or "services" in data2["reply"].lower()
    assert len(data2["messages"]) >= 4

    # 3. Retrieve chat history via GET /api/public/website/chat/{conversation_id}
    get_resp = client.get(f"/api/public/website/chat/{conv_id}", headers=public_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    assert len(get_resp.json()["messages"]) >= 4

    # 4. Also test passing tenant_id directly in body without X-Tenant header
    direct_payload = {
        "tenant_id": tenant.id,
        "visitor_name": "John Doe",
        "visitor_contact": "john@example.com",
        "message": "Hi, I have a quick question about bookings",
    }
    resp3 = client.post("/api/public/website/chat", json=direct_payload)
    assert resp3.status_code == status.HTTP_200_OK
    assert resp3.json()["ok"] is True
    assert resp3.json()["conversation_id"] > 0

