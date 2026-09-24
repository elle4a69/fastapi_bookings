"""Privacy-safe synthetic tests for the external AI gateway boundary."""

import asyncio
import logging
import secrets

import pytest
from pydantic import SecretStr

from app.core.config import Settings, settings
from app.services.gateway import responses_client


@pytest.fixture(autouse=True)
def isolate_global_openai_credential(monkeypatch):
    """Keep gateway tests independent from developer-machine configuration."""

    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(""))


class _FailingAsyncClient:
    def __init__(self, marker: str):
        self._marker = marker

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        raise RuntimeError(self._marker)


class _SyntheticResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Synthetic response"}}]}


class _SuccessfulAsyncClient:
    def __init__(self, captured_headers: dict[str, str]):
        self._captured_headers = captured_headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **kwargs):
        self._captured_headers.update(kwargs["headers"])
        return _SyntheticResponse()


def test_openai_setting_is_typed_secret_and_excluded_from_serialization():
    marker = "SyntheticTypedSettingsCredentialAlphaOmega"
    configured = Settings(_env_file=None, OPENAI_API_KEY=marker)

    assert isinstance(configured.OPENAI_API_KEY, SecretStr)
    assert secrets.compare_digest(
        configured.OPENAI_API_KEY.get_secret_value(), marker
    )
    assert "OPENAI_API_KEY" not in configured.model_dump()
    assert marker not in repr(configured)
    assert marker not in repr(configured.model_dump())
    assert marker not in configured.model_dump_json()


def test_gateway_uses_typed_global_key_without_network_or_log_reflection(
    monkeypatch,
    caplog,
):
    marker = "SyntheticTypedGatewayCredentialAlphaOmega"
    captured_headers: dict[str, str] = {}
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(marker))
    monkeypatch.setattr(
        responses_client,
        "validate_request",
        lambda *_args, **_kwargs: "synthetic-model",
    )
    monkeypatch.setattr(
        responses_client,
        "enforce_tenant_budget",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        responses_client.httpx,
        "AsyncClient",
        lambda: _SuccessfulAsyncClient(captured_headers),
    )

    with caplog.at_level(logging.INFO, logger=responses_client.__name__):
        result = asyncio.run(
            responses_client.generate_response(
                tenant_id="synthetic-tenant",
                messages=[{"role": "user", "content": "Synthetic prompt"}],
            )
        )

    assert result == {
        "choices": [{"message": {"content": "Synthetic response"}}]
    }
    authorization = captured_headers.pop("Authorization")
    assert secrets.compare_digest(authorization, f"Bearer {marker}")
    assert captured_headers == {"Content-Type": "application/json"}
    assert marker not in caplog.text


def test_gateway_failure_uses_fixed_log_and_exception_without_input_reflection(
    monkeypatch,
    caplog,
):
    marker = "SYNTHETIC_GATEWAY_EXCEPTION_CANARY_DO_NOT_LOG"
    credential_marker = "SyntheticGatewayCredentialAlphaOmega"
    prompt_marker = "Synthetic private gateway prompt marker"
    monkeypatch.setattr(
        responses_client,
        "validate_request",
        lambda *_args, **_kwargs: "synthetic-model",
    )
    monkeypatch.setattr(
        responses_client.httpx,
        "AsyncClient",
        lambda: _FailingAsyncClient(marker),
    )

    with caplog.at_level(logging.ERROR, logger=responses_client.__name__):
        with pytest.raises(responses_client.AiGatewayError) as error:
            asyncio.run(
                responses_client.generate_response(
                    tenant_id=1,
                    messages=[{"role": "user", "content": prompt_marker}],
                    api_key=credential_marker,
                )
            )

    assert str(error.value) == "AI gateway request failed."
    assert caplog.messages == ["OpenAI gateway request failed."]
    for sensitive_value in (marker, credential_marker, prompt_marker):
        assert sensitive_value not in caplog.text
        assert sensitive_value not in str(error.value)
