"""Comprehensive tests for Business Assistant Customer Operations & Messaging Proposals (WP5).

All tests execute against live database models and real domain engines.
Mocks are strictly prohibited.
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.core.state_machine import BookingStatus
from app.models.booking import Booking
from app.models.business_assistant import (
    BusinessAssistantCampaignProposal,
    BusinessAssistantMessageDraft,
)
from app.models.client import Client
from app.models.conversation import (
    ChannelAccount,
    ChannelType,
    Conversation,
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageSource,
)
from app.models.provider import Provider
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import (
    CUSTOMER_OPERATIONS_TOOLS,
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
    ConfirmationExpiredError,
    ConfirmationPayloadMismatchError,
    ConfirmationScopeMismatchError,
    generate_confirmation_token,
    verify_confirmation_token,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _tenant_and_staff(db_session, suffix: str) -> tuple[Tenant, User, Provider, User]:
    """Helper to set up a tenant with an owner and a linked provider user."""
    tenant = Tenant(
        name=f"Customer Ops Tenant {suffix}",
        subdomain=f"custops-{suffix}",
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
    db_session.flush()

    provider = Provider(
        tenant_id=tenant.id,
        name=f"Dr. Provider {suffix}",
        active=True,
    )
    db_session.add(provider)
    db_session.flush()

    provider_user = User(
        tenant_id=tenant.id,
        login=f"provider-{suffix}",
        password_hash="test-hash",
        role="provider",
        provider_id=provider.id,
    )
    db_session.add(provider_user)
    db_session.commit()

    return tenant, owner, provider, provider_user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def _seed_customer_conversation(
    db_session,
    tenant_id: int,
    provider_id: int | None,
    contact: str = "+61412345678",
    name: str = "Alice Customer",
    messages_count: int = 3,
) -> tuple[Conversation, Client]:
    """Seed a real conversation with client and messages."""
    client = Client(
        tenant_id=tenant_id,
        name=name,
        phone=contact,
        accepts_marketing=True,
        opted_out=False,
        sms_consent=True,
        active=True,
    )
    db_session.add(client)
    db_session.flush()

    account = ChannelAccount(
        tenant_id=tenant_id,
        channel_type=ChannelType.SMS,
        inbox_name="Main SMS Inbox",
        account_identifier="+61400000001",
    )
    db_session.add(account)
    db_session.flush()

    conv = Conversation(
        tenant_id=tenant_id,
        provider_id=provider_id,
        channel_account_id=account.id,
        contact_identifier=contact,
        contact_name=name,
        status="active",
        metadata_payload={"client_id": client.id},
    )
    db_session.add(conv)
    db_session.flush()

    for i in range(messages_count):
        msg = Message(
            conversation_id=conv.id,
            tenant_id=tenant_id,
            provider_id=provider_id,
            direction=MessageDirection.INBOUND if i % 2 == 0 else MessageDirection.OUTBOUND,
            source=MessageSource.CLIENT if i % 2 == 0 else MessageSource.ASSISTANT,
            content=f"Message {i + 1} content for {name}",
            delivery_status=DeliveryStatus.DELIVERED,
        )
        db_session.add(msg)
    db_session.commit()
    return conv, client


def test_customer_conversation_search_and_thread_isolation(db_session):
    """Tenant and provider isolation on customer conversation searches and thread reads."""
    tenant_a, owner_a, provider_a, provider_user_a = _tenant_and_staff(db_session, "isold1")
    tenant_b, owner_b, provider_b, provider_user_b = _tenant_and_staff(db_session, "isold2")

    conv_a1, client_a1 = _seed_customer_conversation(db_session, tenant_a.id, provider_a.id, "+61411111111", "Client A1")
    conv_a2, client_a2 = _seed_customer_conversation(db_session, tenant_a.id, None, "+61422222222", "Client A2")
    conv_b1, client_b1 = _seed_customer_conversation(db_session, tenant_b.id, provider_b.id, "+61433333333", "Client B1")

    # 1. Tenant A owner can see both A1 and A2, but NEVER B1
    service_a_owner = BusinessAssistantService(db_session, tenant_a.id, owner_a.id)
    search_owner = service_a_owner.search_customer_conversations()
    found_ids = {c["id"] for c in search_owner}
    assert conv_a1.id in found_ids
    assert conv_a2.id in found_ids
    assert conv_b1.id not in found_ids

    # 2. Provider A user can ONLY see conversations assigned to provider A
    service_a_prov = BusinessAssistantService(db_session, tenant_a.id, provider_user_a.id)
    search_prov = service_a_prov.search_customer_conversations()
    prov_ids = {c["id"] for c in search_prov}
    assert conv_a1.id in prov_ids
    assert conv_a2.id not in prov_ids  # conv_a2 has no provider assigned

    # 3. Thread read of own conversation succeeds with messages and opt-in status
    thread = service_a_prov.get_customer_conversation_thread(conv_a1.id)
    assert thread["conversation_id"] == conv_a1.id
    assert thread["contact_name"] == "Client A1"
    assert thread["opt_in_status"]["opted_out"] is False
    assert thread["opt_in_status"]["sms_consent"] is True
    assert len(thread["messages"]) == 3

    # 4. Provider A attempting to read another conversation raises LookupError
    with pytest.raises(LookupError):
        service_a_prov.get_customer_conversation_thread(conv_a2.id)

    # 5. Cross-tenant thread read raises LookupError
    with pytest.raises(LookupError):
        service_a_owner.get_customer_conversation_thread(conv_b1.id)


def test_opt_out_and_consent_filtering_in_audience_calculation(db_session):
    """Server-authoritative audience selection excludes opted-out, non-consenting, and inactive clients."""
    tenant, owner, provider, _ = _tenant_and_staff(db_session, "aud1")

    # 1. Eligible client (all consent given, active)
    c_eligible = Client(tenant_id=tenant.id, name="Eligible", phone="+61400000001", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    # 2. Opted out client
    c_opted_out = Client(tenant_id=tenant.id, name="Opted Out", phone="+61400000002", active=True, accepts_marketing=True, opted_out=True, sms_consent=True)
    # 3. Lacks SMS consent
    c_no_sms = Client(tenant_id=tenant.id, name="No SMS", phone="+61400000003", active=True, accepts_marketing=True, opted_out=False, sms_consent=False)
    # 4. Marketing not accepted
    c_no_marketing = Client(tenant_id=tenant.id, name="No Marketing", phone="+61400000004", active=True, accepts_marketing=False, opted_out=False, sms_consent=True)
    # 5. Inactive client
    c_inactive = Client(tenant_id=tenant.id, name="Inactive", phone="+61400000005", active=False, accepts_marketing=True, opted_out=False, sms_consent=True)
    # 6. Deleted client
    c_deleted = Client(tenant_id=tenant.id, name="Deleted", phone="+61400000006", active=True, accepts_marketing=True, deleted_at=datetime.now(timezone.utc))

    db_session.add_all([c_eligible, c_opted_out, c_no_sms, c_no_marketing, c_inactive, c_deleted])
    db_session.commit()

    service = BusinessAssistantService(db_session, tenant.id, owner.id)
    preview = service.preview_campaign_audience(
        marketing_opt_in_only=True,
        active_only=True,
    )

    # Only c_eligible should qualify
    assert preview["recipient_count"] == 1
    assert preview["summary"]["total_clients"] == 5  # c_deleted is excluded from tenant active set
    assert preview["summary"]["eligible_count"] == 1
    assert preview["summary"]["excluded_opt_out"] == 2  # c_opted_out and c_no_sms
    assert preview["summary"]["excluded_marketing_unconsented"] == 1  # c_no_marketing
    assert preview["summary"]["excluded_inactive"] == 1  # c_inactive


def test_booking_holds_and_completed_booking_criteria_filtering(db_session):
    """Audience calculation respects exclude_pending_holds and min_completed_bookings."""
    tenant, owner, provider, _ = _tenant_and_staff(db_session, "aud2")

    service_obj = Service(tenant_id=tenant.id, name="Consultation", duration=30, active=True)
    db_session.add(service_obj)
    db_session.flush()

    c1 = Client(tenant_id=tenant.id, name="Client With Hold", phone="+61400000010", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    c2 = Client(tenant_id=tenant.id, name="Client Completed", phone="+61400000020", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    c3 = Client(tenant_id=tenant.id, name="Client No Bookings", phone="+61400000030", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    db_session.add_all([c1, c2, c3])
    db_session.flush()

    # c1 has a PENDING booking hold
    now = datetime.now(timezone.utc)
    b_pending = Booking(
        tenant_id=tenant.id,
        client_id=c1.id,
        provider_id=provider.id,
        service_id=service_obj.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, minutes=30),
        status=BookingStatus.PENDING,
    )
    # c2 has a COMPLETED booking
    b_completed = Booking(
        tenant_id=tenant.id,
        client_id=c2.id,
        provider_id=provider.id,
        service_id=service_obj.id,
        start_time=now - timedelta(days=5),
        end_time=now - timedelta(days=5, minutes=-30),
        status=BookingStatus.COMPLETED,
    )
    db_session.add_all([b_pending, b_completed])
    db_session.commit()

    service = BusinessAssistantService(db_session, tenant.id, owner.id)

    # 1. With exclude_pending_holds=True and min_completed_bookings=1
    preview = service.preview_campaign_audience(
        exclude_pending_holds=True,
        min_completed_bookings=1,
    )
    # Only c2 should qualify (c1 has hold, c3 has no completed bookings)
    assert preview["recipient_count"] == 1
    assert preview["sample_recipients"][0]["client_id"] == c2.id
    assert preview["summary"]["excluded_pending_holds"] == 1
    assert preview["summary"]["excluded_booking_criteria"] == 1  # c3 excluded due to 0 bookings


def test_prepare_message_draft_without_sending(db_session):
    """Preparing a draft persists it, issues confirmation token, and strictly prevents live sending."""
    tenant, owner, provider, _ = _tenant_and_staff(db_session, "draft1")
    conv, client = _seed_customer_conversation(db_session, tenant.id, provider.id, "+61412345678", "Bob Draft")

    service = BusinessAssistantService(db_session, tenant.id, owner.id)
    content = "Hello Bob, here is the information you requested about our opening hours."

    draft, token, preview = service.prepare_customer_message_draft(
        conversation_id=conv.id,
        content=content,
        request_key="req-draft-001",
    )

    assert draft.id is not None
    assert draft.status == "draft"
    assert draft.version == 1
    assert draft.conversation_id == conv.id
    assert draft.content == content
    assert "+614***" in draft.recipient_preview
    assert preview["live_send_dispatched"] is False
    assert preview["live_send_disabled"] is True
    assert token is not None

    # Verify confirmation token validity
    verify_confirmation_token(
        token=token,
        expected_tenant_id=tenant.id,
        expected_user_id=owner.id,
        expected_action="approve_customer_message_draft",
        expected_target_key=str(draft.id),
        expected_version=1,
        expected_payload_hash=draft.payload_hash,
    )

    # Idempotent re-run with same request_key returns existing draft
    draft2, token2, preview2 = service.prepare_customer_message_draft(
        conversation_id=conv.id,
        content=content,
        request_key="req-draft-001",
    )
    assert draft2.id == draft.id


def test_create_and_approve_campaign_proposal(db_session):
    """Campaign proposal stores snapshot, requires confirmed approval token, and keeps live send disabled."""
    tenant, owner, provider, _ = _tenant_and_staff(db_session, "camp1")

    # Add 2 eligible clients
    c1 = Client(tenant_id=tenant.id, name="Client One", phone="+61400000001", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    c2 = Client(tenant_id=tenant.id, name="Client Two", phone="+61400000002", active=True, accepts_marketing=True, opted_out=False, sms_consent=True)
    db_session.add_all([c1, c2])
    db_session.commit()

    service = BusinessAssistantService(db_session, tenant.id, owner.id)
    proposal, token, summary = service.create_campaign_proposal(
        title="Spring Re-engagement Campaign",
        content="Spring is here! Enjoy 10% off your next appointment.",
        marketing_opt_in_only=True,
        active_only=True,
        request_key="req-camp-001",
    )

    assert proposal.id is not None
    assert proposal.status == "proposed"
    assert proposal.recipient_count == 2
    assert proposal.version == 1
    assert summary["eligible_count"] == 2
    assert token is not None

    # Idempotent re-run
    p_dup, t_dup, _ = service.create_campaign_proposal(
        title="Spring Re-engagement Campaign",
        content="Spring is here! Enjoy 10% off your next appointment.",
        request_key="req-camp-001",
    )
    assert p_dup.id == proposal.id

    # Approve with valid token
    approved = service.approve_campaign_proposal(
        proposal_id=proposal.id,
        confirmation_token=token,
    )
    assert approved.status == "approved"

    # Approval with tampered token is rejected
    with pytest.raises(Exception):
        service.approve_campaign_proposal(
            proposal_id=proposal.id,
            confirmation_token="invalid.tampered.token",
        )


def test_customer_operations_tool_pack_execution(db_session):
    """Customer Operations tools execute accurately via BusinessAssistantToolRegistry."""
    tenant, owner, provider, _ = _tenant_and_staff(db_session, "tools1")
    conv, client = _seed_customer_conversation(db_session, tenant.id, provider.id, "+61412345678", "Tool User")

    adapters = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=owner.id)
    registry = BusinessAssistantToolRegistry(
        adapters,
        packs=("customer_operations",),
    )

    tool_names = {t["function"]["name"] for t in registry.schemas}
    assert "search_customer_conversations" in tool_names
    assert "get_customer_conversation_thread" in tool_names
    assert "prepare_customer_message_draft" in tool_names
    assert "create_campaign_proposal" in tool_names

    # 1. Execute search_customer_conversations
    res_search = registry.execute("search_customer_conversations", {"query": "Tool User"})
    assert res_search["status"] == "ok"
    assert len(res_search["conversations"]) >= 1

    # 2. Execute get_customer_conversation_thread
    res_thread = registry.execute("get_customer_conversation_thread", {"conversation_id": conv.id})
    assert res_thread["status"] == "ok"
    assert res_thread["thread"]["conversation_id"] == conv.id
    assert len(res_thread["thread"]["messages"]) == 3

    # 3. Execute prepare_customer_message_draft
    res_draft = registry.execute(
        "prepare_customer_message_draft",
        {"conversation_id": conv.id, "content": "Thank you for reaching out!"},
    )
    assert res_draft["status"] == "ok"
    assert res_draft["draft"]["status"] == "draft"
    assert res_draft["preview"]["live_send_dispatched"] is False

    # 4. Execute create_campaign_proposal
    res_camp = registry.execute(
        "create_campaign_proposal",
        {
            "title": "Welcome Special",
            "content": "Welcome to our clinic! Use code WELCOME for a discount.",
            "marketing_opt_in_only": True,
        },
    )
    assert res_camp["status"] == "ok"
    assert res_camp["proposal"]["status"] == "proposed"
    assert "confirmation_token" in res_camp

    # 5. Tool not in active pack is rejected
    res_unavail = registry.execute("draft_business_rule", {"memory_key": "x", "content": "y"})
    assert res_unavail["status"] == "rejected"


def test_customer_operations_http_api(client: TestClient, db_session):
    """Test full HTTP REST API endpoints for customer operations."""
    tenant, owner, provider, provider_user = _tenant_and_staff(db_session, "api1")
    conv, cust = _seed_customer_conversation(db_session, tenant.id, provider.id, "+61412345678", "API Client")

    owner_hdrs = _headers(tenant, owner)
    prov_hdrs = _headers(tenant, provider_user)

    # 1. GET /api/admin/business-assistant/customer/conversations
    resp = client.get("/api/admin/business-assistant/customer/conversations", headers=owner_hdrs)
    assert resp.status_code == 200
    conv_list = resp.json()
    assert len(conv_list) >= 1
    assert conv_list[0]["id"] == conv.id

    # 2. GET /api/admin/business-assistant/customer/conversations/{id}
    resp = client.get(f"/api/admin/business-assistant/customer/conversations/{conv.id}", headers=owner_hdrs)
    assert resp.status_code == 200
    thread_data = resp.json()
    assert thread_data["conversation_id"] == conv.id
    assert len(thread_data["messages"]) == 3

    # 3. POST /api/admin/business-assistant/customer/conversations/{id}/draft
    resp = client.post(
        f"/api/admin/business-assistant/customer/conversations/{conv.id}/draft",
        headers=owner_hdrs,
        json={"content": "Drafted reply via HTTP endpoint."},
    )
    assert resp.status_code == 200
    draft_resp = resp.json()
    assert draft_resp["draft"]["status"] == "draft"
    assert draft_resp["preview"]["live_send_dispatched"] is False
    draft_id = draft_resp["draft"]["id"]

    # 4. GET /api/admin/business-assistant/customer/drafts
    resp = client.get("/api/admin/business-assistant/customer/drafts", headers=owner_hdrs)
    assert resp.status_code == 200
    assert any(d["id"] == draft_id for d in resp.json())

    # 5. GET /api/admin/business-assistant/customer/drafts/{id}
    resp = client.get(f"/api/admin/business-assistant/customer/drafts/{draft_id}", headers=owner_hdrs)
    assert resp.status_code == 200
    assert resp.json()["id"] == draft_id

    # 6. POST /api/admin/business-assistant/campaigns/audience-preview
    resp = client.post(
        "/api/admin/business-assistant/campaigns/audience-preview",
        headers=owner_hdrs,
        json={"marketing_opt_in_only": True, "active_only": True},
    )
    assert resp.status_code == 200
    aud_prev = resp.json()
    assert "recipient_count" in aud_prev
    assert "summary" in aud_prev

    # 7. POST /api/admin/business-assistant/campaigns/proposals
    resp = client.post(
        "/api/admin/business-assistant/campaigns/proposals",
        headers=owner_hdrs,
        json={
            "title": "VIP Spring Promo",
            "content": "Exclusive offer for VIP customers.",
            "marketing_opt_in_only": True,
        },
    )
    assert resp.status_code == 200
    prop_resp = resp.json()
    prop_id = prop_resp["proposal"]["id"]
    token = prop_resp["confirmation_token"]
    assert prop_resp["proposal"]["status"] == "proposed"

    # 8. GET /api/admin/business-assistant/campaigns/proposals
    resp = client.get("/api/admin/business-assistant/campaigns/proposals", headers=owner_hdrs)
    assert resp.status_code == 200
    assert any(p["id"] == prop_id for p in resp.json())

    # 9. GET /api/admin/business-assistant/campaigns/proposals/{id}
    resp = client.get(f"/api/admin/business-assistant/campaigns/proposals/{prop_id}", headers=owner_hdrs)
    assert resp.status_code == 200
    assert resp.json()["id"] == prop_id

    # 10. POST /api/admin/business-assistant/campaigns/proposals/{id}/approve
    resp = client.post(
        f"/api/admin/business-assistant/campaigns/proposals/{prop_id}/approve",
        headers=owner_hdrs,
        json={"confirmation_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_customer_operations_migration_upgrade_and_downgrade():
    """Verify that migration u5v6w7x8y9z0 upgrades and downgrades cleanly on a test database."""
    import importlib.util
    from pathlib import Path
    from alembic import op
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect
    from app.db.database import Base
    import app.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    # Create base schema
    Base.metadata.create_all(connection)

    migration_path = Path("alembic/versions") / "u5v6w7x8y9z0_add_business_assistant_customer_operations.py"
    spec = importlib.util.spec_from_file_location("customer_ops_migration_test", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        # Upgrade (idempotent with existing Base.metadata tables)
        module.upgrade()
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        assert "business_assistant_campaign_proposals" in tables
        assert "business_assistant_message_drafts" in tables

        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        assert "opted_out" in client_cols
        assert "sms_consent" in client_cols

        # Test downgrade
        module.downgrade()
        inspector_post = inspect(connection)
        tables_post = set(inspector_post.get_table_names())
        assert "business_assistant_campaign_proposals" not in tables_post
        assert "business_assistant_message_drafts" not in tables_post

        # Re-upgrade to ensure clean replay
        module.upgrade()
        inspector_replay = inspect(connection)
        assert "business_assistant_campaign_proposals" in set(inspector_replay.get_table_names())
    finally:
        del op._proxy
        connection.close()
        engine.dispose()

