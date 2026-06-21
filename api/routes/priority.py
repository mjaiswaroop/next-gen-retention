from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from auth import get_current_user, require_role
from services.priority_service import compute_priority_queue

router = APIRouter()

@router.get("/queue", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def get_priority_queue(current_user: dict = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """
    Returns the customer priority queue sorted by Expected Value Score (EVS).
    """
    result = compute_priority_queue(current_user["tenant_id"])
    return result
