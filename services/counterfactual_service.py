import logging
import uuid
import random
from typing import Dict, Any

logger = logging.getLogger("retention_core.counterfactual")

def generate_counterfactuals(tenant_id: int, customer_id: str, max_cfs: int = 5) -> Dict[str, Any]:
    """
    Mock DiCE-ML counterfactual generation.
    Generates actionable save paths for the UI.
    """
    logger.info(f"Generating counterfactuals for {customer_id}")
    
    # Generate realistic-looking counterfactuals
    paths = []
    actions = [
        {"action": "Apply 15% Lifetime Discount", "cost": 45.0, "queue": "billing_retention"},
        {"action": "Waive Integration Fees", "cost": 150.0, "queue": "sales_ops"},
        {"action": "Assign Dedicated Technical Account Manager", "cost": 500.0, "queue": "customer_success"},
        {"action": "Downgrade to Standard Tier (prevent full churn)", "cost": -20.0, "queue": "auto_billing"},
        {"action": "Offer Free 3-Month Premium Trial", "cost": 90.0, "queue": "marketing_campaigns"}
    ]
    
    for i in range(min(max_cfs, len(actions))):
        act = actions[i]
        paths.append({
            "cf_id": str(uuid.uuid4()),
            "recommended_action": act["action"],
            "cost_usd": act["cost"],
            "feasibility": round(random.uniform(0.65, 0.98), 2),
            "resulting_score": round(random.uniform(0.15, 0.45), 2),
            "routed_to": act["queue"],
            "features_to_change": {
                "billing_amount": round(random.uniform(50, 200), 2),
                "customer_support_level": random.choice([2.0, 3.0, 4.0])
            }
        })
        
    return {
        "customer_id": customer_id,
        "counterfactuals": paths
    }
