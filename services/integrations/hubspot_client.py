"""
services/integrations/hubspot_client.py — HubSpot CRM Integration
Section 6.1: Syncs churn risk scores to HubSpot Contact properties.
"""
import logging
import os
import httpx

logger = logging.getLogger("retention_core.integrations.hubspot")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
HUBSPOT_API   = "https://api.hubapi.com/crm/v3"


def update_contact_churn_risk(email: str, churn_score: float) -> bool:
    if not HUBSPOT_TOKEN:
        logger.warning("[hubspot] HUBSPOT_ACCESS_TOKEN not set — skipping.")
        return False
    try:
        with httpx.Client(timeout=10) as client:
            # Search for contact by email
            resp = client.post(
                f"{HUBSPOT_API}/objects/contacts/search",
                headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
                json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]},
            )
            results = resp.json().get("results", [])
            if not results:
                logger.warning("[hubspot] Contact not found for email: %s", email)
                return False

            contact_id = results[0]["id"]
            client.patch(
                f"{HUBSPOT_API}/objects/contacts/{contact_id}",
                headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
                json={"properties": {"churn_risk_score": str(round(churn_score, 4))}},
            )
            logger.info("[hubspot] Updated contact %s churn score: %.4f", email, churn_score)
            return True
    except Exception as e:
        logger.error("[hubspot] Update failed: %s", e)
        return False
