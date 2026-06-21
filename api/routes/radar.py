import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth import require_role
from services.radar_service import RadarService

router = APIRouter()
logger = logging.getLogger("retention_core.radar")

@router.get("/scan", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST"))])
def scan_competitors():
    service = RadarService()
    alerts = service.scan_market()
    return {"alerts": alerts}
