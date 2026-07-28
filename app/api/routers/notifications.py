
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..deps import get_current_admin, get_db, get_current_tenant
from ...models.tenant import Tenant
from ...core.pagination import paginate_query, pagination_params
from ...models.notification import (
    Notification as NotificationModel,
    NotificationTemplate as TemplateModel,
    ReminderRule as RuleModel,
)
from ...schemas.notification import (
    Notification,
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
    NotificationTemplate as TemplateSchema,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationTemplateListResponse,
    ReminderRule as RuleSchema,
    ReminderRuleCreate,
    ReminderRuleUpdate,
    ReminderRuleResponse,
    ReminderRuleListResponse,
)

router = APIRouter()


# --- Notification Endpoints ---

@router.get("/notifications", response_model=NotificationListResponse, tags=["notifications"])
def list_notifications(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of notifications."""
    query = db.query(NotificationModel).filter(NotificationModel.tenant_id == tenant.id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/notifications", response_model=NotificationResponse, tags=["notifications"])
def create_notification(
    notification_in: NotificationCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new notification."""
    notification_data = notification_in.dict()
    notification_data["tenant_id"] = tenant.id
    notification = NotificationModel(**notification_data)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"ok": True, "data": notification}


@router.put("/notifications/{notification_id}", response_model=NotificationResponse, tags=["notifications"])
def update_notification(
    notification_id: int,
    notification_in: NotificationUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing notification."""
    notification = db.query(NotificationModel).filter(
        NotificationModel.id == notification_id,
        NotificationModel.tenant_id == tenant.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    for field, value in notification_in.dict(exclude_unset=True).items():
        setattr(notification, field, value)
    db.commit()
    db.refresh(notification)
    return {"ok": True, "data": notification}


# --- Notification Template Endpoints ---

@router.get("/notification-templates", response_model=NotificationTemplateListResponse, tags=["notification-templates"])
def list_notification_templates(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of notification templates."""
    query = db.query(TemplateModel).filter(TemplateModel.tenant_id == tenant.id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/notification-templates", response_model=NotificationTemplateResponse, tags=["notification-templates"])
def create_notification_template(
    template_in: NotificationTemplateCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new notification template."""
    existing = db.query(TemplateModel).filter(TemplateModel.code == template_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Notification template code '{template_in.code}' already exists",
        )

    tmpl_data = template_in.dict()
    tmpl_data["tenant_id"] = tenant.id
    template = TemplateModel(**tmpl_data)
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"ok": True, "data": template}


@router.put("/notification-templates/{template_id}", response_model=NotificationTemplateResponse, tags=["notification-templates"])
def update_notification_template(
    template_id: int,
    template_in: NotificationTemplateUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a notification template."""
    template = db.query(TemplateModel).filter(
        TemplateModel.id == template_id,
        TemplateModel.tenant_id == tenant.id,
    ).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    for field, value in template_in.dict(exclude_unset=True).items():
        setattr(template, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Notification template code already exists",
        )
    db.refresh(template)
    return {"ok": True, "data": template}


@router.delete("/notification-templates/{template_id}", response_model=NotificationTemplateResponse, tags=["notification-templates"])
def delete_notification_template(
    template_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a notification template."""
    template = db.query(TemplateModel).filter(
        TemplateModel.id == template_id,
        TemplateModel.tenant_id == tenant.id,
    ).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"ok": True, "data": template}


# --- Reminder Rule Endpoints ---

@router.get("/reminder-rules", response_model=ReminderRuleListResponse, tags=["reminder-rules"])
def list_reminder_rules(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of reminder rules."""
    query = db.query(RuleModel).filter(RuleModel.tenant_id == tenant.id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/reminder-rules", response_model=ReminderRuleResponse, tags=["reminder-rules"])
def create_reminder_rule(
    rule_in: ReminderRuleCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a reminder rule."""
    rule_data = rule_in.dict()
    rule_data["tenant_id"] = tenant.id
    rule = RuleModel(**rule_data)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"ok": True, "data": rule}


@router.put("/reminder-rules/{rule_id}", response_model=ReminderRuleResponse, tags=["reminder-rules"])
def update_reminder_rule(
    rule_id: int,
    rule_in: ReminderRuleUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a reminder rule."""
    rule = db.query(RuleModel).filter(
        RuleModel.id == rule_id,
        RuleModel.tenant_id == tenant.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder rule not found")
    for field, value in rule_in.dict(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return {"ok": True, "data": rule}


@router.delete("/reminder-rules/{rule_id}", response_model=ReminderRuleResponse, tags=["reminder-rules"])
def delete_reminder_rule(
    rule_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a reminder rule."""
    rule = db.query(RuleModel).filter(
        RuleModel.id == rule_id,
        RuleModel.tenant_id == tenant.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True, "data": rule}
