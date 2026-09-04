from fastapi import APIRouter, HTTPException, status


PAYMENTS_UNAVAILABLE_DETAIL = "Stripe payments are temporarily unavailable"

router = APIRouter(prefix="/api/v1", tags=["stripe"])


def _payments_unavailable() -> None:
    """Keep all legacy Stripe entry points fail-closed until redesigned."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=PAYMENTS_UNAVAILABLE_DETAIL,
    )


@router.post("/checkout/deposit-session")
def create_deposit_session() -> None:
    """Disable legacy deposit-session creation before request processing."""
    _payments_unavailable()


@router.post("/webhooks/stripe")
def stripe_webhook() -> None:
    """Disable legacy Stripe webhook processing before request processing."""
    _payments_unavailable()
