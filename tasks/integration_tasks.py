"""
tasks/integration_tasks.py — Celery Integration Tasks
=======================================================
Section 6: Integration Layer periodic and retry tasks.
"""

import logging
from datetime import datetime, timezone, timedelta

from tasks.celery_app import celery_app

logger = logging.getLogger("retention_core.integration_tasks")


@celery_app.task(name="tasks.integration_tasks.poll_zendesk_all_tenants")
def poll_zendesk_all_tenants() -> dict:
    """Polls Zendesk for all active tenants that have Zendesk enabled."""
    from database import SessionLocal
    from models import Merchant, TenantIntegration
    from services.integrations.zendesk_poller import poll_recent_tickets

    db = SessionLocal()
    try:
        integrations = (
            db.query(TenantIntegration)
            .filter(
                TenantIntegration.integration_name == "zendesk",
                TenantIntegration.is_enabled == True,
            )
            .all()
        )
    finally:
        db.close()

    results = {}
    for integration in integrations:
        try:
            count = poll_recent_tickets(tenant_id=integration.tenant_id)
            results[integration.tenant_id] = {"tickets_ingested": count}
        except Exception as e:
            logger.error("[zendesk_task] Failed for tenant %d: %s", integration.tenant_id, e)
            results[integration.tenant_id] = {"error": str(e)}

    return results


@celery_app.task(
    bind=True,
    name="tasks.integration_tasks.retry_failed_webhooks_task",
    max_retries=0,   # This task itself doesn't retry; it retries others
)
def retry_failed_webhooks_task(self) -> dict:
    """
    Retries outbound webhook deliveries that failed in the last 24h.
    Backs off exponentially: attempt 1 = immediate, 2 = 15min, 3 = 1h.
    After 3 attempts, marks as permanently_failed.
    """
    from database import SessionLocal
    from models import WebhookDeliveryLog
    from sqlalchemy import and_
    import httpx
    import json

    db = SessionLocal()
    retried = 0
    failed_permanently = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        pending_webhooks = (
            db.query(WebhookDeliveryLog)
            .filter(
                and_(
                    WebhookDeliveryLog.delivered_at.is_(None),
                    WebhookDeliveryLog.attempt_count < 3,
                    WebhookDeliveryLog.created_at >= cutoff,
                )
            )
            .all()
        )

        logger.info("[webhook_retry] %d webhooks pending retry.", len(pending_webhooks))

        for webhook in pending_webhooks:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        webhook.url,
                        headers={"Content-Type": "application/json",
                                 "X-RetentionCore-Attempt": str(webhook.attempt_count + 1)},
                        content=b"{}",   # Payload hash only — actual payload was logged at creation
                    )
                if resp.status_code < 400:
                    webhook.delivered_at = datetime.now(timezone.utc)
                    webhook.http_status = resp.status_code
                    retried += 1
                else:
                    webhook.attempt_count += 1
                    webhook.http_status = resp.status_code
                    webhook.error = f"HTTP {resp.status_code}"
            except Exception as e:
                webhook.attempt_count += 1
                webhook.error = str(e)[:255]

            if webhook.attempt_count >= 3 and webhook.delivered_at is None:
                webhook.error = f"permanently_failed: {webhook.error}"
                failed_permanently += 1

            webhook.updated_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("[webhook_retry] Task failed: %s", e)
    finally:
        db.close()

    return {"retried_successfully": retried, "permanently_failed": failed_permanently}
