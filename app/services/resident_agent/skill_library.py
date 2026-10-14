"""Bounded Skills RAG integration for the resident development agent.

The resident agent never scans or reads host files. Discovery and content
retrieval are delegated to the read-only Skills RAG service on loopback port
8008, and reads accept only indexed skill identifiers.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

_VALID_SKILL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TECHNICAL_TERMS = {
    "accessibility", "agent", "agents", "ai", "alembic", "api", "async",
    "authentication", "backend", "booking", "cache",
    "calendar", "chatwoot", "cli", "cloud", "codex", "concurrency",
    "context", "css", "database", "debug", "docker",
    "documentation", "embedding", "fastapi", "frontend", "git", "github",
    "graph", "graphql", "html", "http", "index", "javascript", "jwt",
    "latency", "livekit", "llm", "logging", "memory", "mcp", "migration",
    "network", "oauth", "observability", "openai", "performance",
    "permissions", "plugin", "postgres", "privacy", "prompt", "pytest",
    "python", "rag", "react", "refactor", "retrieval", "schema", "security",
    "semantic", "skills", "sms", "sql", "sqlite", "sse", "telemetry",
    "tenant", "testing", "typescript", "ui", "vector", "vite", "websocket",
    "worker",
}


def derive_safe_search_query(raw_text: str) -> str:
    """Derive an allowlisted technical query without forwarding caller text."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,31}", raw_text.lower())
    selected: list[str] = []
    for token in tokens:
        normalized = token.replace("_", "-")
        if (
            normalized in _TECHNICAL_TERMS
            and normalized != "codex"
            and normalized not in selected
        ):
            selected.append(normalized)
        if len(selected) >= 12:
            break
    if not selected:
        selected = ["software", "engineering", "implementation"]
    return "codex " + " ".join(selected)


class SkillsServiceError(RuntimeError):
    """The bounded Skills RAG service could not fulfil a request."""


class SkillNotFoundError(FileNotFoundError, SkillsServiceError):
    """The requested identifier is not present in the live Skills RAG index."""


class InvalidSkillIdError(ValueError):
    """The supplied value is not an indexed skill identifier."""


class SkillLibrary:
    """Small synchronous client for the read-only Skills RAG HTTP contract."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("SKILLS_RAG_URL")
            or "http://127.0.0.1:8008"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("SKILLS_RAG_TIMEOUT_SECONDS", "5")
        )
        self._transport = transport

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Dict[str, Any]:
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(f"{self.base_url}{path}", params=params)
                if response.status_code == 404:
                    raise SkillNotFoundError("Skill not found in the live index")
                response.raise_for_status()
                payload = response.json()
        except SkillNotFoundError:
            raise
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
            raise SkillsServiceError("Local Skills RAG service is unavailable") from exc
        if not isinstance(payload, dict):
            raise SkillsServiceError("Skills RAG returned an invalid response")
        return payload

    @staticmethod
    def _validate_skill_id(skill_id: str) -> str:
        candidate = skill_id.strip()
        if not _VALID_SKILL_ID.fullmatch(candidate):
            raise InvalidSkillIdError("A valid indexed skill identifier is required")
        return candidate

    @staticmethod
    def _summary(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise SkillsServiceError("Skills RAG returned an invalid skill record")
        skill_id = str(value.get("id") or value.get("name") or "")
        if not skill_id:
            raise SkillsServiceError("Skills RAG returned a skill without an identifier")
        summary: Dict[str, Any] = {
            "skill_id": skill_id,
            "name": str(value.get("name") or skill_id),
            "description": str(value.get("description") or ""),
            "tags": [
                str(tag) for tag in value.get("tags", []) if isinstance(tag, str)
            ],
        }
        if isinstance(value.get("score"), (int, float)):
            summary["score"] = float(value["score"])
        return summary

    def find_relevant_skills(
        self,
        query: str,
        top_k: int = 3,
        *,
        fail_open: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search the bounded index; background advisory callers may degrade empty."""
        try:
            safe_query = derive_safe_search_query(query)
            payload = self._get(
                "/api/skills/search",
                params={"query": safe_query},
            )
            results = payload.get("results")
            if not isinstance(results, list):
                raise SkillsServiceError("Skills RAG returned invalid search results")
            limit = max(1, min(top_k, 15))
            return [self._summary(item) for item in results[:limit]]
        except SkillsServiceError:
            if not fail_open:
                raise
            logger.warning(
                "Skills RAG discovery unavailable; continuing without resident skill context"
            )
            return []

    def read_skill(self, skill_id: str) -> str:
        """Read only a skill selected by opaque identifier from the live index."""
        safe_id = self._validate_skill_id(skill_id)
        payload = self._get("/api/skills/read", params={"name": safe_id})
        content = payload.get("content")
        if not isinstance(content, str):
            raise SkillsServiceError("Skills RAG returned invalid skill content")
        return content

    def get_library_stats(self) -> Dict[str, Any]:
        payload = self._get("/api/skills/stats")
        return {
            "total_skills": int(payload.get("total_skills") or 0),
            "indexed_count": int(payload.get("indexed_count") or 0),
            "is_available": True,
            "source": self.base_url,
        }


skill_library = SkillLibrary()
