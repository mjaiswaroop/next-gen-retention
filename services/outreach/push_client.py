"""
services/outreach/push_client.py — In-App Push Webhook Delivery
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("retention_core.outreach.push")


def send_push(
    webhook_url: str,
    customer_id: str,
    tenant_id: int,
    subject: str,
    body: str,
    campaign_id: str,
) -> dict:
    """POSTs campaign payload to the tenant's configured in-app push webhook URL."""
    if not webhook_url:
        logger.warning("[push] No webhook URL configured for tenant %d.", tenant_id)
        return {"success": False, "error": "No webhook URL configured"}

    payload = {
        "event_type": "campaign.win_back",
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "campaign_id": campaign_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"subject": subject, "body": body},
    }
    payload_bytes = json.dumps(payload).encode()
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                webhook_url,
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-RetentionCore-Signature": payload_hash,
                },
            )
        logger.info("[push] Webhook delivered (status=%d, campaign=%s)", response.status_code, campaign_id)
        return {"success": response.status_code < 400, "status_code": response.status_code, "error": None}
    except httpx.RequestError as e:
        logger.error("[push] Webhook delivery failed: %s", e)
        return {"success": False, "status_code": 500, "error": str(e)}
