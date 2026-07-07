"""Mock notification routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.notification import Notification as NotificationModel
from ...schemas.notification import (
    Notification,
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
)


router = APIRouter()


@router.get("/notifications", response_model=NotificationListResponse, tags=["notifications"])
def list_notifications(
    params: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of notifications."""
    query = db.query(NotificationModel)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/notifications", response_model=NotificationResponse, tags=["notifications"])
def create_notification(
    notification_in: NotificationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a notification record."""
    notification = NotificationModel(**notification_in.dict())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"ok": True, "data": notification}


@router.put("/notifications/{notification_id}", response_model=NotificationResponse, tags=["notifications"])
def update_notification(
    notification_id: int,
    notification_in: NotificationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a notification's status."""
    notification = db.query(NotificationModel).filter(NotificationModel.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    for field, value in notification_in.dict(exclude_unset=True).items():
        setattr(notification, field, value)
    db.commit()
    db.refresh(notification)
    return {"ok": True, "data": notification}