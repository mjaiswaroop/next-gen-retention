"""
tasks/twin_tasks.py
"""
import logging
from celery_app import celery_app
from services.twin_service import retrain_customer_twin

logger = logging.getLogger("retention_core.tasks.twin")

@celery_app.task(queue="ml_worker")
def retrain_all_twins_task(tenant_id: int):
    """
    Weekly background task mapped to the `ml_worker` queue to avoid blocking main processing.
    """
    logger.info("[tasks] Retraining all customer twins for tenant %d", tenant_id)
    
    # In a real scenario, we'd query all active customers for this tenant
    # For now, we mock retraining a batch
    mock_customers = ["cust_1", "cust_2"]
    for cid in mock_customers:
        retrain_customer_twin(tenant_id, cid)
        
    logger.info("[tasks] Twin retraining complete for tenant %d", tenant_id)
