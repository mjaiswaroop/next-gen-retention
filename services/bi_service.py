"""
services/bi_service.py — Business Intelligence & Reporting
===========================================================
Implements Section 9:
- Cohort churn trend computation (weekly buckets)
- Revenue-at-risk calculation
- Campaign ROI: send cost vs. revenue recovered
- Executive digest data compilation for Section 9.5
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger("retention_core.bi")


def get_cohort_churn_trend(tenant_id: int, weeks: int = 12) -> pd.DataFrame:
    """
    Returns a DataFrame of weekly churn rates for the last N weeks.
    Columns: week_start, total_customers, high_risk_count, churn_rate_pct
    """
    from database import SessionLocal
    from models import Customer
    from sqlalchemy import and_, func

    db = SessionLocal()
    try:
        all_customers = (
            db.query(Customer)
            .filter(
                Customer.merchant_id == tenant_id,
                Customer.is_deleted == False,
            )
            .all()
        )
    finally:
        db.close()

    if not all_customers:
        return pd.DataFrame(columns=["week_start", "total_customers", "high_risk_count", "churn_rate_pct"])

    rows = []
    now = datetime.now(timezone.utc)

    for week_offset in range(weeks, 0, -1):
        week_start = now - timedelta(weeks=week_offset)
        week_end   = week_start + timedelta(weeks=1)

        week_customers = [
            c for c in all_customers
            if week_start <= c.created_at.replace(tzinfo=timezone.utc) < week_end
            or c.updated_at.replace(tzinfo=timezone.utc) < week_end
        ]

        total = len(week_customers)
        high_risk = sum(1 for c in week_customers if (c.churn_probability or 0) >= 0.75)
        churn_rate = (high_risk / total * 100) if total > 0 else 0.0

        rows.append({
            "week_start":      week_start.strftime("%Y-%m-%d"),
            "total_customers": total,
            "high_risk_count": high_risk,
            "churn_rate_pct":  round(churn_rate, 2),
        })

    return pd.DataFrame(rows)


def get_revenue_at_risk(tenant_id: int, churn_threshold: float = 0.75) -> dict:
    """
    Computes revenue at risk: sum of monetary_value for high-risk customers.

    Returns:
        dict: { total_at_risk, customer_count, avg_value, currency_symbol }
    """
    from database import SessionLocal
    from models import Customer
    from sqlalchemy import and_

    db = SessionLocal()
    try:
        high_risk = (
            db.query(Customer)
            .filter(
                and_(
                    Customer.merchant_id == tenant_id,
                    Customer.is_deleted == False,
                    Customer.churn_probability >= churn_threshold,
                )
            )
            .all()
        )
    finally:
        db.close()

    if not high_risk:
        return {"total_at_risk": 0.0, "customer_count": 0, "avg_value": 0.0}

    values = [c.monetary_value or 0.0 for c in high_risk]
    return {
        "total_at_risk":  round(sum(values), 2),
        "customer_count": len(high_risk),
        "avg_value":      round(np.mean(values), 2),
        "max_value":      round(max(values), 2),
    }


def get_campaign_roi(tenant_id: int) -> dict:
    """
    Estimates campaign ROI:
    - Campaigns sent: count of non-pending, non-rejected campaigns
    - Revenue recovered: customers who were high-risk and are now below threshold (proxy)
    - Rough ROI = (revenue_recovered / send_cost) * 100
    """
    from database import SessionLocal
    from models import CampaignQueue, CampaignEvent, Customer
    from sqlalchemy import and_, func

    db = SessionLocal()
    try:
        sent_count = (
            db.query(func.count(CampaignQueue.queue_id))
            .filter(
                CampaignQueue.tenant_id == tenant_id,
                CampaignQueue.status.in_(["approved", "auto_approved", "sent"]),
            )
            .scalar() or 0
        )

        total_events = (
            db.query(func.count(CampaignEvent.event_id))
            .filter(CampaignEvent.tenant_id == tenant_id)
            .scalar() or 0
        )

        clicked = (
            db.query(func.count(CampaignEvent.event_id))
            .filter(
                CampaignEvent.tenant_id == tenant_id,
                CampaignEvent.event_type == "clicked",
            )
            .scalar() or 0
        )
    finally:
        db.close()

    ctr = (clicked / sent_count * 100) if sent_count > 0 else 0.0
    # Estimate: $0.012 per email send, $150 average recovery value per click
    send_cost = sent_count * 0.012
    recovered = clicked * 150
    roi_pct = ((recovered - send_cost) / max(send_cost, 0.01)) * 100

    return {
        "campaigns_sent":        sent_count,
        "total_interactions":    total_events,
        "clicks":                clicked,
        "click_through_rate_pct": round(ctr, 2),
        "estimated_send_cost":   round(send_cost, 2),
        "estimated_revenue_recovered": round(recovered, 2),
        "estimated_roi_pct":     round(roi_pct, 1),
    }


def compile_executive_digest(tenant_id: int) -> dict:
    """
    Compiles all BI metrics into a single dict for the executive weekly digest email.
    """
    try:
        trend_df = get_cohort_churn_trend(tenant_id, weeks=4)
        revenue  = get_revenue_at_risk(tenant_id)
        roi      = get_campaign_roi(tenant_id)

        latest_rate = trend_df["churn_rate_pct"].iloc[-1] if not trend_df.empty else 0.0
        prev_rate   = trend_df["churn_rate_pct"].iloc[-2] if len(trend_df) >= 2 else 0.0
        trend_delta = round(latest_rate - prev_rate, 2)

        return {
            "tenant_id":         tenant_id,
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "churn_rate_this_week": latest_rate,
            "churn_rate_delta":  trend_delta,
            "revenue_at_risk":   revenue,
            "campaign_roi":      roi,
            "trend_weeks":       trend_df.to_dict("records") if not trend_df.empty else [],
        }
    except Exception as e:
        logger.error("[bi] Executive digest compilation failed for tenant %d: %s", tenant_id, e)
        return {"tenant_id": tenant_id, "error": str(e)}
