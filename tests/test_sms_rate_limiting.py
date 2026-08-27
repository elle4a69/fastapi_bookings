import pytest
import asyncio
from datetime import datetime, timezone, timedelta, time
from unittest.mock import patch

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.client import Client
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsOutboundJob
from app.services.sms.transports.fake import FakeTransportAdapter
from app.services.sms.rate_limit_service import check_rate_limit_and_quiet_hours
from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs


@pytest.fixture
def setup_rate_limit_data(db_session):
    # Create tenant with timezone info
    tenant = Tenant(name="Rate Limit Tenant", subdomain="rate-limit", timezone="Australia/Sydney")
    db_session.add(tenant)
    db_session.commit()

    admin = User(tenant_id=tenant.id, login="admin@ratelimit.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name="Rate Limit Provider", active=True)
    db_session.add(provider)
    db_session.commit()

    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Rate Limit Line",
        sender_address="61400000003",
        is_enabled=True,
        throughput_limit=2,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00"
    )
    db_session.add(account)
    db_session.commit()

    client = Client(tenant_id=tenant.id, name="Jane Doe", phone="0412345679", active=True)
    db_session.add(client)
    db_session.commit()

    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61412345679",
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conversation)
    db_session.commit()

    FakeTransportAdapter.sent_messages.clear()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "account": account,
        "client": client,
        "conversation": conversation
    }


