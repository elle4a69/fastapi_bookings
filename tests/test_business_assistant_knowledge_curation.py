"""Comprehensive tests for Business Assistant Knowledge & Curator Workflow (WP4).

All tests execute against live database models and real domain engines.
Mocks are strictly prohibited.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.business_assistant import BusinessAssistantMemory
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import (
    BUSINESS_KNOWLEDGE_TOOLS,
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    DynamicFactRejectedError,
    generate_confirmation_token,
    verify_confirmation_token,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _tenant_and_user(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(
        name=f"Knowledge Tenant {suffix}",
        subdomain=f"knowledge-{suffix}",
        timezone="Australia/Sydney",
        subscription_tier="growth",
    )
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id,
        login=f"owner-{suffix}",
        password_hash="test-hash",
        role="owner",
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_draft_vs_activation_separation(db_session):
    """Drafting a rule stores it in 'draft' status without active effect until confirmed."""
    tenant, user = _tenant_and_user(db_session, "separation")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    memory, interpretation, token, hash_val = service.draft_business_rule(
        memory_key="pet_policy",
        content="Guide dogs and certified service animals are welcome in all consultation areas.",
        category="policy",
    )

    assert memory.status == "draft"
    assert memory.version == 1
    assert memory.activated_at is None
    assert memory.activated_by_user_id is None
    assert "Assistant interpretation" in interpretation
    assert token is not None
    assert hash_val == memory.payload_hash

    # Ensure CuratedMemory is not synced yet while in draft
    curated = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant.id, CuratedMemory.user_query == "pet_policy")
        .first()
    )
    assert curated is None

    # Now activate with valid token
    activated = service.activate_business_rule(
        id_or_key="pet_policy",
        confirmation_token=token,
    )

    assert activated.status == "active"
    assert activated.activated_at is not None
    assert activated.activated_by_user_id == user.id
    assert activated.provenance["activated_by_user_id"] == user.id

    # Active memory is now synced to CuratedMemory for system retrieval
    curated_synced = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant.id, CuratedMemory.user_query == "pet_policy")
        .first()
    )
    assert curated_synced is not None
    assert curated_synced.status == "active"
    assert curated_synced.authority == "owner_verified"
    assert curated_synced.ideal_response == activated.content


def test_confirmation_binding_rejects_tampered_payload_and_version(db_session):
    """Confirmation tokens cannot activate a draft whose content or version has changed."""
    tenant, user = _tenant_and_user(db_session, "binding")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    # 1. Draft version 1
    memory, _, token_v1, hash_v1 = service.draft_business_rule(
        memory_key="intake_policy",
        content="Clients must complete standard health questionnaires prior to consultation.",
        category="operations",
    )
    assert memory.version == 1

    # 2. Update draft to version 2 (changing content)
    memory_v2, _, token_v2, hash_v2 = service.draft_business_rule(
        memory_key="intake_policy",
        content="Clients must complete health questionnaires and provide primary contact details.",
        category="operations",
    )
    assert memory_v2.version == 2
    assert hash_v2 != hash_v1

    # 3. Old token for v1 fails when trying to activate v2
    with pytest.raises(ConfirmationPayloadMismatchError):
        service.activate_business_rule(
            id_or_key="intake_policy",
            confirmation_token=token_v1,
        )

    # 4. Token for v2 succeeds
    activated = service.activate_business_rule(
        id_or_key="intake_policy",
        confirmation_token=token_v2,
    )
    assert activated.status == "active"
    assert activated.version == 2


def test_confirmation_binding_rejects_expired_token(db_session):
    """Expired confirmation tokens fail closed."""
    tenant, user = _tenant_and_user(db_session, "expired")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    memory, _, _, hash_val = service.draft_business_rule(
        memory_key="aftercare_policy",
        content="Post-session guidance will be delivered in writing to the client.",
        category="policy",
    )

    # Generate an expired token (expires_in_seconds = -10)
    expired_token = generate_confirmation_token(
        tenant_id=tenant.id,
        user_id=user.id,
        action="activate_business_rule",
        target_key="aftercare_policy",
        version=memory.version,
        payload_hash=hash_val,
        expires_in_seconds=-10,
    )

    with pytest.raises(ConfirmationExpiredError):
        service.activate_business_rule(
            id_or_key="aftercare_policy",
            confirmation_token=expired_token,
        )


def test_cross_tenant_and_cross_user_isolation(db_session):
    """Tokens and rules from tenant A cannot be seen or activated by tenant B."""
    tenant_a, user_a = _tenant_and_user(db_session, "tenant-a")
    tenant_b, user_b = _tenant_and_user(db_session, "tenant-b")
    service_a = BusinessAssistantService(db_session, tenant_a.id, user_a.id)
    service_b = BusinessAssistantService(db_session, tenant_b.id, user_b.id)

    # Tenant A drafts a rule
    memory_a, _, token_a, _ = service_a.draft_business_rule(
        memory_key="shared_slug",
        content="Strict non-smoking policy inside all premises.",
        category="safety",
    )

    # Tenant B drafts a different rule with the same slug
    memory_b, _, token_b, _ = service_b.draft_business_rule(
        memory_key="shared_slug",
        content="Designated smoking zones are provided outside.",
        category="safety",
    )

    # Tenant B cannot activate Tenant A's rule using Tenant A's token
    with pytest.raises(ConfirmationScopeMismatchError):
        service_b.activate_business_rule(
            id_or_key="shared_slug",
            confirmation_token=token_a,
        )

    # Rules are isolated by tenant
    assert service_a.get_business_rule("shared_slug").content == "Strict non-smoking policy inside all premises."
    assert service_b.get_business_rule("shared_slug").content == "Designated smoking zones are provided outside."


def test_dynamic_facts_prohibition_rejects_operational_facts(db_session):
    """Dynamic operational facts (availability, pricing, dates, booking states) cannot be stored."""
    tenant, user = _tenant_and_user(db_session, "dynamic-reject")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    forbidden_examples = [
        ("pricing_fact", "Consultation fee is $150 per hour with a $50 deposit."),
        ("slots_fact", "Open slots are available tomorrow morning from 9am to 11am."),
        ("booking_fact", "Appointment is confirmed for customer [NAME] on 2026-10-15."),
        ("relative_time_fact", "The practitioner is currently booked out next week."),
        ("url_fact", "Pay the invoice at https://checkout.example.com/inv_12345"),
        ("customer_fact", "Customer phone is 0412345678 and email is test@example.com"),
    ]

    for key, text in forbidden_examples:
        with pytest.raises(DynamicFactRejectedError) as exc_info:
            service.draft_business_rule(
                memory_key=key,
                content=text,
                category="policy",
            )
        assert "Dynamic operational facts cannot be saved as static business knowledge" in str(exc_info.value)
        assert len(exc_info.value.detected_types) > 0


def test_curator_workflow_integration_and_automatic_resolution(db_session):
    """Drafting and activating a rule to answer a curator question automatically resolves it."""
    tenant, user = _tenant_and_user(db_session, "curator-flow")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    # Create a real pending KnowledgeProposal (curator question)
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        proposal_type="gap",
        status="pending",
        category="operations",
        user_query="Can clients bring companion animals?",
        proposed_response="Unknown clinic policy regarding companion animals.",
        fingerprint="fp-curator-test-1234",
        reason_code="knowledge_gap_detected",
        requires_review=True,
    )
    db_session.add(proposal)
    db_session.commit()

    # List curator questions via service
    questions = service.list_curator_questions(status="pending")
    assert any(q.id == proposal.id for q in questions)

    # Draft a business rule addressing the curator question
    memory, interpretation, token, _ = service.draft_business_rule(
        memory_key="companion_animal_policy",
        content="Registered therapy animals are permitted with 24 hours advance notification.",
        category="operations",
        curator_item_id=proposal.id,
    )
    assert memory.curator_item_id == proposal.id
    db_session.refresh(proposal)
    assert proposal.status == "pending"  # Still pending while in draft

    # Activate the rule
    service.activate_business_rule(
        id_or_key="companion_animal_policy",
        confirmation_token=token,
    )

    # Ensure proposal was automatically resolved with audit tracking
    db_session.refresh(proposal)
    assert proposal.status == "resolved"
    assert proposal.resolution_code == "business_rule_activated"
    assert proposal.reviewed_by_user_id == user.id
    assert proposal.reviewed_at is not None


def test_explicit_curator_question_resolution_without_rule(db_session):
    """Staff can explicitly dismiss or resolve a curator question without drafting a rule."""
    tenant, user = _tenant_and_user(db_session, "curator-dismiss")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        proposal_type="conflict",
        status="pending",
        category="general",
        user_query="Irrelevant or spam customer query?",
        proposed_response="No action required.",
        fingerprint="fp-curator-spam-9999",
        reason_code="spam_suspected",
        requires_review=True,
    )
    db_session.add(proposal)
    db_session.commit()

    resolved = service.resolve_curator_question(
        curator_item_id=proposal.id,
        resolution="dismissed",
        note="Out of scope query",
    )

    assert resolved.status == "dismissed"
    assert resolved.resolution_code == "dismissed:Out of scope query"
    assert resolved.reviewed_by_user_id == user.id


def test_business_knowledge_tool_pack_execution(db_session):
    """Verify tool execution through BusinessAssistantToolRegistry for all business knowledge tools."""
    tenant, user = _tenant_and_user(db_session, "tool-pack")
    adapters = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id)
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    registry = BusinessAssistantToolRegistry(
        adapters,
        service=service,
        packs=("business_knowledge",),
    )

    # Verify tool schemas
    tool_names = [t["function"]["name"] for t in registry.schemas]
    assert set(tool_names) == {
        "list_curator_questions",
        "draft_business_rule",
        "get_business_rule",
        "activate_business_rule",
        "resolve_curator_question",
    }

    # 1. Tool execution: list_curator_questions
    curator_res = registry.execute("list_curator_questions", {"status": "pending"})
    assert curator_res["status"] == "ok"
    assert isinstance(curator_res["questions"], list)

    # 2. Tool execution: draft_business_rule with dynamic fact should be rejected
    rejected_res = registry.execute(
        "draft_business_rule",
        {
            "memory_key": "bad_rule",
            "content": "Price is $200 and available slots are at 2pm tomorrow.",
        },
    )
    assert rejected_res["status"] == "rejected"
    assert "Dynamic operational facts cannot be saved" in rejected_res["reason"]

    # 3. Tool execution: draft valid business rule
    draft_res = registry.execute(
        "draft_business_rule",
        {
            "memory_key": "sanitation_protocol",
            "content": "All treatment tables and equipment are disinfected between each appointment.",
            "category": "clinical",
        },
    )
    assert draft_res["status"] == "ok"
    token = draft_res["confirmation_token"]
    assert "Assistant interpretation" in draft_res["interpretation"]

    # 4. Tool execution: get_business_rule
    get_res = registry.execute("get_business_rule", {"memory_key": "sanitation_protocol"})
    assert get_res["status"] == "ok"
    assert get_res["rule"]["status"] == "draft"

    # 5. Tool execution: activate_business_rule
    act_res = registry.execute(
        "activate_business_rule",
        {
            "memory_key": "sanitation_protocol",
            "confirmation_token": token,
        },
    )
    assert act_res["status"] == "ok"
    assert act_res["rule"]["status"] == "active"


def test_business_knowledge_http_api_lifecycle(client, db_session):
    """End-to-end HTTP API lifecycle: draft, list, get, and activate with confirmation."""
    tenant, user = _tenant_and_user(db_session, "api-lifecycle")
    headers = _headers(tenant, user)

    # 1. Draft a rule via POST /knowledge/rules/draft
    draft_payload = {
        "memory_key": "parking_guidelines",
        "content": "Dedicated accessible parking spaces are available at the front entrance.",
        "category": "facilities",
    }
    draft_resp = client.post(
        "/api/admin/business-assistant/knowledge/rules/draft",
        json=draft_payload,
        headers=headers,
    )
    assert draft_resp.status_code == 201, draft_resp.text
    draft_data = draft_resp.json()
    assert draft_data["rule"]["status"] == "draft"
    assert draft_data["rule"]["version"] == 1
    token = draft_data["confirmation_token"]

    # 2. Dynamic fact rejection via API returns 422
    bad_payload = {
        "memory_key": "invalid_dynamic",
        "content": "Slots are available today for $120.",
        "category": "pricing",
    }
    bad_resp = client.post(
        "/api/admin/business-assistant/knowledge/rules/draft",
        json=bad_payload,
        headers=headers,
    )
    assert bad_resp.status_code == 422
    assert "DYNAMIC_FACT_REJECTED" in bad_resp.text

    # 3. List rules via GET /knowledge/rules
    list_resp = client.get("/api/admin/business-assistant/knowledge/rules", headers=headers)
    assert list_resp.status_code == 200
    rules = list_resp.json()
    assert any(r["memory_key"] == "parking_guidelines" for r in rules)

    # 4. Get rule via GET /knowledge/rules/{id_or_key}
    get_resp = client.get("/api/admin/business-assistant/knowledge/rules/parking_guidelines", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "draft"

    # 5. Activate rule with invalid/tampered token returns 400
    bad_act_resp = client.post(
        "/api/admin/business-assistant/knowledge/rules/parking_guidelines/activate",
        json={"confirmation_token": "invalid.tampered_signature_12345"},
        headers=headers,
    )
    assert bad_act_resp.status_code == 400

    # 6. Activate rule with valid confirmation token returns 200
    act_resp = client.post(
        "/api/admin/business-assistant/knowledge/rules/parking_guidelines/activate",
        json={"confirmation_token": token},
        headers=headers,
    )
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["status"] == "active"
    assert act_data["activated_at"] is not None


def test_curator_questions_http_api(client, db_session):
    """End-to-end HTTP API for curator questions list and resolve."""
    tenant, user = _tenant_and_user(db_session, "api-curator")
    headers = _headers(tenant, user)

    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        proposal_type="gap",
        status="pending",
        category="billing",
        user_query="Do you accept third-party health insurance vouchers?",
        proposed_response="Unknown billing voucher policy.",
        fingerprint="fp-curator-http-5555",
        reason_code="knowledge_gap",
        requires_review=True,
    )
    db_session.add(proposal)
    db_session.commit()

    # List questions
    list_resp = client.get("/api/admin/business-assistant/knowledge/curator/questions", headers=headers)
    assert list_resp.status_code == 200
    questions = list_resp.json()
    assert any(q["id"] == proposal.id for q in questions)

    # Resolve question
    resolve_resp = client.post(
        f"/api/admin/business-assistant/knowledge/curator/questions/{proposal.id}/resolve",
        json={"resolution": "resolved", "note": "Addressed by staff"},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
