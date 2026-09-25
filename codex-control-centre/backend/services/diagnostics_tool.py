import os
import httpx
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.event_service import broker
from backend.services.worker_manager import worker_manager


class DiagnosticQuery(BaseModel):
    query: str = Field(..., max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(50, le=100)


class SigNozDiagnosticsTool:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or getattr(settings, "signoz_url", "http://localhost:3301")).rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=2.0)

    def _sanitize_query(self, query: str) -> str:
        # Prompt-injection defense wrapper
        # Remove any system prompt leakage or suspicious command injections
        query = re.sub(
            r'(?i)(ignore previous|system prompt|system message|bypass|inject|drop table|select \*)',
            '',
            query
        )
        return query.strip()

    async def check_connectivity(self, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Truthfully probes the configured SigNoz/OTLP endpoint.
        Returns connected=False and explicit offline status if unreachable.
        Strictly NEVER fabricates synthetic telemetry claims.
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 1. Try GET /api/v1/health (SigNoz UI / Query Service)
                try:
                    resp = await client.get(f"{self.base_url}/api/v1/health")
                except Exception:
                    resp = None

                # 2. If health path failed or 404, probe the collector base directly
                if resp is None or resp.status_code == 404:
                    resp = await client.get(f"{self.base_url}/")

                if resp.status_code < 500:
                    return {
                        "connected": True,
                        "collector_url": self.base_url,
                        "status": "Connected",
                        "status_code": resp.status_code
                    }
                return {
                    "connected": False,
                    "collector_url": self.base_url,
                    "status": "Not connected (No active telemetry collector)",
                    "status_code": resp.status_code
                }
        except Exception as exc:
            return {
                "connected": False,
                "collector_url": self.base_url,
                "status": "Not connected (No active telemetry collector)",
                "error": str(exc)
            }

    async def search_errors(
        self,
        service: str,
        query: str = "",
        limit: int = 50,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        limit = min(limit, 100)
        query = self._sanitize_query(query)
        try:
            params = {"service": service, "query": query, "limit": limit}
            if start_time:
                params["start"] = start_time.isoformat()
            if end_time:
                params["end"] = end_time.isoformat()
            resp = await self.client.get("/api/v1/logs", params=params)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception:
            pass
        return []

    async def get_trace(self, trace_id: str) -> Dict[str, Any]:
        trace_id = self._sanitize_query(trace_id)
        try:
            resp = await self.client.get(f"/api/v1/traces/{trace_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {"trace_id": trace_id, "spans": []}

    async def search_logs(
        self,
        query: str,
        limit: int = 50,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        limit = min(limit, 100)
        query = self._sanitize_query(query)
        try:
            params = {"query": query, "limit": limit}
            if start_time:
                params["start"] = start_time.isoformat()
            if end_time:
                params["end"] = end_time.isoformat()
            resp = await self.client.get("/api/v1/logs", params=params)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception:
            pass
        return []

    async def get_error_rate(self, service: str, window_minutes: int = 60) -> float:
        service = self._sanitize_query(service)
        try:
            resp = await self.client.get(
                "/api/v1/metrics/error_rate",
                params={"service": service, "window": window_minutes}
            )
            if resp.status_code == 200:
                return float(resp.json().get("error_rate", 0.0))
        except Exception:
            pass
        return 0.0


def check_database_health(db: Session) -> Dict[str, Any]:
    """Inspects database connectivity and schema tables."""
    try:
        db.execute(text("SELECT 1"))
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        return {
            "status": "healthy",
            "connected": True,
            "tables": table_names,
            "table_count": len(table_names)
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(exc)
        }


def check_event_broker_health() -> Dict[str, Any]:
    """Inspects EventBroker subscriber queues and buffered events."""
    active_queues = sum(len(q_set) for q_set in broker.subscribers.values())
    total_buffered = sum(len(h_deque) for h_deque in broker.history.values())
    active_threads = len(broker.subscribers)
    return {
        "status": "healthy",
        "active_subscriber_queues": active_queues,
        "active_threads": active_threads,
        "total_buffered_events": total_buffered
    }


def check_worker_status() -> Dict[str, Any]:
    """Inspects Worker process manager and supervisor status."""
    worker = worker_manager.worker
    is_running = bool(worker and worker.running and worker.process and worker.process.returncode is None)
    pid = worker.process.pid if (worker and worker.process) else None
    return {
        "status": "running" if is_running else "idle",
        "running": is_running,
        "pid": pid,
        "command": worker_manager.command
    }


def check_worktree_storage() -> Dict[str, Any]:
    """Inspects accessibility and writability of worktree storage directory."""
    wt_dir_str = getattr(settings, "worktrees_dir", None)
    if not wt_dir_str:
        repo_root = Path(settings.database_url.replace("sqlite:///", "")).parent.resolve()
        wt_dir = (repo_root / "worktrees").resolve()
    else:
        wt_dir = Path(wt_dir_str).resolve()

    exists = wt_dir.exists()
    writable = False
    if exists:
        writable = os.access(wt_dir, os.W_OK)
    else:
        try:
            wt_dir.mkdir(parents=True, exist_ok=True)
            exists = True
            writable = os.access(wt_dir, os.W_OK)
        except Exception:
            writable = False

    return {
        "status": "healthy" if writable else "degraded",
        "path": str(wt_dir),
        "exists": exists,
        "writable": writable
    }


async def check_telemetry_status(signoz_url: Optional[str] = None) -> Dict[str, Any]:
    """Truthfully probes the SigNoz / OTLP telemetry collector status and integrates OTel engine data."""
    target_url = signoz_url or getattr(settings, "otlp_endpoint", "http://localhost:4318")
    tool = SigNozDiagnosticsTool(base_url=target_url)
    res = await tool.check_connectivity()
    from backend.services.telemetry import get_telemetry_status_data
    telemetry_data = get_telemetry_status_data()
    res.update(telemetry_data)
    return res


async def get_deep_diagnostics(db: Session) -> Dict[str, Any]:
    """Gathers comprehensive subsystem health statuses."""
    db_health = check_database_health(db)
    broker_health = check_event_broker_health()
    worker_health = check_worker_status()
    wt_health = check_worktree_storage()
    telemetry_health = await check_telemetry_status()

    is_overall_healthy = (
        db_health.get("status") == "healthy" and
        broker_health.get("status") == "healthy" and
        wt_health.get("writable", False)
    )

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "database": db_health,
            "event_broker": broker_health,
            "worker": worker_health,
            "worktree_storage": wt_health,
            "telemetry": telemetry_health
        }
    }

