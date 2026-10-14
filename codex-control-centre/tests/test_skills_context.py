"""Contracts for port 8008 Skills RAG search and bounded Codex turn context."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import settings
from backend.routers import skills
from backend.routers.turns import _safe_dispatch_turn_start
from backend.services.skills_context import (
    SkillNotFoundError,
    SkillsContextService,
    SkillsServiceError,
    derive_safe_search_query,
    skills_context_service,
)
from backend.services.worker_manager import worker_manager


class FakeWorker:
    def __init__(self) -> None:
        self.thread_map = {"thread-skills": "codex-thread-skills"}
        self.calls: list[tuple[str, dict]] = []

    async def send_request(self, method: str, params: dict):
        self.calls.append((method, params))
        return {"turn": {"id": "turn-skills"}}


def test_safe_query_uses_only_allowlisted_technical_terms():
    query = derive_safe_search_query(
        "Fix FastAPI authorization for person@example.com using secret sk-test-123 and React context"
    )
    assert query == "codex fastapi authorization react context"
    assert "example.com" not in query
    assert "sk-test" not in query


@pytest.mark.asyncio
async def test_build_turn_context_reads_only_top_matches_and_enforces_budget(monkeypatch):
    service = SkillsContextService("http://127.0.0.1:8008")
    monkeypatch.setattr(settings, "skills_rag_enabled", True)
    monkeypatch.setattr(settings, "skills_rag_top_k", 2)
    monkeypatch.setattr(settings, "skills_rag_max_skill_chars", 6)
    monkeypatch.setattr(settings, "skills_rag_max_context_chars", 10)
    service.search = AsyncMock(return_value=[
        {"id": "security", "name": "security", "description": "Secure APIs", "category": "", "tags": [], "score": 0.9},
        {"id": "fastapi", "name": "fastapi", "description": "FastAPI", "category": "", "tags": [], "score": 0.8},
    ])
    service.read = AsyncMock(side_effect=[
        {"id": "security", "name": "security", "description": "Secure APIs", "content": "ABCDEFGHIJK"},
        {"id": "fastapi", "name": "fastapi", "description": "FastAPI", "content": "123456789"},
    ])

    result = await service.build_turn_context("FastAPI security implementation")

    assert result["status"] == "loaded"
    assert [item["id"] for item in result["skills"]] == ["security", "fastapi"]
    assert result["skills"][0]["includedChars"] == 6
    assert result["skills"][1]["includedChars"] == 4
    assert "ABCDEF" in result["context"]
    assert "1234" in result["context"]
    assert "12345" not in result["context"]


@pytest.mark.asyncio
async def test_context_retrieval_failure_does_not_fail_the_codex_turn():
    service = SkillsContextService()
    service.search = AsyncMock(side_effect=SkillsServiceError("offline"))

    result = await service.build_turn_context("FastAPI testing")

    assert result["status"] == "unavailable"
    assert result["context"] == ""


@pytest.mark.asyncio
async def test_turn_dispatch_attaches_bounded_skill_context(monkeypatch):
    worker = FakeWorker()
    original_mapping = dict(worker_manager.thread_map)
    worker_manager.thread_map["thread-skills"] = "codex-thread-skills"
    context = {
        "status": "loaded",
        "query": "codex fastapi security",
        "skills": [{"id": "api-security", "name": "api-security", "includedChars": 20}],
        "context": "<retrieved_skill_context>safe reference</retrieved_skill_context>",
    }
    monkeypatch.setattr(skills_context_service, "build_turn_context", AsyncMock(return_value=context))
    try:
        await _safe_dispatch_turn_start(
            worker=worker,
            thread_id="thread-skills",
            turn_id=41,
            prompt="Secure the FastAPI route",
            model="gpt-6.1-sol",
            reasoning_effort="high",
            wt_str="F:/worktree",
            project_id="default",
        )
    finally:
        worker_manager.thread_map.clear()
        worker_manager.thread_map.update(original_mapping)

    assert len(worker.calls) == 1
    method, params = worker.calls[0]
    assert method == "turn/start"
    assert params["prompt"].startswith("<retrieved_skill_context>")
    assert params["prompt"].endswith("<user_request>\nSecure the FastAPI route\n</user_request>")
    assert params["input"] == [{"type": "text", "text": params["prompt"]}]


def test_skills_router_proxies_sanitized_service_contract():
    app = FastAPI()
    app.include_router(skills.router)
    client = TestClient(app)

    with (
        patch.object(skills_context_service, "stats", AsyncMock(return_value={"totalSkills": 1692, "status": "available"})),
        patch.object(skills_context_service, "search", AsyncMock(return_value=[{"id": "security", "name": "security"}])),
        patch.object(skills_context_service, "read", AsyncMock(return_value={"id": "security", "name": "security", "content": "instructions"})),
    ):
        assert client.get("/codex/skills/stats").json()["totalSkills"] == 1692
        assert client.get("/codex/skills/search", params={"query": "api security", "top_k": 3}).json()["results"][0]["id"] == "security"
        detail = client.get("/codex/skills/security").json()

    assert detail["content"] == "instructions"


def test_skills_router_returns_503_when_port_8008_is_unavailable():
    app = FastAPI()
    app.include_router(skills.router)
    client = TestClient(app)

    with patch.object(skills_context_service, "stats", AsyncMock(side_effect=SkillsServiceError("unavailable"))):
        response = client.get("/codex/skills/stats")

    assert response.status_code == 503
    assert response.json()["detail"] == "unavailable"


def test_skills_router_preserves_not_found_boundary():
    app = FastAPI()
    app.include_router(skills.router)
    client = TestClient(app)

    with patch.object(skills_context_service, "read", AsyncMock(side_effect=SkillNotFoundError("missing"))):
        response = client.get("/codex/skills/does-not-exist")

    assert response.status_code == 404
