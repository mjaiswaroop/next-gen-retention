"""
api/routes/causal.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from auth import get_current_user, require_role
from services.causal_service import estimate_causal_effect

router = APIRouter()

class Intervention(BaseModel):
    variable: str
    value: float

class CausalRequest(BaseModel):
    customer_id: str
    interventions: List[Intervention]

@router.post("/estimate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def estimate_effect(payload: CausalRequest, current_user: dict = Depends(get_current_user)):
    """
    Runs DoWhy do-calculus on the structural causal model to estimate 
    churn probability if an intervention is applied.
    """
    interventions_dict = [{"variable": i.variable, "value": i.value} for i in payload.interventions]
    result = estimate_causal_effect(current_user["tenant_id"], payload.customer_id, interventions_dict)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result

@router.get("/validation-report", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST"))])
def get_validation_report(current_user: dict = Depends(get_current_user)):
    """
    Returns a report comparing predicted causal uplift vs actual outcomes 
    from the InterventionExperiment tracking table.
    """
    from database import SessionLocal
    from models import InterventionExperiment
    
    db = SessionLocal()
    try:
        interventions = db.query(InterventionExperiment).filter(
            InterventionExperiment.tenant_id == current_user["tenant_id"]
        ).all()
        
        success_count = sum(1 for i in interventions if i.status == "success")
        failed_count = sum(1 for i in interventions if i.status == "failed")
        pending_count = sum(1 for i in interventions if i.status == "pending")
        
        total_resolved = success_count + failed_count
        success_rate = (success_count / total_resolved) if total_resolved > 0 else 0.0
        
        return {
            "total_interventions": len(interventions),
            "pending": pending_count,
            "success": success_count,
            "failed": failed_count,
            "actual_success_rate": success_rate,
            "average_predicted_uplift": 0.15 # placeholder for actual math
        }
    finally:
        db.close()
