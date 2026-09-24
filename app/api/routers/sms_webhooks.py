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

DELIVERY_STATUS_TRANSITIONS = {
    "queued": frozenset({"sent", "delivered", "failed"}),
    "sending": frozenset({"sent", "delivered", "failed"}),
    "sent": frozenset({"delivered", "failed"}),
    "delivered": frozenset(),
    "failed": frozenset(),
}
DELIVERY_ACKNOWLEDGEMENT = {"status": "success"}

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
    except HTTPException:
        raise
    except Exception:
        logger.error("Inbound SMS webhook processing failed.")
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
        SmsAccount.is_enabled.is_(True),
    ).first()
    
    if not account:
        logger.warning("Delivery receipt webhook account resolution failed.")
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
        ).with_for_update().first()
        
        if not message:
            # If not found, log it but return success to provider (acknowledgement)
            logger.info("Delivery receipt did not match a tracked message.")
            return DELIVERY_ACKNOWLEDGEMENT

        if message.status == update.status:
            logger.info("Duplicate delivery receipt was acknowledged.")
            return DELIVERY_ACKNOWLEDGEMENT

        allowed_next_statuses = DELIVERY_STATUS_TRANSITIONS.get(message.status)
        if (
            allowed_next_statuses is None
            or update.status not in allowed_next_statuses
        ):
            logger.info("Out-of-order delivery receipt was acknowledged without mutation.")
            return DELIVERY_ACKNOWLEDGEMENT

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
        
        return DELIVERY_ACKNOWLEDGEMENT
        
    except HTTPException:
        raise
    except Exception:
        logger.error("Delivery receipt webhook processing failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing delivery status webhook."
        )
