import abc
import logging
from typing import List, Dict, Any

from database import SessionLocal
from models import Customer
from services.causal_service import estimate_causal_effect

logger = logging.getLogger("retention_core.priority")

class CLVEstimator(abc.ABC):
    """Abstract interface for Customer Lifetime Value estimation."""
    @abc.abstractmethod
    def estimate_clv(self, tenant_id: int, customer_id: str) -> float:
        pass

class BaseCLVEstimator(CLVEstimator):
    """
    Basic estimator that treats the customer's monetary_value as 
    Annual Recurring Revenue (ARR) and computes CLV assuming a 5-year lifespan.
    """
    def estimate_clv(self, tenant_id: int, customer_id: str) -> float:
        db = SessionLocal()
        try:
            customer = db.query(Customer).filter_by(merchant_id=tenant_id, id=customer_id).first()
            if not customer:
                return 0.0
            
            # Using monetary_value as MRR/ARR proxy. Let's assume ARR * 5 years
            clv = customer.monetary_value * 5.0
            return clv
        finally:
            db.close()

def compute_priority_queue(tenant_id: int) -> List[Dict[str, Any]]:
    """
    Computes the Expected Value Score (EVS) for all active customers:
    EVS = churn_probability * CLV * causal_uplift
    Returns a sorted list of customers from highest priority to lowest.
    """
    db = SessionLocal()
    clv_estimator = BaseCLVEstimator()
    priority_list = []
    
    try:
        # Fetch all customers with high churn probability (e.g. > 0.5)
        customers = db.query(Customer).filter(
            Customer.merchant_id == tenant_id,
            Customer.is_deleted == False,
            Customer.churn_probability > 0.5
        ).all()
        
        for c in customers:
            clv = clv_estimator.estimate_clv(tenant_id, c.id)
            
            # Use causal model to see if an intervention (e.g. discount) would help
            # Default intervention for the engine: 20% discount
            causal_res = estimate_causal_effect(tenant_id, c.id, [{"variable": "discount", "value": 0.2}])
            uplift = causal_res.get("uplift", 0.0)
            
            # EVS calculation
            evs = c.churn_probability * clv * uplift
            
            priority_list.append({
                "customer_id": c.id,
                "name": c.name,
                "segment": c.segment,
                "churn_probability": c.churn_probability,
                "clv": clv,
                "causal_uplift": uplift,
                "expected_value_score": evs
            })
            
        # Sort by EVS descending
        priority_list.sort(key=lambda x: x["expected_value_score"], reverse=True)
        return priority_list
        
    except Exception as e:
        logger.error(f"[priority] Failed to compute queue: {e}")
        return []
    finally:
        db.close()
