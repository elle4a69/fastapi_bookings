"""Admin schedule management routes.

CRUD endpoints for managing working hours, special day overrides,
blocked times and reserved times for providers.
"""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models import (
    BlockedTime,
    Provider as ProviderModel,
    Location as LocationModel,
    ProviderSpecialDay,
    ProviderWorkDay,
    ReservedTime,
)
from ...models import Booking as BookingModel
from ...schemas.schedule import (
    BlockedTimeCreate,
    BlockedTimeOut,
    BlockedTimeUpdate,
    ProviderSpecialDayCreate,
    ProviderSpecialDayOut,
    ProviderSpecialDayUpdate,
    ProviderWorkDayCreate,
    ProviderWorkDayOut,
    ProviderWorkDayUpdate,
    ReservedTimeCreate,
    ReservedTimeOut,
    ReservedTimeUpdate,
    WorkloadSummary,
)

router = APIRouter(prefix="/api/admin/schedule", tags=["schedule"])


def get_provider_or_none(db: Session, provider_id: int | None) -> ProviderModel | None:
    if provider_id is None:
        return None
    return db.query(ProviderModel).filter(ProviderModel.id == provider_id).first()


def get_location_or_none(db: Session, location_id: int | None) -> LocationModel | None:
    if location_id is None:
        return None
    return db.query(LocationModel).filter(LocationModel.id == location_id).first()


@router.get("/workdays", response_model=List[ProviderWorkDayOut])
def list_workdays(db: Session = Depends(get_db)) -> list[ProviderWorkDay]:
    """Return all provider workday rules."""
    return db.query(ProviderWorkDay).all()


