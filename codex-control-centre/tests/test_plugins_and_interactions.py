import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.middleware.auth import verify_auth
from backend.routers.plugins import MARKETPLACE_KINDS
from backend.services import governance_service


PLUGIN_ID = "codex-security@openai-curated-remote"


def _catalog(installed: bool = False):
    return {
        "marketplaces": [{
            "name": "openai-curated-remote",
            "path": None,
            "interface": {"displayName": "OpenAI"},
            "plugins": [{
                "id": PLUGIN_ID,
                "name": "codex-security",
                "version": "0.1.32",
                "localVersion": "0.1.32" if installed else None,
                "installed": installed,
                "enabled": installed,
                "installPolicy": "AVAILABLE",
                "authPolicy": "ON_INSTALL",
                "availability": "AVAILABLE",
                "source": {"type": "remote"},
                "interface": {
                    "displayName": "Codex Security",
                    "shortDescription": "Security scanning for your codebase",
                    "developerName": "OpenAI",
                    "category": "Security",
                    "capabilities": ["Interactive", "Read", "Write"],
                    "logoUrl": "https://files.openai.com/security.png",
                },
                "keywords": ["security"],
            }],
        }],
        "marketplaceLoadErrors": [],
        "featuredPluginIds": [PLUGIN_ID],
    }


@pytest.fixture(autouse=True)
def clear_pending_interactions():
    governance_service._pending_interaction_registry.clear()
    yield
    governance_service._pending_interaction_registry.clear()


@pytest.fixture
def client():
    app.dependency_overrides[verify_auth] = lambda: "test-token"
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_plugin_catalog_is_sanitized_and_authenticated(client):
    worker = AsyncMock()
    worker.running = True
    worker.send_request.return_value = _catalog()
    with patch("backend.routers.plugins.worker_manager.get_worker", AsyncMock(return_value=worker)):
        response = client.get("/codex/plugins")

    assert response.status_code == 200
    payload = response.json()
    assert payload["featuredPluginIds"] == [PLUGIN_ID]
    assert payload["plugins"][0]["id"] == PLUGIN_ID
    assert payload["plugins"][0]["marketplace"] == {
        "name": "openai-curated-remote",
        "displayName": "OpenAI",
        "remote": True,
    }
    assert "path" not in json.dumps(payload)
    worker.send_request.assert_awaited_once_with(
        "plugin/list",
        {"marketplaceKinds": MARKETPLACE_KINDS},
        timeout=90,
    )


def test_plugin_install_uses_catalog_identity_and_returns_auth_links(client):
    worker = AsyncMock()
    worker.running = True
    worker.send_request.side_effect = [
        _catalog(),
        {
            "authPolicy": "ON_INSTALL",
            "appsNeedingAuth": [{
                "id": "github",
                "name": "GitHub",
                "description": "Repository access",
                "installUrl": "https://chatgpt.com/apps/github",
                "category": "Code Hosting",
            }],
        },
    ]
    with patch("backend.routers.plugins.worker_manager.get_worker", AsyncMock(return_value=worker)):
        response = client.post(f"/codex/plugins/{PLUGIN_ID}/install")

    assert response.status_code == 200
    assert response.json()["installed"] is True
    assert response.json()["appsNeedingAuth"][0]["installUrl"] == "https://chatgpt.com/apps/github"
    install_call = worker.send_request.await_args_list[1]
    assert install_call.args[0] == "plugin/install"
    assert install_call.args[1] == {
        "pluginName": "codex-security",
        "remoteMarketplaceName": "openai-curated-remote",
    }
    assert "marketplacePath" not in install_call.args[1]


@pytest.mark.asyncio
async def test_tool_user_input_response_reaches_originating_worker():
    worker = AsyncMock()
    interaction = governance_service.register_pending_interaction(
        resp_id=77,
        worker=worker,
        method="item/tool/requestUserInput",
        thread_id="thread-1",
        project_id="project-1",
        turn_id="turn-1",
        params={"questions": [{"id": "approval", "question": "Install?"}]},
    )

    result = await governance_service.resolve_pending_interaction(
        interaction["id"],
        action="accept",
        response={"answers": {"approval": "Accept"}},
    )

    assert result["status"] == "submitted"
    response_packet = json.loads(worker.send_raw.await_args.args[0])
    assert response_packet == {
        "jsonrpc": "2.0",
        "id": 77,
        "result": {"answers": {"approval": {"answers": ["Accept"]}}},
    }
    assert governance_service.list_pending_interactions("thread-1") == []


@pytest.mark.asyncio
async def test_mcp_url_and_permissions_responses_use_app_server_contracts():
    mcp_worker = AsyncMock()
    mcp = governance_service.register_pending_interaction(
        resp_id="mcp-1",
        worker=mcp_worker,
        method="mcpServer/elicitation/request",
        thread_id="thread-1",
        project_id="project-1",
        turn_id="turn-1",
        params={"mode": "url", "url": "https://example.test/auth"},
    )
    await governance_service.resolve_pending_interaction(mcp["id"], action="decline", response={})
    mcp_packet = json.loads(mcp_worker.send_raw.await_args.args[0])
    assert mcp_packet["result"] == {"action": "decline", "content": None}

    permission_worker = AsyncMock()
    requested = {"network": {"enabled": True}}
    permission = governance_service.register_pending_interaction(
        resp_id="permission-1",
        worker=permission_worker,
        method="item/permissions/requestApproval",
        thread_id="thread-1",
        project_id="project-1",
        turn_id="turn-1",
        params={"permissions": requested},
    )
    await governance_service.resolve_pending_interaction(
        permission["id"],
        action="accept",
        response={"permissions": requested, "scope": "session"},
    )
    permission_packet = json.loads(permission_worker.send_raw.await_args.args[0])
    assert permission_packet["result"] == {"permissions": requested, "scope": "session"}


@pytest.mark.asyncio
async def test_v2_approval_response_honors_session_scope():
    worker = AsyncMock()
    governance_service.dispatch_approval_rpc(
        resp_id="approval-1",
        worker=worker,
        approved=True,
        method="item/commandExecution/requestApproval",
        scope="session",
    )
    # dispatch_approval_rpc schedules the worker coroutine on the active loop.
    import asyncio
    await asyncio.sleep(0)
    packet = json.loads(worker.send_raw.await_args.args[0])
    assert packet["result"] == {"decision": "acceptForSession"}
