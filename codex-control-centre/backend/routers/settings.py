from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.boundary_service import (
    list_boundaries,
    add_boundary,
    remove_boundary,
)
from backend.services.telemetry_settings_service import (
    get_telemetry_settings,
    update_telemetry_settings,
    test_endpoint_connectivity,
)

router = APIRouter(prefix="", tags=["settings"])


# Schemas
class BoundaryCreate(BaseModel):
    path: str
    name: Optional[str] = None


class BoundaryResponse(BaseModel):
    id: str
    path: str
    name: str
    is_default: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TelemetrySettingsUpdate(BaseModel):
    signoz_url: str
    otlp_endpoint: str
    enabled: bool


class TelemetryTestRequest(BaseModel):
    endpoint: str


# Endpoints: Boundaries
@router.get("/boundaries", response_model=List[BoundaryResponse])
def get_boundaries_endpoint(db: Session = Depends(get_db)):
    return list_boundaries(db)


@router.post("/boundaries", response_model=BoundaryResponse)
def add_boundary_endpoint(payload: BoundaryCreate, db: Session = Depends(get_db)):
    return add_boundary(db, payload.path, payload.name)


@router.delete("/boundaries")
def delete_boundary_query_endpoint(
    id: Optional[str] = None,
    path: Optional[str] = None,
    db: Session = Depends(get_db),
):
    target = id or path
    if not target:
        raise HTTPException(status_code=400, detail="Must provide 'id' or 'path' to delete")
    return remove_boundary(db, target)


@router.delete("/boundaries/{boundary_id_or_path:path}")
def delete_boundary_endpoint(boundary_id_or_path: str, db: Session = Depends(get_db)):
    import urllib.parse
    unquoted = urllib.parse.unquote(boundary_id_or_path)
    return remove_boundary(db, unquoted)


# Endpoints: Telemetry
@router.get("/telemetry")
async def get_telemetry_settings_endpoint(db: Session = Depends(get_db)):
    return await get_telemetry_settings(db)


@router.put("/telemetry")
def update_telemetry_settings_endpoint(payload: TelemetrySettingsUpdate, db: Session = Depends(get_db)):
    return update_telemetry_settings(
        db,
        signoz_url=payload.signoz_url,
        otlp_endpoint=payload.otlp_endpoint,
        enabled=payload.enabled,
    )


@router.post("/telemetry/test")
async def test_telemetry_endpoint(payload: TelemetryTestRequest):
    return await test_endpoint_connectivity(payload.endpoint)
