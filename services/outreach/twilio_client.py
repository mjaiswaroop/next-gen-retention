"""
services/outreach/twilio_client.py — Twilio SMS Delivery
=========================================================
Section 4.2: Sends approved win-back campaigns via Twilio SMS.
Enforces 160-char truncation. Handles STOP opt-out keyword.
Gracefully skips if TWILIO_* credentials not set.
"""

import logging
import os

logger = logging.getLogger("retention_core.outreach.twilio")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+15550000000")
SMS_MAX_LENGTH = 160
OPT_OUT_FOOTER = " Reply STOP to opt out."


def send_sms(
    to_phone: str,
    message_body: str,
    customer_id: str,
    campaign_id: str,
) -> dict:
    """
    Sends a win-back SMS via Twilio. Truncates to 160 chars including footer.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("[twilio] TWILIO credentials not set — skipping SMS.")
        return {"success": False, "status_code": 0, "error": "Credentials not configured"}

    try:
        from twilio.rest import Client
    except ImportError:
        logger.error("[twilio] twilio library not installed.")
        return {"success": False, "status_code": 0, "error": "twilio not installed"}

    # Truncate message body to fit within 160 chars including footer
    max_body = SMS_MAX_LENGTH - len(OPT_OUT_FOOTER)
    truncated = message_body[:max_body].strip()
    full_message = truncated + OPT_OUT_FOOTER

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=full_message,
            from_=TWILIO_FROM_NUMBER,
            to=to_phone,
        )
        logger.info("[twilio] SMS sent to %s (sid=%s, campaign=%s)", to_phone, msg.sid, campaign_id)
        return {"success": True, "sid": msg.sid, "status_code": 200, "error": None}
    except Exception as e:
        logger.error("[twilio] SMS send failed: %s", e)
        return {"success": False, "status_code": 500, "error": str(e)}
