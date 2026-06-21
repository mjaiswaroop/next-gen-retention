"""
services/outreach/sendgrid_client.py — SendGrid Email Delivery
==============================================================
Section 4.2: Sends approved win-back campaigns via SendGrid API v3.
Includes CAN-SPAM / GDPR List-Unsubscribe header.
Gracefully skips if SENDGRID_API_KEY not set.
"""

import logging
import os

logger = logging.getLogger("retention_core.outreach.sendgrid")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@retentioncore.io")
FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Retention Core")
UNSUBSCRIBE_URL = os.getenv("UNSUBSCRIBE_BASE_URL", "https://retentioncore.io/unsubscribe")


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    customer_id: str,
    tenant_id: int,
    campaign_id: str,
) -> dict:
    """
    Sends a win-back email via SendGrid.

    Args:
        to_email:    Recipient email address
        subject:     Email subject line
        body_text:   Plain-text email body
        customer_id: Customer ID for unsubscribe link token
        tenant_id:   Tenant ID for routing
        campaign_id: Campaign queue ID for tracking

    Returns:
        dict: { success: bool, status_code: int, error: str|None }
    """
    if not SENDGRID_API_KEY:
        logger.warning("[sendgrid] SENDGRID_API_KEY not set — skipping email send.")
        return {"success": False, "status_code": 0, "error": "API key not configured"}

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail, Header, To, Content
        )
    except ImportError:
        logger.error("[sendgrid] sendgrid library not installed.")
        return {"success": False, "status_code": 0, "error": "sendgrid not installed"}

    unsubscribe_link = f"{UNSUBSCRIBE_URL}?cid={customer_id}&tid={tenant_id}"
    html_body = f"""
    <html><body>
    <p>{body_text.replace(chr(10), '<br>')}</p>
    <hr>
    <p style="font-size:11px;color:#888;">
    You are receiving this because you are a valued customer.
    <a href="{unsubscribe_link}">Unsubscribe</a>
    </p>
    </body></html>
    """

    message = Mail(
        from_email=(FROM_EMAIL, FROM_NAME),
        to_emails=To(to_email),
        subject=subject,
        html_content=html_body,
    )
    # CAN-SPAM / GDPR compliance header
    message.header = Header("List-Unsubscribe", f"<{unsubscribe_link}>")
    message.custom_arg = {"campaign_id": campaign_id, "tenant_id": str(tenant_id)}

    try:
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(
            "[sendgrid] Email sent to %s (status=%d, campaign=%s)",
            to_email, response.status_code, campaign_id
        )
        return {"success": response.status_code in (200, 202), "status_code": response.status_code, "error": None}
    except Exception as e:
        logger.error("[sendgrid] Email send failed: %s", e)
        return {"success": False, "status_code": 500, "error": str(e)}
