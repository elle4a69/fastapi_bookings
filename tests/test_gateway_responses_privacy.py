"""Privacy-safe synthetic tests for the external AI gateway boundary."""

import asyncio
import logging

import pytest

from app.services.gateway import responses_client


class _FailingAsyncClient:
    def __init__(self, marker: str):
        self._marker = marker

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        raise RuntimeError(self._marker)


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
