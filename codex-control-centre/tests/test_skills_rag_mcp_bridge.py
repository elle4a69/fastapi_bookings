"""Contract tests for the lightweight native Skills RAG MCP bridge."""

import json
from io import BytesIO
from urllib import error

from backend.config import settings
from backend.services import skills_rag_mcp_bridge as bridge


class FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


def test_initialize_and_tools_list_expose_only_read_only_find_and_skill():
    initialized = bridge.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
    )
    listed = bridge.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    assert initialized["result"]["protocolVersion"] == "2025-06-18"
    assert initialized["result"]["serverInfo"]["name"] == "skills-rag-http-bridge"
    assert [tool["name"] for tool in listed["result"]["tools"]] == ["find", "skill"]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in listed["result"]["tools"])


def test_onboard_codex_worker_registers_lightweight_bridge():
    joined = "\n".join(settings.codex_app_server_args)

    assert "mcp_servers.mcp-skillset.enabled=false" in joined
    assert "mcp_servers.skills-rag.command=" in joined
    assert "skills_rag_mcp_bridge.py" in joined
    assert "mcp_servers.skills-rag.enabled=true" in joined


def test_find_validates_and_truncates_results(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        return FakeResponse({"results": [{"id": "one"}, {"id": "two"}, {"id": "three"}]})

    monkeypatch.setattr(bridge.request, "urlopen", fake_urlopen)
    result = bridge.call_tool("find", {"query": "FastAPI tenant security", "limit": 2})
    payload = json.loads(result["content"][0]["text"])

    assert result["isError"] is False
    assert payload["count"] == 2
    assert [item["id"] for item in payload["results"]] == ["one", "two"]
    assert "query=FastAPI+tenant+security" in captured["url"]
    assert captured["timeout"] == bridge.DEFAULT_TIMEOUT_SECONDS


def test_skill_reads_complete_indexed_content(monkeypatch):
    monkeypatch.setattr(
        bridge.request,
        "urlopen",
        lambda _req, timeout: FakeResponse({"id": "api-security", "content": "complete instructions"}),
    )

    result = bridge.call_tool("skill", {"name": "api-security"})
    payload = json.loads(result["content"][0]["text"])

    assert result["isError"] is False
    assert payload["content"] == "complete instructions"


def test_validation_and_daemon_failures_are_explicit_tool_errors(monkeypatch):
    invalid = bridge.call_tool("find", {"query": "", "limit": 100})
    assert invalid["isError"] is True
    assert "non-empty string" in invalid["content"][0]["text"]

    def unavailable(_req, timeout):
        raise error.URLError("offline")

    monkeypatch.setattr(bridge.request, "urlopen", unavailable)
    offline = bridge.call_tool("skill", {"name": "api-security"})
    assert offline["isError"] is True
    assert "port 8008" in offline["content"][0]["text"]


def test_tools_call_uses_mcp_content_contract(monkeypatch):
    monkeypatch.setattr(
        bridge.request,
        "urlopen",
        lambda _req, timeout: FakeResponse({"results": [{"id": "agent-tool-builder"}]}),
    )
    response = bridge.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "find", "arguments": {"query": "MCP tool schema"}},
        }
    )

    assert response["id"] == 7
    assert response["result"]["isError"] is False
    assert response["result"]["content"][0]["type"] == "text"
