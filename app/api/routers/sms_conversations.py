from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob, SmsConversationEvent, SmsAiJob
from ...schemas.sms_conversation import SmsConversationResponse
from ...schemas.sms_message import SmsMessageCreate, SmsMessageResponse
from ...services.sms.outbound_service import enqueue_outbound_message_transactional

router = APIRouter(prefix="/sms/conversations", tags=["sms-conversations"])

@router.get("", response_model=List[SmsConversationResponse])
async def list_conversations(
    provider_id: Optional[int] = None,
    sms_account_id: Optional[int] = None,
    unread_only: bool = False,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(SmsConversation).filter(SmsConversation.tenant_id == tenant.id)
    
    if provider_id is not None:
        query = query.filter(SmsConversation.provider_id == provider_id)
    if sms_account_id is not None:
        query = query.filter(SmsConversation.sms_account_id == sms_account_id)
    if unread_only:
        query = query.filter(SmsConversation.unread_count > 0)
        
    conversations = query.order_by(SmsConversation.last_activity_at.desc()).all()
    
    # Map to response format
    result = []
    for conv in conversations:
        client_name = conv.client.name if conv.client else None
        result.append(SmsConversationResponse(
            id=conv.id,
            tenant_id=conv.tenant_id,
            provider_id=conv.provider_id,
            sms_account_id=conv.sms_account_id,
            customer_address=conv.customer_address,
            client_id=conv.client_id,
            client_name=client_name,
            state=conv.state,
            unread_count=conv.unread_count,
            last_activity_at=conv.last_activity_at,
            created_at=conv.created_at,
            updated_at=conv.updated_at
        ))
    return result

@router.get("/jobs", response_model=List[dict])
async def list_outbound_jobs(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Fetch jobs that belong to the accounts of this tenant
    jobs = db.query(SmsOutboundJob).join(
        SmsAccount, SmsAccount.id == SmsOutboundJob.sms_account_id
    ).filter(
        SmsAccount.tenant_id == tenant.id
    ).order_by(SmsOutboundJob.created_at.desc()).limit(50).all()
    
    return [
        {
            "id": job.id,
            "message_id": job.message_id,
            "sms_account_id": job.sms_account_id,
            "status": job.status,
            "retry_count": job.retry_count,
            "error_log": job.error_log,
            "created_at": job.created_at
        }
        for job in jobs
    ]

@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_200_OK)
async def retry_outbound_job(
    job_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    job = db.query(SmsOutboundJob).join(
        SmsAccount, SmsAccount.id == SmsOutboundJob.sms_account_id
    ).filter(
        SmsOutboundJob.id == job_id,
        SmsAccount.tenant_id == tenant.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Outbound job not found.")
        
    job.status = "PENDING"
    job.retry_count = 0
    job.error_log = None
    
    # Also reset the message status to queued
    message = db.query(SmsMessage).filter(SmsMessage.id == job.message_id).first()
    if message:
        message.status = "queued"
        
    db.commit()
    return {"status": "success", "detail": "Job marked for retry."}

@router.post("/messages/{message_id}/approve", response_model=SmsMessageResponse)
async def approve_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Retrieve message, checking tenant boundary
    message = db.query(SmsMessage).filter(
        SmsMessage.id == message_id,
        SmsMessage.tenant_id == tenant.id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")
        
    if message.status != "draft":
        # Already approved/processed; return current message (idempotency!)
        return message

    # Mark message as queued for outbound send
    message.direction = "outbound"
    message.status = "queued"
    
    # Create the SmsOutboundJob record transactionally
    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=message.sms_account_id,
        status="PENDING",
        retry_count=0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(job)

    # Log approval event
    event = SmsConversationEvent(
        conversation_id=message.conversation_id,
        type="draft_approved",
        meta={"message_id": message.id}
    )
    db.add(event)
    db.commit()
    db.refresh(message)
    
    return message

@router.post("/messages/{message_id}/discard", response_model=SmsMessageResponse)
async def discard_draft_message(
    message_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    message = db.query(SmsMessage).filter(
        SmsMessage.id == message_id,
        SmsMessage.tenant_id == tenant.id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Draft message not found.")
        
    if message.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft messages can be discarded.")

    message.status = "discarded"
    
    event = SmsConversationEvent(
        conversation_id=message.conversation_id,
        type="draft_discarded",
        meta={"message_id": message.id}
    )
    db.add(event)
    db.commit()
    db.refresh(message)
    
    return message

@router.get("/{conversation_id}", response_model=SmsConversationResponse)
async def get_conversation(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    conv = db.query(SmsConversation).filter(
        SmsConversation.id == conversation_id,
        SmsConversation.tenant_id == tenant.id
    ).first()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    # Mark as read when opening details
    if conv.unread_count > 0:
        conv.unread_count = 0
        db.commit()

    return SmsConversationResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        customer_address=conv.customer_address,
        client_id=conv.client_id,
        client_name=conv.client.name if conv.client else None,
        state=conv.state,
        unread_count=conv.unread_count,
        last_activity_at=conv.last_activity_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )

@router.get("/{conversation_id}/messages", response_model=List[SmsMessageResponse])
async def list_conversation_messages(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Verify conversation belongs to tenant
    conv = db.query(SmsConversation).filter(
        SmsConversation.id == conversation_id,
        SmsConversation.tenant_id == tenant.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    messages = db.query(SmsMessage).filter(
        SmsMessage.conversation_id == conversation_id
    ).order_by(
        SmsMessage.occurred_at.asc(),
        SmsMessage.received_at.asc(),
        SmsMessage.id.asc()
    ).all()
    
    return messages

@router.post("/{conversation_id}/messages", response_model=SmsMessageResponse)
async def send_manual_reply(
    conversation_id: DatabaseId,
    payload: SmsMessageCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    conv = db.query(SmsConversation).filter(
        SmsConversation.id == conversation_id,
        SmsConversation.tenant_id == tenant.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    account = db.query(SmsAccount).filter(SmsAccount.id == conv.sms_account_id).first()
    if not account or not account.is_enabled:
        raise HTTPException(status_code=400, detail="SMS account is disabled or missing.")

    # 1. Enqueue message
    msg = enqueue_outbound_message_transactional(
        db=db,
        account=account,
        conversation=conv,
        body=payload.body,
        author_type="staff",
        author_id=admin_user.id,
        status="queued",
        client_request_id=payload.client_request_id
    )

    # 2. Cancel pending AI jobs (since staff took action, current turn is resolved)
    db.query(SmsAiJob).filter(
        SmsAiJob.conversation_id == conv.id,
        SmsAiJob.status == "PENDING"
    ).update({"status": "CANCELLED"})

    # 3. Log event
    event = SmsConversationEvent(
        conversation_id=conv.id,
        type="staff_replied",
        meta={"body": payload.body}
    )
    db.add(event)
    
    # 4. Takeover automatically if not already
    if conv.state != "taken-over":
        conv.state = "taken-over"
        takeover_event = SmsConversationEvent(
            conversation_id=conv.id,
            type="takeover",
            meta={"trigger": "manual_reply"}
        )
        db.add(takeover_event)

    db.commit()
    db.refresh(msg)
    return msg

@router.post("/{conversation_id}/takeover", response_model=SmsConversationResponse)
async def takeover_conversation(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    conv = db.query(SmsConversation).filter(
        SmsConversation.id == conversation_id,
        SmsConversation.tenant_id == tenant.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.state = "taken-over"
    
    # Cancel pending AI jobs
    db.query(SmsAiJob).filter(
        SmsAiJob.conversation_id == conv.id,
        SmsAiJob.status == "PENDING"
    ).update({"status": "CANCELLED"})

    # Log takeover event
    event = SmsConversationEvent(
        conversation_id=conv.id,
        type="takeover",
        meta={"trigger": "explicit_click"}
    )
    db.add(event)
    db.commit()
    
    return conv

@router.post("/{conversation_id}/auto-reply", response_model=SmsConversationResponse)
async def restore_auto_reply(
    conversation_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    conv = db.query(SmsConversation).filter(
        SmsConversation.id == conversation_id,
        SmsConversation.tenant_id == tenant.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.state = "auto-reply"

    # Log event
    event = SmsConversationEvent(
        conversation_id=conv.id,
        type="restore_auto_reply",
        meta={}
    )
    db.add(event)
    db.commit()
    
    return conv
