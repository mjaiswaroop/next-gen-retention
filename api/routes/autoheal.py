import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from services.auto_heal_service import AutoHealService

router = APIRouter()
logger = logging.getLogger("retention_core.autoheal")

service = AutoHealService()

@router.get("/errors", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def get_recent_errors():
    errors = service.get_recent_errors()
    return {"errors": errors}

class GeneratePatchRequest(BaseModel):
    target_file: str
    traceback: str

@router.post("/generate_patch", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def generate_patch(req: GeneratePatchRequest):
    try:
        patch = service.generate_patch(req.target_file, req.traceback)
        return patch
    except Exception as e:
        logger.error(f"Failed to generate patch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ApplyPatchRequest(BaseModel):
    target_file: str
    fixed_code: str

@router.post("/apply_patch", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def apply_patch(req: ApplyPatchRequest):
    success = service.apply_patch(req.target_file, req.fixed_code)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to write patch to file.")
