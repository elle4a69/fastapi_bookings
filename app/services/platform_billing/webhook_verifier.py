"""Webhook signature verification and payload digesting for external billing providers."""

import hashlib
import hmac
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""
    pass


class WebhookVerificationService:
    """Verifies HMAC-SHA256 signatures for provider webhooks using raw body bytes."""

    @staticmethod
    def compute_payload_digest(raw_body: bytes) -> str:
        """Compute hex-encoded SHA-256 digest of raw payload.

        Ensures we can record audit receipts in ProviderEventInbox without storing
        sensitive payload data or customer PII.
        """
        return hashlib.sha256(raw_body).hexdigest()

    @classmethod
    def verify_signature(
        cls,
        raw_body: bytes,
        signature_header: Optional[str],
        secret: Optional[str] = None,
    ) -> bool:
        """Verify HMAC-SHA256 signature against raw body bytes.

        Args:
            raw_body: Exact raw request body bytes.
            signature_header: Value of X-Flexprice-Signature or similar signature header.
            secret: Webhook secret. If None, uses settings.FLEXPRICE_WEBHOOK_SECRET.

        Returns:
            True if signature matches; False otherwise.
        """
        signing_secret = secret or settings.FLEXPRICE_WEBHOOK_SECRET
        if not signing_secret or not signature_header:
            logger.warning("Webhook verification rejected: missing signature header or secret")
            return False

        # Support signature header formats:
        # 1. Plain hex: "abcdef123..."
        # 2. Key-value: "t=123456,v1=abcdef123..."
        signature_to_check = signature_header.strip()
        if "v1=" in signature_to_check:
            parts = dict(
                item.split("=", 1)
                for item in signature_to_check.split(",")
                if "=" in item
            )
            signature_to_check = parts.get("v1", "")

        expected_mac = hmac.new(
            key=signing_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_mac, signature_to_check)


webhook_verifier = WebhookVerificationService()
