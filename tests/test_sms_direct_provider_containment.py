import asyncio

import pytest
from fastapi import HTTPException, status

from app.api.routers import sms_webhooks as sms_webhooks_router
from app.core.security import create_access_token
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.models.sms_receipt import SmsDeliveryReceipt, SmsInboundReceipt
from app.models.tenant import Tenant
from app.models.user import User
from app.services.sms import chatwoot_service, inbound_service, outbox_worker
from app.services.sms.transports import get_transport_adapter


DISABLED_DETAIL = "Direct MobileMessage integration is disabled."
LOCAL_SEND_DETAIL = "Local messaging controls are disabled; use Chatwoot."
TERMINAL_REASON = "transport_disabled"


def assert_api_error(response, expected_status: int, expected_message: str) -> None:
    assert response.status_code == expected_status
    assert response.json()["error"]["message"] == expected_message


@pytest.fixture
def containment_data(db_session):
    tenant = Tenant(name="Containment Test Tenant", subdomain="containment-test")
    db_session.add(tenant)
    db_session.flush()

    admin = User(
        tenant_id=tenant.id,
        login="admin@containment.invalid",
        password_hash="synthetic-hash",
        role="admin",
    )
    provider = Provider(
        tenant_id=tenant.id,
        name="Synthetic Containment Provider",
        active=True,
    )
    db_session.add_all([admin, provider])
    db_session.flush()

    mobile_account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="mobilemessage",
        display_name="Historical Direct Line",
        sender_address="61400000991",
        is_enabled=True,
        autoresponder_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot",
    )
    mobile_account.credentials = {"api_key": "synthetic-never-valid"}

    simulator_account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Synthetic Simulator Line",
        sender_address="61400000992",
        is_enabled=True,
    )
    db_session.add_all([mobile_account, simulator_account])
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "mobile_account": mobile_account,
        "simulator_account": simulator_account,
        "headers": {
            "X-Tenant": tenant.subdomain,
            "X-Token": create_access_token({"sub": str(admin.id)}),
        },
    }


def test_account_api_rejects_new_mobilemessage_but_keeps_simulator_available(
    client, db_session, containment_data
):
    provider = containment_data["provider"]
    headers = containment_data["headers"]
    account_count = db_session.query(SmsAccount).count()

    response = client.post(
        "/api/admin/sms/accounts",
        headers=headers,
        json={
            "provider_id": provider.id,
            "transport_type": "MobileMessage",
            "display_name": "Must Not Persist",
            "sender_address": "+61400000993",
            "credentials": {"api_key": "synthetic-must-not-persist"},
        },
    )

    assert_api_error(response, status.HTTP_409_CONFLICT, DISABLED_DETAIL)
    assert db_session.query(SmsAccount).count() == account_count
    assert (
        db_session.query(SmsAccount)
        .filter(SmsAccount.display_name == "Must Not Persist")
        .first()
        is None
    )

    simulator_response = client.post(
        "/api/admin/sms/accounts",
        headers=headers,
        json={
            "provider_id": provider.id,
            "transport_type": "simulator",
            "display_name": "Additional Synthetic Simulator",
            "sender_address": "+61400000994",
            "is_enabled": True,
        },
    )
    assert simulator_response.status_code == status.HTTP_201_CREATED
    assert simulator_response.json()["transport_type"] == "simulator"


def test_admin_containment_controls_preserve_the_authentication_boundary(
    client, db_session, containment_data
):
    tenant_header_only = {"X-Tenant": containment_data["tenant"].subdomain}
    account_count = db_session.query(SmsAccount).count()

    account_response = client.post(
        "/api/admin/sms/accounts",
        headers=tenant_header_only,
        json={
            "provider_id": containment_data["provider"].id,
            "transport_type": "mobilemessage",
            "display_name": "Unauthenticated Attempt",
            "sender_address": "+61400000998",
        },
    )
    control_response = client.post(
        "/api/admin/sms/conversations/jobs/1/retry",
        headers=tenant_header_only,
    )

    assert account_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert control_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert db_session.query(SmsAccount).count() == account_count


