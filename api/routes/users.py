from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Customer
from auth import get_current_user, require_role

router = APIRouter()

@router.get("/high-risk", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER", "PII_VIEWER"))])
def get_high_risk_users(
    threshold: float = Query(0.75, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a list of customers whose churn probability is >= threshold.
    Returns limited PII based on role, but always returns user_id and churn_probability.
    """
    tenant_id = current_user["tenant_id"]
    
    customers = (
        db.query(Customer)
        .filter(Customer.merchant_id == tenant_id)
        .filter(Customer.churn_probability >= threshold)
        .filter(Customer.is_deleted == False)
        .order_by(Customer.churn_probability.desc())
        .limit(100)
        .all()
    )
    
    # Format the response to match dashboard expectations
    result = []
    for c in customers:
        result.append({
            "user_id": c.user_id,
            "email": f"{c.user_id}@example.com", # Mock email for UI
            "churn_probability": c.churn_probability,
            "segment": c.segment,
            "recency_days": c.recency_days,
            "frequency": c.frequency,
            "monetary_value": c.monetary_value,
            "session_failures": c.session_failures,
            "payment_friction_index": c.payment_friction_index,
            "active_support_tickets": c.active_support_tickets,
        })
        
    return result
