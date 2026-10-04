"""Comprehensive test suite for Native Business Assistant Website-Builder Tool Pack (WP10).

Validates:
1. Inspection of tenant website state (initial unconfigured, live, and proposal history).
2. Draft edit proposals, version incrementing, payload hashing, and idempotency.
3. Optimistic version concurrency enforcement and rejection on conflict.
4. Content sanitisation: strict rejection of XSS scripts, unsafe HTML/iframe injections, customer PII, and unauthorized asset domains.
5. Preview generation: merging proposed changes onto current base website configuration and advancing status to 'preview'.
6. Separate publication gate:
   - Prohibition of automatic publication from conversational confirmation alone.
   - Rejection of publication by non-owner roles (403 Forbidden).
   - Rejection of publication without valid cryptographic confirmation token (expired, tampered, scope-mismatched).
   - Authoritative publication with valid owner token updating proposal status and live TenantWebsite.
7. Rollback behavior: restoring previous published version with optimistic concurrency and recording rollback_version.
8. WEBSITE_BUILDER_TOOLS execution via BusinessAssistantToolRegistry.
9. HTTP REST API endpoints mounted at /api/admin/business-assistant/website/*.

All tests use 100% real database models and live domain logic. Mocks are strictly prohibited.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.business_assistant import BusinessAssistantWebsiteProposal
from app.models.tenant import Tenant
from app.models.tenant_website import TenantWebsite
from app.models.user import User
from app.services.business_assistant import (
    WEBSITE_BUILDER_TOOLS,
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    ConfirmationSignatureError,
    WebsiteContentSafetyError,
    WebsiteVersionConflictError,
    generate_confirmation_token,
    verify_confirmation_token,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _tenant_and_users(db_session, suffix: str) -> tuple[Tenant, User, User]:
    """Helper to create a tenant with an owner and a staff/provider user."""
    tenant = Tenant(
        name=f"Website Builder Tenant {suffix}",
        subdomain=f"sitebuilder-{suffix}",
        timezone="Australia/Sydney",
        subscription_tier="growth",
    )
    db_session.add(tenant)
    db_session.flush()

    owner = User(
        tenant_id=tenant.id,
        login=f"owner-{suffix}",
        password_hash="test-hash",
        role="owner",
    )
    db_session.add(owner)

    staff = User(
        tenant_id=tenant.id,
        login=f"staff-{suffix}",
        password_hash="test-hash",
        role="manager",
    )
    db_session.add(staff)
    db_session.commit()

    return tenant, owner, staff


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


# ==============================================================================
# 1. State Inspection Tests
# ==============================================================================


def test_inspect_website_state_initial(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "init-state")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    state = service.inspect_website_state(include_history=True)

    assert state["tenant_id"] == tenant.id
    assert state["is_published"] is False
    assert state["published_at"] is None
    assert state["template_id"] == "minimalist"
    assert state["theme_id"] == "ocean_slate"
    assert state["has_pending_draft"] is False
    assert state["recent_proposals"] == []


def test_inspect_website_state_with_published_and_draft(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "pub-draft")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # 1. Propose and publish v1
    p1 = service.propose_website_edit(
        title="Initial website setup",
        content_payload={"template_id": "luxury", "theme_id": "emerald_oasis"},
    )
    _, token1 = service.request_website_publication(p1.id)
    service.publish_website_proposal(proposal_id=p1.id, confirmation_token=token1)

    # 2. Propose v2 draft
    p2 = service.propose_website_edit(
        title="Update hero section",
        content_payload={"sections_data": {"hero": {"headline": "New Wellness Era"}}},
    )

    state = service.inspect_website_state(include_history=True)

    assert state["is_published"] is True
    assert state["template_id"] == "luxury"
    assert state["theme_id"] == "emerald_oasis"
    assert state["has_pending_draft"] is True
    assert state["latest_proposal_id"] == p2.id
    assert state["latest_proposal_version"] == 2
    assert state["latest_proposal_status"] == "draft"
    assert state["published_proposal_id"] == p1.id
    assert state["published_proposal_version"] == 1
    assert len(state["recent_proposals"]) == 2


# ==============================================================================
# 2. Proposal Creation, Versioning, and Optimistic Concurrency Tests
# ==============================================================================


def test_propose_website_edit_lifecycle_and_idempotency(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "proposal-lifecycle")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # Create proposal with request_key
    req_key = "idemp-site-edit-001"
    proposal = service.propose_website_edit(
        title="Add autumn theme",
        content_payload={"theme_id": "rose_gold"},
        request_key=req_key,
    )

    assert proposal.id is not None
    assert proposal.tenant_id == tenant.id
    assert proposal.created_by_user_id == owner.id
    assert proposal.version == 1
    assert proposal.status == "draft"
    assert proposal.payload_hash is not None
    assert proposal.request_key == req_key

    # Re-submitting with identical payload returns existing proposal
    same_proposal = service.propose_website_edit(
        title="Add autumn theme",
        content_payload={"theme_id": "rose_gold"},
        request_key=req_key,
    )
    assert same_proposal.id == proposal.id

    # Creating next version auto-increments
    v2 = service.propose_website_edit(
        title="Second edit",
        content_payload={"theme_id": "royal_indigo"},
    )
    assert v2.version == 2


def test_optimistic_version_concurrency_conflict(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "opt-conflict")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # v1 exists
    service.propose_website_edit(
        title="First change",
        content_payload={"theme_id": "monochrome"},
    )

    # Attempt to propose expecting version 0 when current highest is 1
    with pytest.raises(WebsiteVersionConflictError) as exc_info:
        service.propose_website_edit(
            title="Conflicting change",
            content_payload={"theme_id": "rose_gold"},
            expected_version=0,
        )
    assert "Version conflict" in str(exc_info.value)
    assert "current website proposal version is 1, but expected 0" in str(exc_info.value)

    # Expecting version 1 succeeds
    v2 = service.propose_website_edit(
        title="Valid sequential change",
        content_payload={"theme_id": "rose_gold"},
        expected_version=1,
    )
    assert v2.version == 2


# ==============================================================================
# 3. Content Sanitisation & Tenant Scoping Tests
# ==============================================================================


def test_sanitisation_rejects_xss_scripts(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "san-xss")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # 1. Direct script tag
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Dangerous script",
            content_payload={"sections_data": {"hero": {"headline": "<script>alert('xss')</script>"}}},
        )
    assert "Unsafe script or HTML injection" in str(exc.value)

    # 2. Iframe injection
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Iframe exploit",
            content_payload={"sections_data": {"about": {"story": "<iframe src='http://evil.com'></iframe>"}}},
        )
    assert "Unsafe script or HTML injection" in str(exc.value)

    # 3. Inline event handler
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Event handler attack",
            content_payload={"sections_data": {"contact": {"headline": "<img src='x' onerror='alert(1)'>"}}},
        )
    assert "Unsafe script or HTML injection" in str(exc.value)

    # 4. javascript: protocol
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="JS link attack",
            content_payload={"sections_data": {"hero": {"cta_link": "javascript:stealCookies()"}}},
        )
    assert "Unsafe URL scheme" in str(exc.value) or "Unsafe script" in str(exc.value)


def test_sanitisation_rejects_customer_pii(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "san-pii")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # 1. PII token marker
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Customer leak",
            content_payload={"sections_data": {"testimonials": {"items": [{"name": "[NAME]", "content": "Good"}]}}},
        )
    assert "Customer PII or payment card data detected" in str(exc.value)

    # 2. Credit card number
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Card leak",
            content_payload={"sections_data": {"about": {"story": "Our founder card 4111111111111111 is on file."}}},
        )
    assert "Customer PII or payment card data detected" in str(exc.value)


def test_sanitisation_asset_domains(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "san-domains")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # Allowed asset: Unsplash
    v1 = service.propose_website_edit(
        title="Unsplash image",
        content_payload={
            "sections_data": {
                "hero": {
                    "bg_image_url": "https://images.unsplash.com/photo-1540555700478-4be289fbecef",
                }
            }
        },
    )
    assert v1.id is not None

    # Disallowed external asset domain
    with pytest.raises(WebsiteContentSafetyError) as exc:
        service.propose_website_edit(
            title="Unauthorized CDN",
            content_payload={
                "sections_data": {
                    "hero": {
                        "bg_image_url": "https://untrusted-hacker-cdn.ru/exploit.jpg",
                    }
                }
            },
        )
    assert "Unauthorized asset domain" in str(exc.value)


# ==============================================================================
# 4. Preview Generation Tests
# ==============================================================================


def test_preview_advances_status_and_renders_merge(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "preview-merge")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    proposal = service.propose_website_edit(
        title="Update headline only",
        content_payload={
            "template_id": "clinical",
            "sections_data": {
                "hero": {"headline": "Modern Clinical Treatments"},
            },
        },
    )
    assert proposal.status == "draft"

    updated_proposal, preview = service.preview_website_edit(proposal.id)

    assert updated_proposal.status == "preview"
    assert preview["template_id"] == "clinical"
    assert preview["theme_id"] == "ocean_slate"  # Kept from default
    assert preview["sections_data"]["hero"]["headline"] == "Modern Clinical Treatments"
    # Preserves other default hero fields (subhead, cta_text)
    assert "cta_text" in preview["sections_data"]["hero"]
    assert "about" in preview["sections_data"]


# ==============================================================================
# 5. Strict Publication Gate & Confirmation Token Tests
# ==============================================================================


def test_publication_gate_security(db_session):
    tenant, owner, staff = _tenant_and_users(db_session, "gate-sec")
    owner_service = BusinessAssistantService(db_session, tenant.id, owner.id)
    staff_service = BusinessAssistantService(db_session, tenant.id, staff.id)

    # Create proposal as staff
    proposal = staff_service.propose_website_edit(
        title="Staff proposed edit",
        content_payload={"theme_id": "emerald_oasis"},
    )

    # 1. Request publication generates token
    _, token = staff_service.request_website_publication(proposal.id)
    assert token is not None

    # 2. Staff user CANNOT publish (Forbidden)
    with pytest.raises(PermissionError) as exc:
        staff_service.publish_website_proposal(proposal_id=proposal.id, confirmation_token=token)
    assert "Only tenant owners may approve and publish website proposals" in str(exc.value)

    # 3. Cannot publish with tampered token
    tampered = token[:-4] + "abcd"
    with pytest.raises(ConfirmationSignatureError):
        owner_service.publish_website_proposal(proposal_id=proposal.id, confirmation_token=tampered)

    # 4. Cannot publish with scope-mismatched token
    other_tenant, other_owner, _ = _tenant_and_users(db_session, "other-scope")
    wrong_token = generate_confirmation_token(
        tenant_id=other_tenant.id,
        user_id=other_owner.id,
        action="publish_website",
        target_key=f"proposal_{proposal.id}",
        version=proposal.version,
        payload_hash=proposal.payload_hash or "",
    )
    with pytest.raises(ConfirmationScopeMismatchError):
        owner_service.publish_website_proposal(proposal_id=proposal.id, confirmation_token=wrong_token)

    # 5. Valid publication by owner succeeds
    published_p, live_site = owner_service.publish_website_proposal(
        proposal_id=proposal.id, confirmation_token=token
    )
    assert published_p.status == "published"
    assert published_p.published_at is not None
    assert published_p.published_by_user_id == owner.id
    assert live_site.is_published is True
    assert live_site.theme_id == "emerald_oasis"


# ==============================================================================
# 6. Rollback Mechanism Tests
# ==============================================================================


def test_rollback_to_previous_published_version(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "rollback")
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # Version 1: luxury / emerald_oasis
    p1 = service.propose_website_edit(
        title="V1 Luxury Theme",
        content_payload={"template_id": "luxury", "theme_id": "emerald_oasis"},
    )
    _, t1 = service.request_website_publication(p1.id)
    service.publish_website_proposal(proposal_id=p1.id, confirmation_token=t1)

    # Version 2: minimalist / rose_gold
    p2 = service.propose_website_edit(
        title="V2 Minimalist Theme",
        content_payload={"template_id": "minimalist", "theme_id": "rose_gold"},
    )
    _, t2 = service.request_website_publication(p2.id)
    service.publish_website_proposal(proposal_id=p2.id, confirmation_token=t2)

    # Current live site is v2
    current_site = service.inspect_website_state()
    assert current_site["template_id"] == "minimalist"
    assert current_site["theme_id"] == "rose_gold"

    # Rollback to v1 with optimistic concurrency check
    rollback_p = service.rollback_website_version(
        target_version=1,
        expected_current_version=2,
    )

    assert rollback_p.version == 3
    assert rollback_p.status == "published"
    assert rollback_p.rollback_version == 1

    # Live site is restored to v1 settings
    restored_site = service.inspect_website_state()
    assert restored_site["template_id"] == "luxury"
    assert restored_site["theme_id"] == "emerald_oasis"


# ==============================================================================
# 7. WEBSITE_BUILDER_TOOLS Execution in Tool Registry
# ==============================================================================


def test_website_builder_tool_pack_dispatch(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "tool-pack")
    adapters = BusinessAssistantReadAdapters(db_session, tenant.id, owner.id)
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    registry = BusinessAssistantToolRegistry(
        adapters,
        service=service,
        packs=("product_help", "website_builder"),
    )

    tool_names = {t["function"]["name"] for t in registry.schemas}
    assert "inspect_website_state" in tool_names
    assert "propose_website_edit" in tool_names
    assert "preview_website_edit" in tool_names
    assert "request_website_publication" in tool_names
    assert "rollback_website_version" in tool_names

    # 1. inspect_website_state
    inspect_res = registry.execute("inspect_website_state", {})
    assert inspect_res["status"] == "ok"
    assert inspect_res["website_state"]["is_published"] is False

    # 2. propose_website_edit
    propose_res = registry.execute(
        "propose_website_edit",
        {
            "title": "Tool pack proposed theme",
            "content_payload": {"theme_id": "royal_indigo"},
        },
    )
    assert propose_res["status"] == "ok"
    proposal_id = propose_res["proposal"]["id"]
    assert propose_res["proposal"]["status"] == "draft"

    # 3. preview_website_edit
    preview_res = registry.execute("preview_website_edit", {"proposal_id": proposal_id})
    assert preview_res["status"] == "ok"
    assert preview_res["proposal_status"] == "preview"
    assert preview_res["preview"]["theme_id"] == "royal_indigo"

    # 4. request_website_publication
    req_pub_res = registry.execute("request_website_publication", {"proposal_id": proposal_id})
    assert req_pub_res["status"] == "ok"
    assert "confirmation_token" in req_pub_res
    assert "Automatic publication from conversational confirmation alone is prohibited" in req_pub_res["instructions"]

    # 5. Rollback tool execution after publication
    service.publish_website_proposal(proposal_id=proposal_id, confirmation_token=req_pub_res["confirmation_token"])
    rollback_res = registry.execute(
        "rollback_website_version",
        {"target_version": 1},
    )
    assert rollback_res["status"] == "ok"
    assert rollback_res["rollback_proposal"]["rollback_version"] == 1


def test_tool_registry_pack_isolation(db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "pack-iso")
    adapters = BusinessAssistantReadAdapters(db_session, tenant.id, owner.id)
    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # Registry without website_builder pack
    registry = BusinessAssistantToolRegistry(
        adapters,
        service=service,
        packs=("product_help", "booking_availability"),
    )

    res = registry.execute("inspect_website_state", {})
    assert res["status"] == "rejected"
    assert "Tool 'inspect_website_state' is not available in the active tool packs." in res["reason"]


# ==============================================================================
# 8. HTTP REST API Endpoints Tests
# ==============================================================================


def test_http_api_website_state(client: TestClient, db_session):
    tenant, owner, _ = _tenant_and_users(db_session, "api-state")
    headers = _headers(tenant, owner)

    resp = client.get("/api/admin/business-assistant/website/state", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tenant.id
    assert data["is_published"] is False
    assert data["has_pending_draft"] is False


def test_http_api_propose_and_preview(client: TestClient, db_session):
    tenant, owner, staff = _tenant_and_users(db_session, "api-prop")
    headers = _headers(tenant, staff)

    # 1. Propose edit
    resp = client.post(
        "/api/admin/business-assistant/website/proposals",
        headers=headers,
        json={
            "title": "API Proposed Edit",
            "content_payload": {
                "template_id": "wellness",
                "sections_data": {"about": {"headline": "Our Wellness Sanctuary"}},
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    proposal_id = data["proposal"]["id"]
    assert data["proposal"]["status"] == "draft"
    assert data["proposal"]["version"] == 1

    # 2. Preview proposal
    resp_prev = client.get(
        f"/api/admin/business-assistant/website/proposals/{proposal_id}/preview",
        headers=headers,
    )
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert prev_data["proposal"]["status"] == "preview"
    assert prev_data["preview"]["template_id"] == "wellness"
    assert prev_data["preview"]["sections_data"]["about"]["headline"] == "Our Wellness Sanctuary"


def test_http_api_publication_gate_and_owner_authorization(client: TestClient, db_session):
    tenant, owner, staff = _tenant_and_users(db_session, "api-pubgate")
    owner_headers = _headers(tenant, owner)
    staff_headers = _headers(tenant, staff)

    # Propose
    service = BusinessAssistantService(db_session, tenant.id, staff.id)
    proposal = service.propose_website_edit(
        title="Ready to Publish",
        content_payload={"theme_id": "emerald_oasis"},
    )

    # 1. Staff requests publication token
    resp_token = client.post(
        f"/api/admin/business-assistant/website/proposals/{proposal.id}/request-publish",
        headers=staff_headers,
    )
    assert resp_token.status_code == 200
    token = resp_token.json()["confirmation_token"]

    # 2. Staff attempts to publish -> 403 Forbidden
    resp_staff_pub = client.post(
        f"/api/admin/business-assistant/website/proposals/{proposal.id}/publish",
        headers=staff_headers,
        json={"confirmation_token": token},
    )
    assert resp_staff_pub.status_code == 403

    # 3. Owner publishes with valid token -> 200 OK
    resp_owner_pub = client.post(
        f"/api/admin/business-assistant/website/proposals/{proposal.id}/publish",
        headers=owner_headers,
        json={"confirmation_token": token},
    )
    assert resp_owner_pub.status_code == 200
    pub_data = resp_owner_pub.json()
    assert pub_data["ok"] is True
    assert pub_data["proposal"]["status"] == "published"
    assert pub_data["is_published"] is True


def test_http_api_rollback(client: TestClient, db_session):
    tenant, owner, staff = _tenant_and_users(db_session, "api-rollback")
    owner_headers = _headers(tenant, owner)
    staff_headers = _headers(tenant, staff)

    service = BusinessAssistantService(db_session, tenant.id, owner.id)
    # v1
    p1 = service.propose_website_edit(
        title="Version 1", content_payload={"template_id": "luxury"}
    )
    _, t1 = service.request_website_publication(p1.id)
    service.publish_website_proposal(proposal_id=p1.id, confirmation_token=t1)

    # v2
    p2 = service.propose_website_edit(
        title="Version 2", content_payload={"template_id": "minimalist"}
    )
    _, t2 = service.request_website_publication(p2.id)
    service.publish_website_proposal(proposal_id=p2.id, confirmation_token=t2)

    # Staff rollback -> 403 Forbidden
    staff_resp = client.post(
        "/api/admin/business-assistant/website/rollback",
        headers=staff_headers,
        json={"target_version": 1},
    )
    assert staff_resp.status_code == 403

    # Owner rollback -> 200 OK
    owner_resp = client.post(
        "/api/admin/business-assistant/website/rollback",
        headers=owner_headers,
        json={"target_version": 1, "expected_current_version": 2},
    )
    assert owner_resp.status_code == 200
    data = owner_resp.json()
    assert data["ok"] is True
    assert data["proposal"]["rollback_version"] == 1
    assert data["proposal"]["version"] == 3
