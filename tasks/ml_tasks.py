"""
tasks/ml_tasks.py — Celery ML Background Tasks
================================================
Implements the Celery task layer for Section 1 operations.
All tasks include retry logic, structured logging, and tenant isolation.
"""

import logging
from datetime import datetime, timezone, timedelta

from tasks.celery_app import celery_app

logger = logging.getLogger("retention_core.ml_tasks")


@celery_app.task(
    bind=True,
    name="tasks.ml_tasks.retrain_tenant_task",
    max_retries=2,
    default_retry_delay=300,   # 5 minutes before retry
)
def retrain_tenant_task(self, tenant_id: int) -> dict:
    """
    Retrains the XGBoost model for a single tenant.
    Triggered by: beat schedule (weekly) or emergency drift detection.
    """
    logger.info("[retrain_tenant_task] Starting for tenant_id=%d", tenant_id)
    try:
        from services.retraining_service import retrain_tenant_model
        result = retrain_tenant_model(tenant_id)
        logger.info(
            "[retrain_tenant_task] Completed for tenant %d: promoted=%s, version=%d",
            tenant_id, result.get("promoted"), result.get("version")
        )
        return result
    except Exception as exc:
        logger.error("[retrain_tenant_task] Failed for tenant %d: %s", tenant_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="tasks.ml_tasks.retrain_all_tenants_task")
def retrain_all_tenants_task() -> dict:
    """
    Scheduled weekly task: retrains models for all active tenants.
    Fans out individual retrain_tenant_task per tenant.
    """
    from database import SessionLocal
    from models import Merchant

    db = SessionLocal()
    try:
        merchants = db.query(Merchant).filter(Merchant.is_active == True).all()
        tenant_ids = [m.id for m in merchants]
    finally:
        db.close()

    logger.info("[retrain_all_tenants] Scheduling retraining for %d tenants", len(tenant_ids))
    for tid in tenant_ids:
        retrain_tenant_task.apply_async(args=[tid])

    return {"tenants_scheduled": len(tenant_ids), "tenant_ids": tenant_ids}


@celery_app.task(name="tasks.ml_tasks.evaluate_drift_all_tenants_task")
def evaluate_drift_all_tenants_task() -> dict:
    """
    Daily drift evaluation for all active tenants.
    Compares last 7 days of data vs. prior 7 days as baseline.
    """
    import pandas as pd
    from database import SessionLocal
    from models import Merchant, Customer
    from services.drift_service import evaluate_drift

    db = SessionLocal()
    try:
        merchants = db.query(Merchant).filter(Merchant.is_active == True).all()
    finally:
        db.close()

    results = {}
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=7)
    reference_start = now - timedelta(days=14)

    for merchant in merchants:
        db = SessionLocal()
        try:
            # Reference: 8–14 days ago
            ref_cust = (
                db.query(Customer)
                .filter(
                    Customer.merchant_id == merchant.id,
                    Customer.is_deleted == False,
                    Customer.updated_at >= reference_start,
                    Customer.updated_at < current_start,
                )
                .all()
            )
            # Current: last 7 days
            cur_cust = (
                db.query(Customer)
                .filter(
                    Customer.merchant_id == merchant.id,
                    Customer.is_deleted == False,
                    Customer.updated_at >= current_start,
                )
                .all()
            )

            if not ref_cust or not cur_cust:
                logger.info("[drift] Skipping tenant %d: insufficient data", merchant.id)
                continue

            ref_df = pd.DataFrame([{
                "recency_days": c.recency_days,
                "frequency": c.frequency,
                "monetary_value": c.monetary_value,
                "session_failures": c.session_failures,
                "payment_friction_index": c.payment_friction_index,
                "active_support_tickets": c.active_support_tickets,
            } for c in ref_cust])

            cur_df = pd.DataFrame([{
                "recency_days": c.recency_days,
                "frequency": c.frequency,
                "monetary_value": c.monetary_value,
                "session_failures": c.session_failures,
                "payment_friction_index": c.payment_friction_index,
                "active_support_tickets": c.active_support_tickets,
            } for c in cur_cust])

            import numpy as np
            ref_scores = np.array([c.churn_probability or 0.0 for c in ref_cust])
            cur_scores = np.array([c.churn_probability or 0.0 for c in cur_cust])

            drift_results = evaluate_drift(
                tenant_id=merchant.id,
                reference_df=ref_df,
                current_df=cur_df,
                ref_scores=ref_scores,
                cur_scores=cur_scores,
            )
            results[merchant.id] = drift_results
        finally:
            db.close()

    return results


@celery_app.task(name="tasks.ml_tasks.evaluate_experiments_all_tenants_task")
def evaluate_experiments_all_tenants_task() -> dict:
    """Monthly experiment evaluation for all active tenants."""
    from database import SessionLocal
    from models import Merchant
    from services.experiment_service import evaluate_experiment

    db = SessionLocal()
    try:
        merchants = db.query(Merchant).filter(Merchant.is_active == True).all()
    finally:
        db.close()

    results = {}
    for merchant in merchants:
        try:
            result = evaluate_experiment(merchant.id)
            if result:
                results[merchant.id] = result
        except Exception as e:
            logger.error("[experiment_eval] Failed for tenant %d: %s", merchant.id, e)

    return results


@celery_app.task(name="tasks.ml_tasks.auto_approve_campaigns_task")
def auto_approve_campaigns_task() -> dict:
    """
    Section 4.1: Auto-approves campaigns that have been pending beyond
    the tenant's auto_approve_after_hours threshold.
    """
    from database import SessionLocal
    from models import CampaignQueue, TenantConfig
    from sqlalchemy import and_

    db = SessionLocal()
    approved_count = 0
    try:
        # Find all tenants with pending campaigns
        pending = (
            db.query(CampaignQueue)
            .filter(CampaignQueue.status == "pending")
            .all()
        )

        now = datetime.now(timezone.utc)
        for campaign in pending:
            config = db.query(TenantConfig).filter_by(tenant_id=campaign.tenant_id).first()
            hours_threshold = config.campaign_auto_approve_hours if config else 24

            age_hours = (now - campaign.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_hours >= hours_threshold:
                campaign.status = "auto_approved"
                campaign.reviewed_at = now
                campaign.reviewed_by = "system:auto_approve"
                campaign.updated_at = now
                approved_count += 1
                logger.info(
                    "[auto_approve] Campaign %s auto-approved after %.1fh (threshold=%dh)",
                    campaign.queue_id, age_hours, hours_threshold
                )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("[auto_approve] Auto-approved %d campaigns.", approved_count)
    return {"auto_approved": approved_count}


@celery_app.task(
    bind=True,
    name="tasks.ml_tasks.compute_shap_tenant_task",
    max_retries=1,
)
def compute_shap_tenant_task(self, tenant_id: int) -> dict:
    """Computes SHAP values for top-5 at-risk customers of a tenant."""
    try:
        from services.explainability_service import compute_shap_for_tenant
        results = compute_shap_for_tenant(tenant_id)
        logger.info("[shap] Computed for %d customers (tenant %d)", len(results), tenant_id)
        return {"computed": len(results), "tenant_id": tenant_id}
    except Exception as exc:
        logger.error("[shap] Failed for tenant %d: %s", tenant_id, exc)
        raise self.retry(exc=exc)
