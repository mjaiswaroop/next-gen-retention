"""
api/routes/twin.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from auth import get_current_user, require_role
from services.twin_service import run_twin_simulations

router = APIRouter()

class TwinRequest(BaseModel):
    customer_id: str
    scenarios: List[str]

@router.post("/simulate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def simulate_twin(payload: TwinRequest, current_user: dict = Depends(get_current_user)):
    """
    Runs Monte Carlo simulations on the customer's digital twin for various scenarios.
    """
    result = run_twin_simulations(current_user["tenant_id"], payload.customer_id, payload.scenarios)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result
