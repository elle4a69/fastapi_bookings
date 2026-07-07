"""Recurring booking series routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.booking_series import BookingSeries as SeriesModel
from ...schemas.booking_series import BookingSeriesCreate, BookingSeriesOut

router = APIRouter(prefix="/api/admin/series", tags=["series"])


@router.get("", response_model=List[BookingSeriesOut])
def list_series(db: Session = Depends(get_db)) -> List[BookingSeriesOut]:
    series_list = db.query(SeriesModel).all()
    return [BookingSeriesOut.from_orm(s) for s in series_list]


@router.post("", response_model=BookingSeriesOut)
def create_series(
    series_in: BookingSeriesCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> BookingSeriesOut:
    series = SeriesModel(**series_in.dict())
    db.add(series)
    db.commit()
    db.refresh(series)
    return BookingSeriesOut.from_orm(series)


@router.get("/{series_id}", response_model=BookingSeriesOut)
def get_series(series_id: int, db: Session = Depends(get_db)) -> BookingSeriesOut:
    series = db.query(SeriesModel).filter(SeriesModel.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    return BookingSeriesOut.from_orm(series)