def test_historical_mobilemessage_account_is_readable_and_only_explicitly_disableable(
    client, db_session, containment_data
):
    account = containment_data["mobile_account"]
    headers = containment_data["headers"]
    original_credentials = dict(account._credentials)
    original_name = account.display_name

    list_response = client.get("/api/admin/sms/accounts", headers=headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert any(row["id"] == account.id for row in list_response.json())

    get_response = client.get(f"/api/admin/sms/accounts/{account.id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK

    disable_response = client.put(
        f"/api/admin/sms/accounts/{account.id}",
        headers=headers,
        json={"is_enabled": False},
    )
    assert disable_response.status_code == status.HTTP_200_OK
    assert disable_response.json()["is_enabled"] is False

    for update in (
        {"is_enabled": True},
        {"credentials": {"api_key": "synthetic-replacement"}},
        {"display_name": "Forbidden Historical Rewrite"},
    ):
        response = client.put(
            f"/api/admin/sms/accounts/{account.id}",
            headers=headers,
            json=update,
        )
        assert_api_error(response, status.HTTP_409_CONFLICT, DISABLED_DETAIL)

    delete_response = client.delete(
        f"/api/admin/sms/accounts/{account.id}", headers=headers
    )
    assert_api_error(delete_response, status.HTTP_409_CONFLICT, DISABLED_DETAIL)

    db_session.refresh(account)
    assert account.is_enabled is False
    assert account.display_name == original_name
    assert account._credentials == original_credentials


def test_mobilemessage_webhook_routes_reject_before_delegation_or_adapter_resolution(
    client, db_session, monkeypatch
):
    inbound_delegated = False
    delivery_adapter_resolved = False

    async def forbidden_inbound_delegation(**_kwargs):
        nonlocal inbound_delegated
        inbound_delegated = True
        raise AssertionError("MobileMessage inbound processing must not be delegated")

    def forbidden_delivery_adapter(_transport_type):
        nonlocal delivery_adapter_resolved
        delivery_adapter_resolved = True
        raise AssertionError("MobileMessage delivery adapter must not be resolved")

    monkeypatch.setattr(
        sms_webhooks_router,
        "process_inbound_webhook",
        forbidden_inbound_delegation,
    )
    monkeypatch.setattr(
        sms_webhooks_router,
        "get_transport_adapter",
        forbidden_delivery_adapter,
    )

    inbound_response = client.post(
        "/api/sms/webhooks/mobilemessage/nonexistent-account",
        content=b"not-json-and-must-not-be-read",
        headers={"content-type": "application/json"},
    )
    delivery_response = client.post(
        "/api/sms/webhooks/MobileMessage/nonexistent-account/delivery",
        content=b"not-json-and-must-not-be-read",
        headers={"content-type": "application/json"},
    )

    assert_api_error(inbound_response, status.HTTP_410_GONE, DISABLED_DETAIL)
    assert_api_error(delivery_response, status.HTTP_410_GONE, DISABLED_DETAIL)
    assert inbound_delegated is False
    assert delivery_adapter_resolved is False
    assert db_session.query(SmsInboundReceipt).count() == 0
    assert db_session.query(SmsDeliveryReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0


def test_inbound_service_and_transport_registry_fail_closed_before_database_access():
    class DatabaseAccessForbidden:
        def query(self, *_args, **_kwargs):
            raise AssertionError("MobileMessage rejection must precede account lookup")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            inbound_service.process_inbound_webhook(
                db=DatabaseAccessForbidden(),
                transport_type="MOBILEMESSAGE",
                account_public_id="synthetic-account-id",
                request=object(),
            )
        )

    assert exc_info.value.status_code == status.HTTP_410_GONE
    assert exc_info.value.detail == DISABLED_DETAIL

    with pytest.raises(ValueError, match="Unknown transport type"):
        get_transport_adapter("mobilemessage")
    assert get_transport_adapter("simulator") is not None


def test_worker_terminally_quarantines_mobilemessage_without_adapter_or_network(
    db_session, containment_data, monkeypatch
):
    account = containment_data["mobile_account"]
    conversation = SmsConversation(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        customer_address="61400000995",
        state="taken-over",
    )
    db_session.add(conversation)
    db_session.flush()

    message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Synthetic queued body that must never leave the test",
        direction="outbound",
        author_type="staff",
        status="queued",
    )
    db_session.add(message)
    db_session.flush()

    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=account.id,
        status="PENDING",
        retry_count=0,
    )
    db_session.add(job)
    db_session.commit()

    adapter_resolved = False

    def forbidden_adapter_resolution(_transport_type):
        nonlocal adapter_resolved
        adapter_resolved = True
        raise AssertionError("A disabled direct-provider job must not resolve an adapter")

    monkeypatch.setattr(
        outbox_worker, "get_transport_adapter", forbidden_adapter_resolution
    )

    asyncio.run(outbox_worker.process_pending_sms_outbound_jobs(db=db_session))

    db_session.refresh(job)
    db_session.refresh(message)
    assert adapter_resolved is False
    assert job.status == "FAILED"
    assert job.retry_count == 0
    assert job.lease_expires_at is None
    assert job.processed_at is not None
    assert job.error_log == TERMINAL_REASON
    assert message.status == "failed"
    assert message.provider_message_id is None
    assert message.body not in job.error_log
    assert conversation.customer_address not in job.error_log

    processed_at = job.processed_at
    asyncio.run(outbox_worker.process_pending_sms_outbound_jobs(db=db_session))
    db_session.refresh(job)
    assert adapter_resolved is False
    assert job.processed_at == processed_at


