import logging
import stripe
from ..core.config import settings

logger = logging.getLogger(__name__)

# Initialize Stripe API Key
stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    def create_checkout_session(
        booking_id: int, 
        amount_cents: int, 
        currency: str = "aud", 
        success_url: str = "http://localhost:8000/success", 
        cancel_url: str = "http://localhost:8000/cancel",
        tenant_id: str = None
    ) -> stripe.checkout.Session:
        """Create a Stripe Checkout Session for upfront booking deposit."""
        try:
            metadata = {
                "booking_id": str(booking_id)
            }
            if tenant_id:
                metadata["tenant_id"] = tenant_id

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {
                                "name": f"Booking Deposit (Booking #{booking_id})",
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata
            )
            logger.info(f"Stripe checkout session created: {session.id} for Booking {booking_id}")
            return session
        except Exception as e:
            logger.error(f"Failed to create Stripe Checkout Session: {str(e)}")
            raise

stripe_service = StripeService()
