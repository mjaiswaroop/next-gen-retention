"""
services/integrations/salesforce_client.py — Salesforce CRM Integration
========================================================================
Section 6.1: Syncs churn-risk customer data and campaign outcomes to Salesforce.
Uses simple-salesforce library. Gracefully skips if credentials not set.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("retention_core.integrations.salesforce")

SF_USERNAME = os.getenv("SALESFORCE_USERNAME")
SF_PASSWORD = os.getenv("SALESFORCE_PASSWORD")
SF_TOKEN    = os.getenv("SALESFORCE_SECURITY_TOKEN")


def _get_client():
    """Returns authenticated Salesforce client or None if credentials missing."""
    if not all([SF_USERNAME, SF_PASSWORD, SF_TOKEN]):
        logger.warning("[salesforce] Credentials not configured — skipping.")
        return None
    try:
        from simple_salesforce import Salesforce
        return Salesforce(username=SF_USERNAME, password=SF_PASSWORD, security_token=SF_TOKEN)
    except ImportError:
        logger.error("[salesforce] simple-salesforce not installed.")
        return None
    except Exception as e:
        logger.error("[salesforce] Connection failed: %s", e)
        return None


def upsert_churn_risk(customer_id: str, tenant_id: int, churn_score: float) -> bool:
    """
    Upserts a Contact or Lead in Salesforce with churn risk score.
    Uses external ID field: Retention_Customer_ID__c
    """
    sf = _get_client()
    if not sf:
        return False
    try:
        result = sf.Contact.upsert(
            f"Retention_Customer_ID__c/{customer_id}",
            {
                "Churn_Risk_Score__c": churn_score,
                "Churn_Risk_Tenant__c": str(tenant_id),
                "Churn_Risk_Updated__c": __import__("datetime").datetime.utcnow().isoformat(),
            }
        )
        logger.info("[salesforce] Upserted Contact for customer %s: %s", customer_id, result)
        return True
    except Exception as e:
        logger.error("[salesforce] Upsert failed for customer %s: %s", customer_id, e)
        return False


def log_campaign_outcome(customer_id: str, campaign_id: str, outcome: str) -> bool:
    """Creates a Task activity in Salesforce for a win-back campaign outcome."""
    sf = _get_client()
    if not sf:
        return False
    try:
        sf.Task.create({
            "Subject": f"Retention Core Win-Back: {outcome}",
            "Description": f"Campaign ID: {campaign_id}\nCustomer ID: {customer_id}\nOutcome: {outcome}",
            "Status": "Completed",
            "Priority": "Normal",
        })
        return True
    except Exception as e:
        logger.error("[salesforce] Task creation failed: %s", e)
        return False
