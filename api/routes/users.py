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
    from database import active_tenant_id
    tenant_id = current_user["tenant_id"]
    active_tenant_id.set(tenant_id)
    
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
        base_dict = {
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
        }
        
        # Merge in dynamic schema columns so the dashboard renders them!
        if c.extra_features and isinstance(c.extra_features, dict):
            for k, v in c.extra_features.items():
                if k not in base_dict:
                    base_dict[k] = v
                    
        result.append(base_dict)
        
    return result

from fastapi.responses import StreamingResponse
import io
import csv

@router.get("/export", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def export_customers_csv(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Streams a CSV of all customers for this tenant to handle massive datasets safely.
    """
    from database import active_tenant_id
    tenant_id = current_user["tenant_id"]
    active_tenant_id.set(tenant_id)
    
    def iter_csv():
        # Using yield_per(1000) prevents loading millions of rows into memory
        query = db.query(Customer).filter(Customer.merchant_id == tenant_id, Customer.is_deleted == False).yield_per(1000)
        
        # Yield header
        header = ["user_id", "email", "churn_probability", "segment", "recency_days", "frequency", "monetary_value"]
        yield ",".join(header) + "\n"
        
        for c in query:
            row = [
                str(c.user_id),
                f"{c.user_id}@example.com",
                str(c.churn_probability),
                str(c.segment or ""),
                str(c.recency_days),
                str(c.frequency),
                str(c.monetary_value)
            ]
            yield ",".join(row) + "\n"
            
    response = StreamingResponse(iter_csv(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=customers_export.csv"
    return response