def test_rate_limiting_service_quiet_hours(db_session, setup_rate_limit_data):
    account = setup_rate_limit_data["account"]
    tenant = setup_rate_limit_data["tenant"]

    # Sydney is +10:00 (or +11:00, let's assume +10:00 for the test calculation or check dynamic timezone conversion)
    # If UTC time is 11:30 AM (11:30), Sydney time is 9:30 PM (21:30). Quiet hours start at 22:00, so 21:30 is OUTSIDE.
    # If UTC time is 12:30 PM (12:30), Sydney time is 10:30 PM (22:30). Quiet hours start at 22:00, so 22:30 is INSIDE.
    # If UTC time is 8:30 PM (20:30), Sydney time is 6:30 AM (06:30) next day. Quiet hours end at 07:00, so 06:30 is INSIDE.

    # Mock time to 11:30:00 UTC -> 21:30 Sydney (Outside quiet hours)
    mock_utc_now = datetime(2026, 8, 25, 11, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.sms.rate_limit_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_utc_now
        mock_datetime.combine = datetime.combine
        # Verify check passes
        assert check_rate_limit_and_quiet_hours(db_session, account) is True

    # Mock time to 12:30:00 UTC -> 22:30 Sydney (Inside quiet hours)
    mock_utc_now = datetime(2026, 8, 25, 12, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.sms.rate_limit_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_utc_now
        mock_datetime.combine = datetime.combine
        # Verify check fails (quiet hours active)
        assert check_rate_limit_and_quiet_hours(db_session, account) is False

    # Mock time to 20:30:00 UTC -> 06:30 Sydney next day (Inside quiet hours, midnight wrap)
    mock_utc_now = datetime(2026, 8, 25, 20, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.sms.rate_limit_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_utc_now
        mock_datetime.combine = datetime.combine
        # Verify check fails (quiet hours active)
        assert check_rate_limit_and_quiet_hours(db_session, account) is False


def test_rate_limiting_service_throughput(db_session, setup_rate_limit_data):
    account = setup_rate_limit_data["account"]
    conversation = setup_rate_limit_data["conversation"]

    # Temporarily remove quiet hours to test throughput limit
    account.quiet_hours_start = None
    account.quiet_hours_end = None
    db_session.commit()

    # Create 2 outbound sent messages in last 30 seconds
    now = datetime.now(timezone.utc)
    msg1 = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Msg 1",
        direction="outbound",
        author_type="ai",
        status="sent",
        occurred_at=now - timedelta(seconds=30),
        received_at=now - timedelta(seconds=30)
    )
    msg2 = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Msg 2",
        direction="outbound",
        author_type="ai",
        status="delivered",
        occurred_at=now - timedelta(seconds=20),
        received_at=now - timedelta(seconds=20)
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # Limit is 2. We have sent 2 in the last 60 seconds.
    # The check should return False.
    assert check_rate_limit_and_quiet_hours(db_session, account) is False

    # Now make one of the messages older (e.g. 70 seconds ago)
    msg1.occurred_at = now - timedelta(seconds=70)
    db_session.commit()

    # We now have 1 message in the last 60 seconds.
    # The check should return True.
    assert check_rate_limit_and_quiet_hours(db_session, account) is True


def test_outbox_worker_quiet_hours_deferral(db_session, setup_rate_limit_data):
    account = setup_rate_limit_data["account"]
    conversation = setup_rate_limit_data["conversation"]

    # Add job to queue
    message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Hello quiet hours test",
        direction="outbound",
        author_type="ai",
        status="queued",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(message)
    db_session.commit()

    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=account.id,
        status="PENDING",
        lease_expires_at=None
    )
    db_session.add(job)
    db_session.commit()

    # Mock time to 12:30:00 UTC -> 22:30 Sydney (Inside quiet hours)
    mock_utc_now = datetime(2026, 8, 25, 12, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.sms.rate_limit_service.datetime") as mock_rl_dt, \
         patch("app.services.sms.outbox_worker.datetime") as mock_worker_dt:
        mock_rl_dt.now.return_value = mock_utc_now
        mock_rl_dt.combine = datetime.combine
        mock_worker_dt.now.return_value = mock_utc_now
        mock_worker_dt.combine = datetime.combine

        # Process jobs
        asyncio.run(process_pending_sms_outbound_jobs(db=db_session))

    # Assert job is still PENDING and lease_expires_at is pushed (set to future, i.e., mock_utc_now + 1 minute)
    db_session.refresh(job)
    assert job.status == "PENDING"
    assert job.lease_expires_at is not None
    assert job.lease_expires_at.replace(tzinfo=timezone.utc) == mock_utc_now + timedelta(minutes=1)
    assert len(FakeTransportAdapter.sent_messages) == 0

    # Clear lease_expires_at and mock time to 11:30:00 UTC -> 21:30 Sydney (Outside quiet hours)
    job.lease_expires_at = None
    db_session.commit()

    mock_utc_now_outside = datetime(2026, 8, 25, 11, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.sms.rate_limit_service.datetime") as mock_rl_dt, \
         patch("app.services.sms.outbox_worker.datetime") as mock_worker_dt:
        mock_rl_dt.now.return_value = mock_utc_now_outside
        mock_rl_dt.combine = datetime.combine
        mock_worker_dt.now.return_value = mock_utc_now_outside
        mock_worker_dt.combine = datetime.combine

        # Process jobs
        asyncio.run(process_pending_sms_outbound_jobs(db=db_session))

    # Assert job is SUCCESS
    db_session.refresh(job)
    assert job.status == "SUCCESS"
    assert len(FakeTransportAdapter.sent_messages) == 1
    assert FakeTransportAdapter.sent_messages[0]["body"] == "Hello quiet hours test"


def test_outbox_worker_throughput_deferral(db_session, setup_rate_limit_data):
    account = setup_rate_limit_data["account"]
    conversation = setup_rate_limit_data["conversation"]

    # Temporarily remove quiet hours
    account.quiet_hours_start = None
    account.quiet_hours_end = None
    db_session.commit()

    # Create 2 outbound sent messages in last 30 seconds
    now = datetime.now(timezone.utc)
    msg1 = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Msg 1",
        direction="outbound",
        author_type="ai",
        status="sent",
        occurred_at=now - timedelta(seconds=30),
        received_at=now - timedelta(seconds=30)
    )
    msg2 = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Msg 2",
        direction="outbound",
        author_type="ai",
        status="delivered",
        occurred_at=now - timedelta(seconds=20),
        received_at=now - timedelta(seconds=20)
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # Now queue a new outbound job
    message = SmsMessage(
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Hello throughput test",
        direction="outbound",
        author_type="ai",
        status="queued",
        occurred_at=now,
        received_at=now
    )
    db_session.add(message)
    db_session.commit()

    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=account.id,
        status="PENDING",
        lease_expires_at=None
    )
    db_session.add(job)
    db_session.commit()

    # Process jobs -> throughput is reached, should defer
    asyncio.run(process_pending_sms_outbound_jobs(db=db_session))

    db_session.refresh(job)
    assert job.status == "PENDING"
    assert job.lease_expires_at is not None
    assert len(FakeTransportAdapter.sent_messages) == 0

    # Make the prior sent messages older (120 seconds ago)
    msg1.occurred_at = now - timedelta(seconds=120)
    msg2.occurred_at = now - timedelta(seconds=120)
    job.lease_expires_at = None
    db_session.commit()

    # Process jobs -> throughput limit check now passes, should succeed
    asyncio.run(process_pending_sms_outbound_jobs(db=db_session))

    db_session.refresh(job)
    assert job.status == "SUCCESS"
    assert len(FakeTransportAdapter.sent_messages) == 1
    assert FakeTransportAdapter.sent_messages[0]["body"] == "Hello throughput test"
