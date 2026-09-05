from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/sms/chatwoot", tags=["sms-chatwoot-legacy"])

# Webhook receiver
@router.post("/webhook")
async def retired_chatwoot_webhook() -> None:
    """Reject the obsolete token-in-URL webhook before reading its request."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy Chatwoot webhook is retired.",
    )
