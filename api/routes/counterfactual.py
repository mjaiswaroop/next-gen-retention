"""
api/routes/counterfactual.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_role
from services.counterfactual_service import generate_counterfactuals

router = APIRouter()

class CFRequest(BaseModel):
    customer_id: str
    max_counterfactuals: int = 5

@router.post("/generate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def get_save_paths(payload: CFRequest, current_user: dict = Depends(get_current_user)):
    """
    Uses DiCE-ML to generate actionable save paths that reduce churn probability.
    """
    result = generate_counterfactuals(
        current_user["tenant_id"], 
        payload.customer_id, 
        payload.max_counterfactuals
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result
