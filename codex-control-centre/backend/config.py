import json
import sys
from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

codex_dir = Path(__file__).resolve().parent.parent
# Isolate repository root to codex_dir itself (or dedicated sandbox) to prevent
# worktree operations from escaping into massive parent monorepos.
repo_root = codex_dir
default_db_path = codex_dir / "codex.db"
default_worktrees_dir = codex_dir / "worktrees"
skills_rag_mcp_bridge_path = codex_dir / "backend" / "services" / "skills_rag_mcp_bridge.py"

class Settings(BaseSettings):
    database_url: str = f"sqlite:///{default_db_path.as_posix()}"
    host: str = "127.0.0.1"
    port: int = 4500
    log_level: str = "INFO"
    # Keep compatibility with the existing local frontend. The EventSource
    # route no longer accepts this credential in its URL; it is exchanged for
    # a short-lived, single-use ticket by the authenticated API client.
    token_secret: str = "local_secret"
    signoz_url: str = "http://localhost:8080"
    otlp_endpoint: str = "http://localhost:4318"
    otel_sdk_disabled: bool = True
    otel_service_name: str = "codex-control-centre"
    environment: str = "development"
    worktrees_dir: str = str(default_worktrees_dir)
    repo_root: str = str(codex_dir)
    allowed_boundaries: list[str] = [str(codex_dir)]
    sse_ticket_ttl_seconds: int = 60

    # Supervisor v2 deployment binding.  These values are deliberately
    # server-owned and have no browser/request equivalent.
    codex_supervisor_configured_project_id: Optional[str] = None
    codex_supervisor_configured_project_root: Optional[str] = None
    codex_supervisor_configured_project_name: Optional[str] = None
    codex_supervisor_configured_default_branch: Optional[str] = None

    # Codex App-Server Configuration (CAS-01)
    codex_bin_path: str = "codex"
    codex_transport: str = "stdio"
    codex_app_server_args: list[str] = [
        "app-server",
        "-c", "mcp_servers.mcp-skillset.enabled=false",
        # Register the lightweight native tool surface without importing the
        # heavyweight index stack. The bridge delegates to the hot HTTP daemon.
        "-c", f"mcp_servers.skills-rag.command={json.dumps(sys.executable)}",
        "-c", f"mcp_servers.skills-rag.args={json.dumps([str(skills_rag_mcp_bridge_path)])}",
        "-c", "mcp_servers.skills-rag.enabled=true",
        "-c", "mcp_servers.skills-rag.startup_timeout_sec=10.0",
        "-c", "mcp_servers.skills-rag.tool_timeout_sec=30.0",
        "-c", "mcp_servers.main-context-document.enabled=false",
        "-c", "mcp_servers.livekit-docs.enabled=false",
        "-c", "mcp_servers.playwright.enabled=false",
        "-c", "mcp_servers.agent-context.enabled=false",
        "-c", "mcp_servers.node_repl.enabled=false",
    ]
    codex_worker_timeout_seconds: int = 60
    codex_api_key: Optional[str] = None

    # Local hybrid Skills RAG service. Retrieved skill content is bounded before
    # it is attached to a Codex turn so the full library never enters context.
    skills_rag_url: str = "http://127.0.0.1:8008"
    skills_rag_enabled: bool = True
    skills_rag_timeout_seconds: float = 10.0
    skills_rag_top_k: int = 3
    skills_rag_max_skill_chars: int = 6000
    skills_rag_max_context_chars: int = 16000

    @field_validator("database_url", mode="before")
    @classmethod
    def _validate_database_url(cls, v: object) -> str:
        # Prevent picking up parent project's PostgreSQL DATABASE_URL.
        # Codex DB must unambiguously resolve to codex.db (SQLite WAL mode).
        if isinstance(v, str) and (v.startswith("sqlite") or "codex.db" in v):
            return v
        return f"sqlite:///{default_db_path.as_posix()}"

    @field_validator("repo_root", mode="after")
    @classmethod
    def _validate_repo_root(cls, v: str) -> str:
        p = Path(v).resolve()
        return str(p)

    @field_validator("worktrees_dir", mode="after")
    @classmethod
    def _validate_worktrees_dir(cls, v: str) -> str:
        p = Path(v).resolve()
        return str(p)

    @field_validator("allowed_boundaries", mode="before")
    @classmethod
    def _validate_allowed_boundaries(cls, v: object) -> list[str]:
        if isinstance(v, str):
            import json
            v_str = v.strip()
            if v_str.startswith("["):
                try:
                    return [str(Path(p).resolve()) for p in json.loads(v_str)]
                except Exception:
                    pass
            return [str(Path(p.strip()).resolve()) for p in v_str.split(",") if p.strip()]
        if isinstance(v, (list, tuple)):
            return [str(Path(p).resolve()) for p in v if str(p).strip()]
        return [str(codex_dir)]

    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

settings = Settings()
