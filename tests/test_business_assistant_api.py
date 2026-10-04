"""Authenticated text API tests for the native Business Assistant."""

from app.core.config import settings
from app.core.security import create_access_token
from app.models.business_assistant import BusinessAssistantMessage
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.runtime import BusinessAssistantTextRuntime
from app.services.business_assistant.idempotency import payload_hash


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Text Tenant {suffix}", subdomain=f"text-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"owner-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_text_request_uses_completion_token_limit_without_network_io():
    runtime = BusinessAssistantTextRuntime(
        model_name="configured-text-model",
        api_key="configured",
        max_history_messages=20,
        max_output_tokens=600,
        timeout_seconds=30,
        max_tool_rounds=3,
        client_factory=BusinessAssistantTextRuntime,
    )

    options = runtime._chat_request_options(messages=[], tools=(), include_tools=False)

    assert options["max_completion_tokens"] == 600
    assert "max_tokens" not in options
    assert options["model"] == "configured-text-model"

    tool_options = runtime._chat_request_options(
        messages=[],
        tools=({"type": "function", "function": {"name": "read_product_help"}},),
        include_tools=True,
    )
    assert tool_options["tool_choice"] == "auto"
    assert "reasoning_effort" not in tool_options

    # gpt-4o / gpt-4o-mini models must never include reasoning_effort
    for standard_model in ("gpt-4o", "gpt-4o-mini"):
        std_runtime = BusinessAssistantTextRuntime(
            model_name=standard_model,
            api_key="configured",
            max_history_messages=20,
            max_output_tokens=600,
            timeout_seconds=30,
            max_tool_rounds=3,
            client_factory=BusinessAssistantTextRuntime,
        )
        std_options = std_runtime._chat_request_options(
            messages=[],
            tools=({"type": "function", "function": {"name": "read_product_help"}},),
            include_tools=True,
        )
        assert "reasoning_effort" not in std_options

    # gpt-5 models that require reasoning_effort="none" receive it
    gpt5_runtime = BusinessAssistantTextRuntime(
        model_name="gpt-5.6-terra",
        api_key="configured",
        max_history_messages=20,
        max_output_tokens=600,
        timeout_seconds=30,
        max_tool_rounds=3,
        client_factory=BusinessAssistantTextRuntime,
    )
    gpt5_options = gpt5_runtime._chat_request_options(
        messages=[],
        tools=({"type": "function", "function": {"name": "read_product_help"}},),
        include_tools=True,
    )
    assert gpt5_options["reasoning_effort"] == "none"


def test_text_runtime_constructs_openai_client_with_keyword_api_key_without_network_io():
    from openai import OpenAI

    runtime = BusinessAssistantTextRuntime(
        model_name="configured-text-model",
        api_key="configured",
        max_history_messages=20,
        max_output_tokens=600,
        timeout_seconds=30,
        max_tool_rounds=3,
        client_factory=OpenAI,
    )

    client = runtime._create_client()
    try:
        assert isinstance(client, OpenAI)
    finally:
        client.close()


def _create_conversation(client, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"title": "Product guidance", "request_key": "conversation-request-key"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_text_routes_require_authenticated_owner(client, db_session):
    tenant, _user = _owner(db_session, "auth")
    response = client.get(
        "/api/admin/business-assistant/conversations",
        headers={"X-Tenant": tenant.subdomain},
    )
    assert response.status_code == 401


def test_missing_model_configuration_preserves_exactly_one_user_message(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "unavailable")
    headers = _headers(tenant, user)
    conversation_id = _create_conversation(client, headers)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_TEXT_MODEL", "")
    payload = {"content": "How do I manage services?", "request_key": "unavailable-turn-request-key"}

    response = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TEXT_CONFIGURATION_REQUIRED"
    assert "message was saved" in response.json()["error"]["message"].lower()

    history = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert [message["role"] for message in history.json()] == ["user"]
    assert history.json()[0]["content"] == payload["content"]

    retry = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json=payload,
    )
    assert retry.status_code == 503
    assert len(client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    ).json()) == 1


def test_missing_model_configuration_never_manufactures_a_reply(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "retry")
    headers = _headers(tenant, user)
    conversation_id = _create_conversation(client, headers)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_TEXT_MODEL", "")
    payload = {"content": "Please explain the dashboard.", "request_key": "retry-turn-request-key"}

    unavailable = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json=payload,
    )
    assert unavailable.status_code == 503
    assert "message was saved" in unavailable.json()["error"]["message"].lower()

    after_failure = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert after_failure.status_code == 200
    assert [message["role"] for message in after_failure.json()] == ["user"]

    duplicate = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json=payload,
    )
    assert duplicate.status_code == 503

    final_history = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [message["role"] for message in final_history.json()] == ["user"]


def test_running_duplicate_turn_returns_explicit_in_progress_without_second_user_turn(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "in-progress")
    headers = _headers(tenant, user)
    conversation_id = _create_conversation(client, headers)
    request_key = "concurrent-turn-request-key"
    db_session.add(
        BusinessAssistantMessage(
            conversation_id=conversation_id,
            tenant_id=tenant.id,
            user_id=user.id,
            role="user",
            content="Already claimed by another request.",
            request_key=request_key,
            request_payload_hash=payload_hash({"content": "Already claimed by another request."}),
            generation_status="running",
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_TEXT_MODEL", "")

    response = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Already claimed by another request.", "request_key": request_key},
    )
    assert response.status_code == 409
    assert "already in progress" in response.json()["error"]["message"].lower()

    history = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["role"] == "user"


def test_conversation_history_is_hidden_from_a_different_tenant(client, db_session):
    tenant_a, user_a = _owner(db_session, "scope-a")
    tenant_b, user_b = _owner(db_session, "scope-b")
    conversation_id = _create_conversation(client, _headers(tenant_a, user_a))

    response = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=_headers(tenant_b, user_b),
    )
    assert response.status_code == 404

    response = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=_headers(tenant_b, user_b),
        json={"content": "Attempt cross-tenant access", "request_key": "cross-tenant-request-key"},
    )
    assert response.status_code == 404


def test_conversation_and_text_request_keys_reject_changed_payloads(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "payload-conflict")
    headers = _headers(tenant, user)
    created = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"title": "First subject", "request_key": "conversation-payload-key"},
    )
    assert created.status_code == 201
    changed_conversation = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"title": "Changed subject", "request_key": "conversation-payload-key"},
    )
    assert changed_conversation.status_code == 409

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_TEXT_MODEL", "")
    conversation_id = created.json()["id"]
    saved = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Original text turn", "request_key": "text-payload-conflict-key"},
    )
    assert saved.status_code == 503
    changed_text = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Changed text turn", "request_key": "text-payload-conflict-key"},
    )
    assert changed_text.status_code == 409
