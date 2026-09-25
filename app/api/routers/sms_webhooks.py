import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.sms_account import SmsAccount
from ...models.sms_message import SmsMessage
from ...models.sms_receipt import SmsDeliveryReceipt
from ...services.sms.inbound_service import process_inbound_webhook
from ...services.sms.transports import get_transport_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms/webhooks", tags=["sms-webhooks"])

@router.post("/incoming")
async def inbound_webhook_generic(
    request: Request,
    db: Session = Depends(get_db)
):
    """Generic or simulated incoming SMS webhook intake."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    transport_type = data.get("transport_type", "simulator")
    account_public_id = data.get("account_public_id")
    
    if not account_public_id:
        account = db.query(SmsAccount).filter(SmsAccount.is_enabled == True).first()
        if not account:
            raise HTTPException(status_code=400, detail="No active SMS account found.")
        account_public_id = account.public_id
        transport_type = account.transport_type

    return await process_inbound_webhook(
        db=db,
        transport_type=transport_type,
        account_public_id=account_public_id,
        request=request
    )

@router.post("/{transport_type}/{account_public_id}")
async def inbound_webhook(
    transport_type: str,
    account_public_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Public webhook intake endpoint for incoming SMS events."""
    try:
        result = await process_inbound_webhook(
            db=db,
            transport_type=transport_type,
            account_public_id=account_public_id,
            request=request
        )
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing inbound SMS webhook for transport={transport_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing inbound webhook."
        )

@router.post("/{transport_type}/{account_public_id}/delivery")
async def delivery_receipt_webhook(
    transport_type: str,
    account_public_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Public webhook endpoint for delivery status receipt updates."""
    # 1. Resolve SMS Account
    account = db.query(SmsAccount).filter(
        SmsAccount.public_id == account_public_id,
        SmsAccount.transport_type == transport_type,
        SmsAccount.is_enabled == True
    ).first()
    
    if not account:
        logger.warning(f"Delivery receipt webhook rejected: SMS Account not found or disabled for public_id={account_public_id}, transport={transport_type}")
        raise HTTPException(status_code=404, detail="SMS account not found or disabled.")

    try:
        adapter = get_transport_adapter(transport_type)
        
        # 2. Verify webhook
        await adapter.verify_webhook(request, account)
        
        # 3. Parse receipt
        update = await adapter.parse_delivery_receipt(request, account)
        
        # 4. Resolve outbound message
        # Check both provider_message_id and outbound jobs
        message = db.query(SmsMessage).filter(
            SmsMessage.sms_account_id == account.id,
            SmsMessage.provider_message_id == update.provider_message_id,
            SmsMessage.direction == "outbound"
        ).first()
        
        if not message:
            # If not found, log it but return success to provider (acknowledgement)
            logger.info(f"Delivery receipt received for untracked provider_message_id={update.provider_message_id}")
            return {"status": "success", "detail": "Message not tracked or already deleted."}

        # 5. Update message status
        message.status = update.status
        
        # 6. Store delivery receipt audit log
        receipt = SmsDeliveryReceipt(
            message_id=message.id,
            status=update.status,
            raw_payload=update.raw_payload,
            error_code=update.error_code,
            error_message=update.error_message,
            created_at=datetime.now(timezone.utc)
        )
        db.add(receipt)
        db.commit()
        
        return {"status": "success", "message_id": message.id, "new_status": update.status}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing delivery receipt webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing delivery status webhook."
        )