@router.post("/workdays", response_model=ProviderWorkDayOut, status_code=status.HTTP_201_CREATED)
def create_workday(
    workday_in: ProviderWorkDayCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ProviderWorkDay:
    """Create a new provider workday rule."""
    if workday_in.provider_id and not get_provider_or_none(db, workday_in.provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if workday_in.location_id and not get_location_or_none(db, workday_in.location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    workday = ProviderWorkDay(**workday_in.dict())
    db.add(workday)
    db.commit()
    db.refresh(workday)
    return workday


@router.put("/workdays/{workday_id}", response_model=ProviderWorkDayOut)
def update_workday(
    workday_id: int,
    workday_in: ProviderWorkDayUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ProviderWorkDay:
    """Update an existing provider workday rule."""
    workday = db.query(ProviderWorkDay).filter(ProviderWorkDay.id == workday_id).first()
    if not workday:
        raise HTTPException(status_code=404, detail="Workday not found")
    if workday_in.provider_id is not None and not get_provider_or_none(db, workday_in.provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if workday_in.location_id is not None and not get_location_or_none(db, workday_in.location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    for field, value in workday_in.dict(exclude_unset=True).items():
        setattr(workday, field, value)
    db.commit()
    db.refresh(workday)
    return workday


@router.delete("/workdays/{workday_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_workday(
    workday_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    workday = db.query(ProviderWorkDay).filter(ProviderWorkDay.id == workday_id).first()
    if not workday:
        raise HTTPException(status_code=404, detail="Workday not found")
    db.delete(workday)
    db.commit()


@router.get("/special-days", response_model=List[ProviderSpecialDayOut])
def list_special_days(db: Session = Depends(get_db)) -> list[ProviderSpecialDay]:
    """Return all special day overrides."""
    return db.query(ProviderSpecialDay).all()


@router.post("/special-days", response_model=ProviderSpecialDayOut, status_code=status.HTTP_201_CREATED)
def create_special_day(
    special_day_in: ProviderSpecialDayCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ProviderSpecialDay:
    """Create a special day override."""
    if special_day_in.provider_id and not get_provider_or_none(db, special_day_in.provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if special_day_in.location_id and not get_location_or_none(db, special_day_in.location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    day = ProviderSpecialDay(**special_day_in.dict())
    db.add(day)
    db.commit()
    db.refresh(day)
    return day


@router.put("/special-days/{day_id}", response_model=ProviderSpecialDayOut)
def update_special_day(
    day_id: int,
    special_in: ProviderSpecialDayUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ProviderSpecialDay:
    day = db.query(ProviderSpecialDay).filter(ProviderSpecialDay.id == day_id).first()
    if not day:
        raise HTTPException(status_code=404, detail="Special day not found")
    if special_in.provider_id is not None and not get_provider_or_none(db, special_in.provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    for field, value in special_in.dict(exclude_unset=True).items():
        setattr(day, field, value)
    db.commit()
    db.refresh(day)
    return day


@router.delete("/special-days/{day_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_special_day(day_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> None:
    day = db.query(ProviderSpecialDay).filter(ProviderSpecialDay.id == day_id).first()
    if not day:
        raise HTTPException(status_code=404, detail="Special day not found")
    db.delete(day)
    db.commit()


@router.get("/blocked-times", response_model=List[BlockedTimeOut])
def list_blocked_times(db: Session = Depends(get_db)) -> list[BlockedTime]:
    return db.query(BlockedTime).all()


@router.post("/blocked-times", response_model=BlockedTimeOut, status_code=status.HTTP_201_CREATED)
def create_blocked_time(
    block_in: BlockedTimeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> BlockedTime:
    if block_in.provider_id and not get_provider_or_none(db, block_in.provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    block = BlockedTime(**block_in.dict())
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.put("/blocked-times/{block_id}", response_model=BlockedTimeOut)
def update_blocked_time(
    block_id: int,
    block_in: BlockedTimeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> BlockedTime:
    block = db.query(BlockedTime).filter(BlockedTime.id == block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Blocked time not found")
    for field, value in block_in.dict(exclude_unset=True).items():
        setattr(block, field, value)
    db.commit()
    db.refresh(block)
    return block


@router.delete("/blocked-times/{block_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_blocked_time(block_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> None:
    block = db.query(BlockedTime).filter(BlockedTime.id == block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Blocked time not found")
    db.delete(block)
    db.commit()


@router.get("/reserved-times", response_model=List[ReservedTimeOut])
def list_reserved_times(db: Session = Depends(get_db)) -> list[ReservedTime]:
    return db.query(ReservedTime).all()


@router.post("/reserved-times", response_model=ReservedTimeOut, status_code=status.HTTP_201_CREATED)
def create_reserved_time(
    reserved_in: ReservedTimeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ReservedTime:
    reservation = ReservedTime(**reserved_in.dict())
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@router.put("/reserved-times/{reserved_id}", response_model=ReservedTimeOut)
def update_reserved_time(
    reserved_id: int,
    reserved_in: ReservedTimeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> ReservedTime:
    reservation = db.query(ReservedTime).filter(ReservedTime.id == reserved_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reserved time not found")
    for field, value in reserved_in.dict(exclude_unset=True).items():
        setattr(reservation, field, value)
    db.commit()
    db.refresh(reservation)
    return reservation


@router.delete("/reserved-times/{reserved_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_reserved_time(reserved_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> None:
    reservation = db.query(ReservedTime).filter(ReservedTime.id == reserved_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reserved time not found")
    db.delete(reservation)
    db.commit()


@router.get("/workload", response_model=WorkloadSummary)
def get_workload(db: Session = Depends(get_db)) -> WorkloadSummary:
    """Return counts of bookings within the next day, week and month."""
    now = datetime.utcnow()
    return WorkloadSummary(
        day=db.query(BookingModel).filter(BookingModel.start_time >= now, BookingModel.start_time < now + timedelta(days=1)).count(),
        week=db.query(BookingModel).filter(BookingModel.start_time >= now, BookingModel.start_time < now + timedelta(days=7)).count(),
        month=db.query(BookingModel).filter(BookingModel.start_time >= now, BookingModel.start_time < now + timedelta(days=30)).count(),
    )
