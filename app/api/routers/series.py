"""Recurring booking series routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant
from ...models.booking_series import BookingSeries as SeriesModel
from ...models.tenant import Tenant
from ...schemas.booking_series import BookingSeriesCreate, BookingSeriesOut

router = APIRouter(prefix="/api/admin/series", tags=["series"])


@router.get("", response_model=List[BookingSeriesOut])
def list_series(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> List[BookingSeriesOut]:
    series_list = db.query(SeriesModel).filter(SeriesModel.tenant_id == tenant.id).all()
    return [BookingSeriesOut.from_orm(s) for s in series_list]


@router.post("", response_model=BookingSeriesOut)
def create_series(
    series_in: BookingSeriesCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> BookingSeriesOut:
    series_dict = series_in.dict()
    series_dict["tenant_id"] = tenant.id
    series = SeriesModel(**series_dict)
    db.add(series)
    db.commit()
    db.refresh(series)
    return BookingSeriesOut.from_orm(series)


@router.get("/{series_id}", response_model=BookingSeriesOut)
def get_series(
    series_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> BookingSeriesOut:
    series = db.query(SeriesModel).filter(
        SeriesModel.id == series_id,
        SeriesModel.tenant_id == tenant.id
    ).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    return BookingSeriesOut.from_orm(series)
