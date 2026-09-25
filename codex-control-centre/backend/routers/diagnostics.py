from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from backend.database import get_db
from backend.middleware.auth import verify_auth
from backend.services.diagnostics_tool import (
    get_deep_diagnostics,
    check_telemetry_status
)

router = APIRouter(tags=["diagnostics"])


@router.get("/health")
def liveness_probe() -> Dict[str, Any]:
    """Public liveness endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/codex/diagnostics/readiness", dependencies=[Depends(verify_auth)])
@router.get("/codex/diagnostics/deep", dependencies=[Depends(verify_auth)])
async def readiness_probe(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Deep diagnostics & readiness probe across all subsystems."""
    return await get_deep_diagnostics(db)


@router.get("/codex/diagnostics/telemetry", dependencies=[Depends(verify_auth)])
async def telemetry_probe(collector_url: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Truthful SigNoz / OTLP telemetry reachability verification."""
    return await check_telemetry_status(signoz_url=collector_url)
