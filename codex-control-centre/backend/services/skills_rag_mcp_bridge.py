"""Lightweight MCP stdio bridge for the always-on Skills RAG HTTP daemon.

The bridge intentionally imports only Python's standard library.  Heavy model,
ChromaDB, and graph initialization remains owned by the daemon on port 8008.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib import error, parse, request


SERVER_NAME = "skills-rag-http-bridge"
SERVER_VERSION = "1.0.0"
DEFAULT_BASE_URL = "http://127.0.0.1:8008"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_QUERY_CHARS = 500
MAX_SKILL_NAME_CHARS = 200
MAX_RESULTS = 15
SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)


TOOLS = [
    {
        "name": "find",
        "description": (
            "Search the always-on Skills RAG index using hybrid semantic and graph retrieval. "
            "Use this before implementation when a reusable skill may apply. Returns only compact "
            "skill metadata and relevance scores; call the skill tool with a selected result to load "
            "its complete instructions. This tool is read-only and does not reindex or modify skills."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_QUERY_CHARS,
                    "description": (
                        "A concise technical capability query, for example "
                        "'FastAPI authorization tenant isolation'. Do not include secrets or PII."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_RESULTS,
                    "default": 5,
                    "description": "Maximum number of ranked matches to return, from 1 through 15.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "skill",
        "description": (
            "Load the complete SKILL.md instructions for one exact skill returned by find. Use this "
            "only after selecting a relevant result, and read the returned content completely before "
            "acting. The operation is read-only and returns skill metadata plus the full indexed text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_SKILL_NAME_CHARS,
                    "description": (
                        "Exact skill ID or name returned by find, for example 'api-security-best-practices'."
                    ),
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


class BridgeError(RuntimeError):
    """Expected bridge failure that can be returned safely to an agent."""


def _base_url() -> str:
    value = os.getenv("SKILLS_RAG_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise BridgeError("SKILLS_RAG_URL must be an HTTP(S) URL without embedded credentials.")
    return value


def _timeout_seconds() -> float:
    raw = os.getenv("SKILLS_RAG_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise BridgeError("SKILLS_RAG_TIMEOUT_SECONDS must be numeric.") from exc
    if not 0.1 <= timeout <= 60.0:
        raise BridgeError("SKILLS_RAG_TIMEOUT_SECONDS must be between 0.1 and 60 seconds.")
    return timeout


def _http_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{_base_url()}{path}?{parse.urlencode(params)}"
    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}"})
    try:
        with request.urlopen(req, timeout=_timeout_seconds()) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as exc:
        if exc.code == 404:
            raise BridgeError("The requested skill was not found in the port 8008 index.") from exc
        raise BridgeError(f"Skills RAG returned HTTP {exc.code}.") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise BridgeError(
            "Skills RAG is unavailable. Confirm the always-on daemon is listening on port 8008."
        ) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BridgeError("Skills RAG returned malformed JSON.") from exc
    if not isinstance(data, dict):
        raise BridgeError("Skills RAG returned an unexpected response shape.")
    return data


def _require_string(arguments: dict[str, Any], key: str, max_chars: int) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BridgeError(f"'{key}' must be a non-empty string.")
    value = value.strip()
    if len(value) > max_chars:
        raise BridgeError(f"'{key}' must be at most {max_chars} characters.")
    return value


def call_tool(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return _tool_error("Tool arguments must be a JSON object.")

    try:
        if name == "find":
            query = _require_string(arguments, "query", MAX_QUERY_CHARS)
            limit = arguments.get("limit", 5)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULTS:
                raise BridgeError("'limit' must be an integer from 1 through 15.")
            unexpected = set(arguments) - {"query", "limit"}
            if unexpected:
                raise BridgeError(f"Unexpected argument(s): {', '.join(sorted(unexpected))}.")
            data = _http_get("/api/skills/search", {"query": query})
            results = data.get("results")
            if not isinstance(results, list):
                raise BridgeError("Skills RAG search response did not contain a results list.")
            return _tool_success({"query": query, "count": min(len(results), limit), "results": results[:limit]})

        if name == "skill":
            skill_name = _require_string(arguments, "name", MAX_SKILL_NAME_CHARS)
            unexpected = set(arguments) - {"name"}
            if unexpected:
                raise BridgeError(f"Unexpected argument(s): {', '.join(sorted(unexpected))}.")
            data = _http_get("/api/skills/read", {"name": skill_name})
            return _tool_success(data)

        return _tool_error(f"Unknown tool '{name}'. Available tools: find, skill.")
    except BridgeError as exc:
        return _tool_error(str(exc))
    except Exception:
        return _tool_error("Unexpected bridge failure. Check the bridge stderr log for details.")


def _tool_success(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "isError": False,
    }


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Error: {message}"}], "isError": True}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request")

    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _jsonrpc_error(request_id, -32600, "Invalid Request")
    if method.startswith("notifications/"):
        return None

    if method == "initialize":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        requested_version = params.get("protocolVersion")
        protocol_version = (
            requested_version if requested_version in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        )
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "ping":
        return _jsonrpc_result(request_id, {})
    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _jsonrpc_error(request_id, -32602, "Invalid tools/call parameters")
        return _jsonrpc_result(request_id, call_tool(params["name"], params.get("arguments", {})))
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve() -> int:
    for raw_line in sys.stdin.buffer:
        if not raw_line.strip():
            continue
        try:
            message = json.loads(raw_line)
            response = handle_message(message)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
        except Exception as exc:
            print(f"{SERVER_NAME}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            response = _jsonrpc_error(None, -32603, "Internal error")
        if response is not None:
            encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            sys.stdout.buffer.write(encoded + b"\n")
            sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
