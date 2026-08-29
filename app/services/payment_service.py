"""Payment Service.

Handles server-authoritative deposit calculations, Stripe checkout session
creation, webhook processing, signature verification, event idempotency,
and atomic booking state transitions.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.state_machine import BookingStatus, is_valid_transition
from ..models.booking import Booking as BookingModel
from ..models.payment import Payment as PaymentModel, ProcessedStripeEvent
from ..models.service import Service as ServiceModel
from ..services.outbox_service import create_outbox_event
from ..services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

# Default allowed hosts for dev/testing when FRONTEND_ORIGINS is not explicitly set
DEFAULT_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "testserver"}


def validate_redirect_url(url: str) -> bool:
    """Validate that a redirect URL is safe, has http/https scheme, and matches allowed origins."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Gather allowed hosts
        allowed_hosts = set(DEFAULT_ALLOWED_HOSTS)
        if settings.FRONTEND_ORIGINS:
            for origin in settings.FRONTEND_ORIGINS.split(","):
                cleaned = origin.strip()
                if cleaned:
                    p = urlparse(cleaned)
                    if p.hostname:
                        allowed_hosts.add(p.hostname.lower())

        return hostname.lower() in allowed_hosts
    except Exception as e:
        logger.warning(f"Failed to validate redirect URL '{url}': {e}")
        return False


def get_authoritative_deposit(booking: BookingModel) -> tuple[int, str]:
    """Calculate the server-authoritative deposit amount in cents and normalized currency.

    Never trusts client-supplied pricing. Checks service deposit amount or price.
    """
    service = booking.service
    currency = "aud"
    amount = 0.0

    if service:
        if service.deposit_amount is not None and float(service.deposit_amount) > 0:
            amount = float(service.deposit_amount)
        elif service.price is not None:
            amount = float(service.price)
        
        service_curr = getattr(service, "currency", None)
        if service_curr:
            currency = str(service_curr).lower()

    amount_cents = int(round(amount * 100))
    return amount_cents, currency