def test_worker_quarantines_mixed_mobilemessage_chatwoot_job_before_any_send(
    db_session, containment_data, monkeypatch
):
    account = containment_data["mobile_account"]
    conversation = SmsConversation(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        customer_address="61400000999",
        state="taken-over",
        chatwoot_conversation_id=424242,
    )
    db_session.add(conversation)
    db_session.flush()

    message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Synthetic mixed-state body that must never be sent",
        direction="outbound",
        author_type="staff",
        status="queued",
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=account.id,
        status="PENDING",
        retry_count=0,
    )
    db_session.add(job)
    db_session.commit()

    sends = {"chatwoot": 0, "transport": 0}

    async def forbidden_chatwoot_send(*_args, **_kwargs):
        sends["chatwoot"] += 1
        raise AssertionError("Mixed MobileMessage state must not reach Chatwoot send")

    def forbidden_adapter_resolution(_transport_type):
        sends["transport"] += 1
        raise AssertionError("Mixed MobileMessage state must not resolve an adapter")

    monkeypatch.setattr(
        chatwoot_service, "send_chatwoot_message", forbidden_chatwoot_send
    )
    monkeypatch.setattr(
        outbox_worker, "get_transport_adapter", forbidden_adapter_resolution
    )

    asyncio.run(outbox_worker.process_pending_sms_outbound_jobs(db=db_session))

    db_session.refresh(job)
    db_session.refresh(message)
    assert sends == {"chatwoot": 0, "transport": 0}
    assert job.status == "FAILED"
    assert job.retry_count == 0
    assert job.lease_expires_at is None
    assert job.processed_at is not None
    assert job.error_log == TERMINAL_REASON
    assert message.status == "failed"
    assert message.provider_message_id is None
    assert message.chatwoot_message_id is None
    assert message.body not in job.error_log
    assert conversation.customer_address not in job.error_log
def test_local_send_and_rearm_endpoints_are_disabled_without_mutation(
    client, db_session, containment_data
):
    account = containment_data["simulator_account"]
    headers = containment_data["headers"]
    conversation = SmsConversation(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        customer_address="61400000996",
        state="taken-over",
    )
    db_session.add(conversation)
    db_session.flush()

    draft = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Synthetic draft",
        direction="draft",
        author_type="ai",
        status="draft",
    )
    failed_message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Synthetic previously failed message",
        direction="outbound",
        author_type="staff",
        status="failed",
    )
    db_session.add_all([draft, failed_message])
    db_session.flush()
    failed_job = SmsOutboundJob(
        message_id=failed_message.id,
        sms_account_id=account.id,
        status="FAILED",
        retry_count=5,
        error_log=TERMINAL_REASON,
    )
    db_session.add(failed_job)
    db_session.commit()

    original_counts = {
        "messages": db_session.query(SmsMessage).count(),
        "jobs": db_session.query(SmsOutboundJob).count(),
        "events": db_session.query(SmsConversationEvent).count(),
    }

    responses = (
        client.post(
            f"/api/admin/sms/conversations/{conversation.id}/messages",
            headers=headers,
            json={
                "body": "Synthetic manual reply",
                "client_request_id": "synthetic-local-compose",
            },
        ),
        client.post(
            f"/api/admin/sms/conversations/messages/{draft.id}/approve",
            headers=headers,
        ),
        client.post(
            f"/api/admin/sms/conversations/jobs/{failed_job.id}/retry",
            headers=headers,
        ),
        client.post(
            f"/api/admin/sms/conversations/{conversation.id}/auto-reply",
            headers=headers,
        ),
    )

    for response in responses:
        assert_api_error(response, status.HTTP_409_CONFLICT, LOCAL_SEND_DETAIL)

    db_session.refresh(conversation)
    db_session.refresh(draft)
    db_session.refresh(failed_message)
    db_session.refresh(failed_job)
    assert conversation.state == "taken-over"
    assert draft.direction == "draft"
    assert draft.status == "draft"
    assert failed_message.status == "failed"
    assert failed_job.status == "FAILED"
    assert failed_job.retry_count == 5
    assert failed_job.error_log == TERMINAL_REASON
    assert db_session.query(SmsMessage).count() == original_counts["messages"]
    assert db_session.query(SmsOutboundJob).count() == original_counts["jobs"]
    assert db_session.query(SmsConversationEvent).count() == original_counts["events"]

    discard_response = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/discard",
        headers=headers,
    )
    assert discard_response.status_code == status.HTTP_200_OK
    assert discard_response.json()["status"] == "discarded"

    auto_conversation = SmsConversation(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        customer_address="61400000997",
        state="auto-reply",
    )
    db_session.add(auto_conversation)
    db_session.flush()
    ai_job = SmsAiJob(
        conversation_id=auto_conversation.id,
        customer_turn_ref="synthetic-turn",
        status="PENDING",
    )
    db_session.add(ai_job)
    db_session.commit()

    takeover_response = client.post(
        f"/api/admin/sms/conversations/{auto_conversation.id}/takeover",
        headers=headers,
    )
    assert takeover_response.status_code == status.HTTP_200_OK
    db_session.refresh(auto_conversation)
    db_session.refresh(ai_job)
    assert auto_conversation.state == "taken-over"
    assert ai_job.status == "CANCELLED"
