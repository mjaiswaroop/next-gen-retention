"""
services/integrations/stripe_webhook.py — Stripe Event Handler
Section 6.2: Processes Stripe payment failure and subscription cancellation events.
Increments payment_friction_index on failed charges.
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

logger = logging.getLogger("retention_core.integrations.stripe")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def verify_stripe_signature(payload_bytes: bytes, sig_header: str) -> bool:
    """Validates the Stripe-Signature header to prevent webhook spoofing."""
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("[stripe] STRIPE_WEBHOOK_SECRET not set. Skipping signature verification.")
        return True   # Graceful degradation in dev

    try:
        parts = {k: v for k, v in (item.split("=", 1) for item in sig_header.split(","))}
        timestamp = parts.get("t", "0")
        received_sig = parts.get("v1", "")
        signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}"
        expected = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, received_sig)
    except Exception as e:
        logger.error("[stripe] Signature verification error: %s", e)
        return False


def process_stripe_event(event: dict, tenant_id: int) -> Optional[str]:
    """
    Processes a Stripe webhook event dict.
    Returns action taken or None.

    Handled event types:
    - charge.failed           → increment payment_friction_index
    - customer.subscription.deleted → mark customer at risk
    """
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    customer_stripe_id = data.get("customer")

    if event_type == "charge.failed":
        logger.info("[stripe] Charge failed for customer %s (tenant %d)", customer_stripe_id, tenant_id)
        return _flag_payment_friction(customer_stripe_id, tenant_id, delta=0.1)

    elif event_type == "customer.subscription.deleted":
        logger.info("[stripe] Subscription cancelled for customer %s (tenant %d)", customer_stripe_id, tenant_id)
        return _flag_payment_friction(customer_stripe_id, tenant_id, delta=0.3)

    logger.debug("[stripe] Unhandled event type: %s", event_type)
    return None


def _flag_payment_friction(stripe_customer_id: str, tenant_id: int, delta: float) -> str:
    """Increments payment_friction_index for the matching customer."""
    if not stripe_customer_id:
        return "no_customer_id"
    try:
        from database import SessionLocal
        from models import Customer
        from sqlalchemy import and_
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            # Match on user_id == stripe_customer_id (or add a separate field)
            customer = db.query(Customer).filter(
                and_(Customer.merchant_id == tenant_id, Customer.user_id == stripe_customer_id)
            ).first()
            if customer:
                customer.payment_friction_index = min(1.0, (customer.payment_friction_index or 0.0) + delta)
                customer.updated_at = datetime.now(timezone.utc)
                db.commit()
                return f"friction_incremented_by_{delta}"
        finally:
            db.close()
    except Exception as e:
        logger.error("[stripe] DB update failed: %s", e)
    return "not_found"