class PaymentService:
    """Service encapsulating payment security, checkout session, and webhook reconciliation."""

    @staticmethod
    def create_deposit_checkout_session(
        db: Session,
        booking_id: int,
        success_url: str,
        cancel_url: str,
        tenant_id: int,
        client_amount_cents: Optional[int] = None,
    ) -> dict:
        """Create a Stripe checkout session for a booking deposit with server-authoritative pricing."""
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID is required")

        booking = db.query(BookingModel).filter(
            BookingModel.id == booking_id,
            BookingModel.tenant_id == tenant_id
        ).first()
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        # Booking state validation: must be PENDING
        if booking.status not in (BookingStatus.PENDING, "pending"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot create deposit session for booking with status '{booking.status}'. Only PENDING bookings are eligible."
            )

        # Validate redirect URLs against allowed frontend origins
        if not validate_redirect_url(success_url) or not validate_redirect_url(cancel_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid redirect URL: success_url and cancel_url must use http/https and match allowed frontend origins"
            )

        # Calculate authoritative deposit
        authoritative_cents, currency = get_authoritative_deposit(booking)

        # Reject client-side price tampering
        if client_amount_cents is not None and client_amount_cents != authoritative_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deposit amount mismatch: provided {client_amount_cents} cents, authoritative requirement is {authoritative_cents} cents"
            )

        session = stripe_service.create_checkout_session(
            booking_id=booking.id,
            amount_cents=authoritative_cents,
            currency=currency,
            success_url=success_url,
            cancel_url=cancel_url,
            tenant_id=str(booking.tenant_id)
        )

        return {"session_id": session.id, "url": session.url}

    @staticmethod
    def process_stripe_webhook(db: Session, event: any) -> dict:
        """Process a verified Stripe webhook event idempotently and atomically."""
        if hasattr(event, "to_dict"):
            event = event.to_dict()
        elif not isinstance(event, dict):
            event = dict(event)

        event_id = event.get("id")
        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})
        if hasattr(data_object, "to_dict"):
            data_object = data_object.to_dict()

        if not event_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing event id")

        # 1. Check Event Idempotency
        existing_event = db.query(ProcessedStripeEvent).filter(
            ProcessedStripeEvent.event_id == event_id
        ).first()
        if existing_event:
            logger.info(f"Stripe event {event_id} ({event_type}) was already processed. Idempotent return.")
            return {"ok": True, "duplicate": True, "message": "Event already processed"}

        try:
            if event_type in ["checkout.session.completed", "payment_intent.succeeded"]:
                metadata = data_object.get("metadata", {}) or {}
                booking_id_str = metadata.get("booking_id") or data_object.get("client_reference_id")
                event_tenant_id = metadata.get("tenant_id")

                if not event_tenant_id or not str(event_tenant_id).isdigit():
                    logger.warning(f"Stripe event {event_id} missing or invalid tenant_id in metadata: {event_tenant_id}")
                    event_record = ProcessedStripeEvent(
                        tenant_id=None,
                        event_id=event_id,
                        event_type=event_type,
                        status="quarantined",
                        payload=json.dumps(event)
                    )
                    db.add(event_record)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Missing or invalid tenant_id in Stripe event metadata"
                    )

                tenant_id = int(event_tenant_id)

                if not booking_id_str:
                    logger.warning(f"Stripe event {event_id} has no booking_id in metadata.")
                    event_record = ProcessedStripeEvent(
                        tenant_id=tenant_id,
                        event_id=event_id,
                        event_type=event_type,
                        status="ignored",
                        payload=json.dumps(event)
                    )
                    db.add(event_record)
                    db.commit()
                    return {"ok": True, "message": "No booking_id present in event"}

                try:
                    booking_id = int(booking_id_str)
                except (ValueError, TypeError):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid booking_id format")

                booking = db.query(BookingModel).filter(
                    BookingModel.id == booking_id,
                    BookingModel.tenant_id == tenant_id
                ).first()
                if not booking:
                    other_booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
                    if other_booking:
                        logger.error(f"Tenant mismatch on booking {booking_id}: expected {other_booking.tenant_id}, got {tenant_id}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Tenant mismatch between Stripe event and booking record"
                        )
                    logger.error(f"Booking {booking_id} not found for Stripe event {event_id}")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking {booking_id} not found")

                # Amount & Currency Server-Authoritative Reconciliation
                expected_cents, expected_currency = get_authoritative_deposit(booking)
                amount_total = data_object.get("amount_total")
                if amount_total is None:
                    amount_total = data_object.get("amount")
                if amount_total is None:
                    amount_total = data_object.get("amount_subtotal")

                if amount_total is not None and int(amount_total) != expected_cents:
                    logger.error(f"Amount mismatch for booking {booking_id}: expected {expected_cents} cents, got {amount_total}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stripe payment amount ({amount_total}) does not match authoritative deposit ({expected_cents})"
                    )

                event_currency = data_object.get("currency")
                if event_currency and expected_currency and event_currency.lower() != expected_currency.lower():
                    logger.error(f"Currency mismatch for booking {booking_id}: expected {expected_currency}, got {event_currency}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stripe payment currency ({event_currency}) does not match authoritative currency ({expected_currency})"
                    )

                # Check state machine transition
                if not is_valid_transition(booking.status, BookingStatus.CONFIRMED):
                    if booking.status == BookingStatus.CONFIRMED:
                        logger.info(f"Booking {booking_id} is already CONFIRMED. Recording event as duplicate.")
                        event_record = ProcessedStripeEvent(
                            tenant_id=booking.tenant_id,
                            event_id=event_id,
                            event_type=event_type,
                            booking_id=booking.id,
                            status="processed",
                            payload=json.dumps(event)
                        )
                        db.add(event_record)
                        db.commit()
                        return {"ok": True, "message": "Booking already confirmed"}
                    else:
                        logger.warning(f"Invalid state transition for Booking {booking_id} from {booking.status} to CONFIRMED")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid booking status transition from {booking.status} to CONFIRMED"
                        )

                # Atomic State Transition & Payment Record & Outbox Enqueue
                booking.status = BookingStatus.CONFIRMED

                payment_amount = Decimal(str((amount_total if amount_total is not None else expected_cents) / 100.0))
                payment = PaymentModel(
                    tenant_id=booking.tenant_id,
                    booking_id=booking.id,
                    amount=payment_amount,
                    currency=(event_currency or expected_currency).upper(),
                    status="completed",
                    stripe_event_id=event_id,
                    stripe_session_id=data_object.get("id") if event_type == "checkout.session.completed" else None,
                    stripe_payment_intent_id=data_object.get("payment_intent") if event_type == "checkout.session.completed" else data_object.get("id"),
                )
                db.add(payment)

                # SMS Outbox Notification
                client_phone = booking.client.phone if booking.client and booking.client.phone else "+61411111111"
                client_name = booking.client.name if booking.client and booking.client.name else "Customer"
                sms_payload = {
                    "to": client_phone,
                    "body": f"Hi {client_name}, your deposit has been received and booking #{booking.id} is now CONFIRMED!"
                }
                create_outbox_event(db, "SEND_SMS", sms_payload, tenant_id=booking.tenant_id)

                # Booking Confirmed Outbox Event
                booking_payload = {
                    "id": booking.id,
                    "client_id": booking.client_id,
                    "provider_id": booking.provider_id,
                    "service_id": booking.service_id,
                    "status": booking.status
                }
                create_outbox_event(db, "booking.confirmed", booking_payload, tenant_id=booking.tenant_id)

                # Payment Received Outbox Event
                payment_payload = {
                    "booking_id": booking.id,
                    "amount": float(payment_amount),
                    "currency": (event_currency or expected_currency).upper(),
                    "status": "completed",
                    "stripe_event_id": event_id
                }
                create_outbox_event(db, "payment.received", payment_payload, tenant_id=booking.tenant_id)

                # Record Processed Event
                event_record = ProcessedStripeEvent(
                    tenant_id=booking.tenant_id,
                    event_id=event_id,
                    event_type=event_type,
                    booking_id=booking.id,
                    status="processed",
                    payload=json.dumps(event)
                )
                db.add(event_record)

                db.commit()
                return {"ok": True, "message": f"Booking {booking.id} confirmed and deposit processed"}

            elif event_type in ["invoice.payment_failed", "charge.failed"]:
                metadata = data_object.get("metadata", {}) or {}
                booking_id_str = metadata.get("booking_id") or data_object.get("client_reference_id")
                event_tenant_id = metadata.get("tenant_id")

                if not event_tenant_id or not str(event_tenant_id).isdigit():
                    logger.warning(f"Stripe failure event {event_id} missing or invalid tenant_id in metadata.")
                    event_record = ProcessedStripeEvent(
                        tenant_id=None,
                        event_id=event_id,
                        event_type=event_type,
                        status="quarantined",
                        payload=json.dumps(event)
                    )
                    db.add(event_record)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Missing or invalid tenant_id in Stripe event metadata"
                    )

                tenant_id = int(event_tenant_id)
                if booking_id_str:
                    try:
                        booking_id = int(booking_id_str)
                    except (ValueError, TypeError):
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid booking_id format")

                    booking = db.query(BookingModel).filter(
                        BookingModel.id == booking_id,
                        BookingModel.tenant_id == tenant_id
                    ).first()
                    if not booking:
                        other_booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
                        if other_booking:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Tenant mismatch between Stripe event and booking record"
                            )
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking {booking_id} not found")

                    if is_valid_transition(booking.status, BookingStatus.CANCELLED):
                        booking.status = BookingStatus.CANCELLED

                        payment = PaymentModel(
                            tenant_id=booking.tenant_id,
                            booking_id=booking.id,
                            amount=Decimal("0.00"),
                            currency="AUD",
                            status="failed",
                            stripe_event_id=event_id,
                            stripe_session_id=data_object.get("id"),
                            stripe_payment_intent_id=data_object.get("payment_intent") or data_object.get("id"),
                        )
                        db.add(payment)

                        client_phone = booking.client.phone if booking.client and booking.client.phone else "+61411111111"
                        client_name = booking.client.name if booking.client and booking.client.name else "Customer"
                        sms_payload = {
                            "to": client_phone,
                            "body": f"Hi {client_name}, your deposit payment for booking #{booking.id} failed. The booking has been cancelled."
                        }
                        create_outbox_event(db, "SEND_SMS", sms_payload, tenant_id=booking.tenant_id)

                        booking_payload = {
                            "id": booking.id,
                            "client_id": booking.client_id,
                            "status": booking.status
                        }
                        create_outbox_event(db, "booking.cancelled", booking_payload, tenant_id=booking.tenant_id)

                        payment_payload = {
                            "booking_id": booking.id,
                            "status": "failed",
                            "stripe_event_id": event_id
                        }
                        create_outbox_event(db, "payment.failed", payment_payload, tenant_id=booking.tenant_id)

                        event_record = ProcessedStripeEvent(
                            tenant_id=booking.tenant_id,
                            event_id=event_id,
                            event_type=event_type,
                            booking_id=booking.id,
                            status="processed",
                            payload=json.dumps(event)
                        )
                        db.add(event_record)
                        db.commit()
                        return {"ok": True, "message": f"Booking {booking.id} cancelled due to payment failure"}

                event_record = ProcessedStripeEvent(
                    tenant_id=tenant_id,
                    event_id=event_id,
                    event_type=event_type,
                    status="ignored",
                    payload=json.dumps(event)
                )
                db.add(event_record)
                db.commit()
                return {"ok": True, "message": "Payment failed event handled"}

            else:
                event_record = ProcessedStripeEvent(
                    tenant_id=None,
                    event_id=event_id,
                    event_type=event_type,
                    status="ignored",
                    payload=json.dumps(event)
                )
                db.add(event_record)
                db.commit()
                return {"ok": True, "message": f"Event {event_type} ignored"}

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Unhandled error processing Stripe event {event_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during webhook reconciliation"
            )


payment_service = PaymentService()
