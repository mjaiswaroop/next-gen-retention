from celery_app import celery_app
from database import SessionLocal
from models import InterventionExperiment, Customer
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("retention_core.tasks.intervention")

@celery_app.task(name="resolve_pending_interventions")
def resolve_pending_interventions():
    """
    Daily beat task to resolve PENDING interventions.
    If 30 days have passed since the intervention, we check if the customer churned.
    """
    db = SessionLocal()
    try:
        # Get pending interventions older than 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        pending_interventions = db.query(InterventionExperiment).filter(
            InterventionExperiment.status == "pending",
            InterventionExperiment.created_at <= thirty_days_ago
        ).all()
        
        for inv in pending_interventions:
            customer = db.query(Customer).filter(
                Customer.id == inv.customer_id,
                Customer.merchant_id == inv.tenant_id
            ).first()
            
            if not customer:
                inv.status = "failed"
                inv.evaluated_at = datetime.now(timezone.utc)
                continue
            
            # If the customer is still active after 30 days, it's a success!
            if customer.is_deleted:
                inv.status = "failed"
            else:
                inv.status = "success"
                
            inv.evaluated_at = datetime.now(timezone.utc)
            
        db.commit()
        logger.info(f"Resolved {len(pending_interventions)} pending interventions.")
    except Exception as e:
        logger.error(f"Error resolving interventions: {e}")
        db.rollback()
    finally:
        db.close()
