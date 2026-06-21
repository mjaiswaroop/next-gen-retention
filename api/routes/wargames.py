import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import require_role, get_current_user
from services.simulation_service import SimulationService

router = APIRouter()
logger = logging.getLogger("retention_core.wargames")

class RunSimulationRequest(BaseModel):
    segment: str = None
    email_draft: str
    sample_size: int = 5

@router.post("/simulate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def run_simulation(req: RunSimulationRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    service = SimulationService(db)
    result = service.run_war_game(
        merchant_id=current_user["tenant_id"],
        segment=req.segment,
        email_draft=req.email_draft,
        sample_size=req.sample_size
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
