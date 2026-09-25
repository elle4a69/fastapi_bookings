from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

codex_dir = Path(__file__).resolve().parent.parent
# Default repo_root to parent repository (fastapi_bookings) or allow dynamic parent resolution
repo_root = codex_dir.parent
default_db_path = codex_dir / "storage" / "codex.db"
if not (codex_dir / "storage").exists():
    default_db_path = codex_dir / "codex.db"

class Settings(BaseSettings):
    database_url: str = f"sqlite:///{default_db_path}"
    host: str = "127.0.0.1"
    port: int = 8100
    log_level: str = "INFO"
    token_secret: str = "local_secret"
    signoz_url: str = "http://localhost:8080"
    otlp_endpoint: str = "http://localhost:4318"
    otel_sdk_disabled: bool = False
    otel_service_name: str = "codex-control-centre"
    environment: str = "development"
    worktrees_dir: str = str(repo_root / "worktrees")
    repo_root: str = str(repo_root)

    # Codex App-Server Configuration (CAS-01)
    codex_bin_path: str = "codex"
    codex_transport: str = "stdio"
    codex_app_server_args: list[str] = ["app-server"]
    codex_worker_timeout_seconds: int = 60
    codex_api_key: Optional[str] = None

    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

settings = Settings()
