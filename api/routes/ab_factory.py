import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from sqlalchemy.orm import Session

from database import get_db
from auth import require_role
from api.dependencies import RateLimiter
from services.campaign_optimizer import CampaignOptimizerService

router = APIRouter()
logger = logging.getLogger("retention_core.ab_factory")

class GenerateVariantsRequest(BaseModel):
    base_prompt: str
    target_audience: str

@router.post("/generate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER")), Depends(RateLimiter(20))])
def generate_variants(req: GenerateVariantsRequest, db: Session = Depends(get_db)):
    service = CampaignOptimizerService(db)
    variants = service.generate_variants(req.base_prompt, req.target_audience)
    return {"variants": variants}

class SimulateTestRequest(BaseModel):
    variants: List[Dict]

@router.post("/simulate_test", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def simulate_test(req: SimulateTestRequest, db: Session = Depends(get_db)):
    service = CampaignOptimizerService(db)
    results = service.simulate_live_test(req.variants)
    return results
