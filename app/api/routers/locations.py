"""Location CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.location import Location as LocationModel
from ...schemas.location import (
    Location,
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
)


router = APIRouter()


@router.get("/locations", response_model=LocationListResponse, tags=["locations"])
def list_locations(
    params: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> dict:
    """Return a paginated list of locations."""
    query = db.query(LocationModel)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/locations", response_model=LocationResponse, tags=["locations"])
def create_location(
    location_in: LocationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new location."""
    location = LocationModel(**location_in.dict())
    db.add(location)
    db.commit()
    db.refresh(location)
    return {"ok": True, "data": location}


@router.get("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def get_location(location_id: int, db: Session = Depends(get_db)) -> dict:
    """Retrieve a single location by ID."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {"ok": True, "data": location}


@router.put("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def update_location(
    location_id: int,
    location_in: LocationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing location."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    for field, value in location_in.dict(exclude_unset=True).items():
        setattr(location, field, value)
    db.commit()
    db.refresh(location)
    return {"ok": True, "data": location}


@router.delete("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a location."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    db.delete(location)
    db.commit()
    return {"ok": True, "data": location}