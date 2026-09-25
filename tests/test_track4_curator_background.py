"""Tests for Chatwoot background memory curation dispatch and completion hook (Track 4)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.api.routers.chatwoot_agentbot import (
    curate_conversation_background,
)
from app.services.curation.memory_curator import CuratorDecision


def test_complete_conversation_hook_dispatch():
    """Verify POST /conversations/{conversation_id}/complete dispatches background curation."""
    client = TestClient(app)

    transcript = [
        {"role": "user", "content": "What is the cancellation policy?"},
        {"role": "assistant", "content": "You can cancel up to 24 hours prior to appointment."},
    ]

    with patch("app.api.routers.chatwoot_agentbot.curate_conversation_background", new_callable=AsyncMock) as mock_curate:
        mock_curate.return_value = [
            CuratorDecision(
                action="ADD",
                target_memory_id=1,
                ideal_response="You can cancel up to 24 hours prior to appointment.",
                category="policy",
                rationale="New policy curated",
            )
        ]

        resp = client.post(
            "/api/v1/chatwoot/conversations/42/complete",
            json={
                "tenant_id": 1,
                "provider_id": 2,
                "transcript": transcript,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enqueued"
        assert data["conversation_id"] == 42
        assert data["tenant_id"] == 1
        assert data["action"] == "curation_background_task"

        # FastAPI BackgroundTasks executes after response is generated in TestClient
        mock_curate.assert_called_once_with(
            tenant_id=1,
            transcript=transcript,
            provider_id=2,
        )


def test_webhook_conversation_resolved_dispatches_curation():
    """Verify conversation_resolved event with transcript triggers background curation."""
    client = TestClient(app)

    transcript = [
        {"role": "user", "content": "Where is the clinic located?"},
        {"role": "assistant", "content": "We are located at 42 Wallaby Way, Sydney."},
    ]

    with patch("app.api.routers.chatwoot_agentbot.curate_conversation_background", new_callable=AsyncMock) as mock_curate:
        resp = client.post(
            "/api/v1/chatwoot/webhook",
            json={
                "event": "conversation_resolved",
                "conversation": {"id": 100, "status": "resolved"},
                "account": {"id": 5},
                "transcript": transcript,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "handled"
        assert data["action"] == "conversation_curation_enqueued"
        assert data["conversation_id"] == 100
        assert data["account_id"] == 5

        mock_curate.assert_called_once_with(
            tenant_id=5,
            transcript=transcript,
        )


@pytest.mark.asyncio
async def test_curate_conversation_background_runner():
    """Verify curate_conversation_background opens session scope and executes curate_conversation."""
    transcript = [
        {"role": "user", "content": "Do you offer telehealth?"},
        {"role": "assistant", "content": "Yes, telehealth appointments are available."},
    ]

    fake_decisions = [
        CuratorDecision(
            action="ADD",
            target_memory_id=99,
            ideal_response="Yes, telehealth appointments are available.",
            category="service_info",
            rationale="Telehealth info added",
        )
    ]

    with patch("app.api.routers.chatwoot_agentbot.curate_conversation", new_callable=AsyncMock) as mock_curate:
        mock_curate.return_value = fake_decisions

        decisions = await curate_conversation_background(
            tenant_id=1,
            transcript=transcript,
            provider_id=None,
        )

        assert len(decisions) == 1
        assert decisions[0].action == "ADD"
        assert decisions[0].target_memory_id == 99
        mock_curate.assert_called_once()
