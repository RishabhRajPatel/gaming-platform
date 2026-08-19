"""Razorpay integration: create orders, verify payment + webhook signatures.

Signature verification is implemented with `hmac` directly so it works even if the
`razorpay` SDK is not installed (e.g. in CI with REAL_MONEY_ENABLED=false). The SDK is
used only for the outbound order-create call.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from app.core.config import settings


class RazorpayError(Exception):
    pass


def _client():
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise RazorpayError("Razorpay keys not configured")
    try:
        import razorpay  # imported lazily
    except ImportError as exc:  # pragma: no cover
        raise RazorpayError("razorpay SDK not installed") from exc
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_order(amount_paise: int, receipt: str, currency: str = "INR") -> dict:
    """Create a Razorpay order. Returns the order dict (contains 'id')."""
    if amount_paise <= 0:
        raise RazorpayError("amount must be positive")
    client = _client()
    return client.order.create(
        {
            "amount": amount_paise,      # Razorpay expects paise
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1,
        }
    )


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify the checkout callback signature: HMAC_SHA256(order_id|payment_id)."""
    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify the X-Razorpay-Signature header for a webhook payload."""
    if not settings.razorpay_webhook_secret:
        return False
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")
