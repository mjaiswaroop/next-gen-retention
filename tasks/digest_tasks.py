"""
tasks/digest_tasks.py — Weekly Executive Digest
=================================================
Section 9.5: Generates the weekly BI digest and emails it to the Tenant Admin.
"""

import logging
from datetime import datetime, timezone

from tasks.celery_app import celery_app

logger = logging.getLogger("retention_core.digest_tasks")


@celery_app.task(name="tasks.digest_tasks.send_weekly_digest_all_tenants")
def send_weekly_digest_all_tenants() -> dict:
    """Iterates through all active tenants and sends their weekly BI digest."""
    from database import SessionLocal
    from models import Merchant, User
    from services.bi_service import compile_executive_digest
    from services.outreach.sendgrid_client import send_email
    import json

    db = SessionLocal()
    results = {}
    try:
        active_tenants = db.query(Merchant).filter(Merchant.is_active == True).all()

        for tenant in active_tenants:
            from database import active_tenant_id
            active_tenant_id.set(tenant.id)
            # Get the tenant's admin email (fallback to first user if no explicitly marked admin)
            admin = (
                db.query(User)
                .filter(User.tenant_id == tenant.id, User.is_active == True)
                .order_by(User.id)
                .first()
            )
            if not admin:
                logger.warning("[digest] No active users found for tenant %d", tenant.id)
                results[tenant.id] = "no_admin_user"
                continue

            digest = compile_executive_digest(tenant.id)
            if "error" in digest:
                results[tenant.id] = f"error: {digest['error']}"
                continue

            # Format the email body
            revenue = digest.get("revenue_at_risk", {})
            roi = digest.get("campaign_roi", {})

            body = f"""
Weekly Executive Digest: Retention Core
=======================================
Tenant: {tenant.name}
Generated: {digest.get('generated_at')}

--- 📈 CHURN TRENDS ---
Churn Rate This Week: {digest.get('churn_rate_this_week'):.2f}%
Delta vs. Last Week:  {digest.get('churn_rate_delta'):+.2f}%

--- 💰 REVENUE AT RISK ---
Total At-Risk: ${revenue.get('total_at_risk', 0):,.2f}
Customers At-Risk: {revenue.get('customer_count', 0)}

--- 🚀 CAMPAIGN ROI ---
Campaigns Sent: {roi.get('campaigns_sent', 0)}
Estimated ROI:  {roi.get('estimated_roi_pct', 0):.1f}%
Rev. Recovered: ${roi.get('estimated_revenue_recovered', 0):,.2f}
            """

            subject = f"Retention Core Weekly Digest: {tenant.name}"

            # Send email
            response = send_email(
                to_email=admin.email,
                subject=subject,
                body_text=body,
                customer_id=str(admin.id),
                tenant_id=tenant.id,
                campaign_id="digest_weekly",
            )
            
            if response.get("success"):
                results[tenant.id] = "sent"
                logger.info("[digest] Weekly digest sent to %s for tenant %d", admin.email, tenant.id)
            else:
                results[tenant.id] = f"send_failed: {response.get('error')}"
                logger.error("[digest] Failed to send digest to %s: %s", admin.email, response.get("error"))

    except Exception as e:
        logger.error("[digest] Digest task failed: %s", e)
    finally:
        db.close()

    return results
