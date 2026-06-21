"""
api/routes/bi.py
"""
from fastapi import APIRouter, Depends
from auth import get_current_user, require_role
from services import bi_service

bi_router = APIRouter()
router = bi_router

@bi_router.get("/digest", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST"))])
def get_digest(current_user: dict = Depends(get_current_user)):
    """Returns the executive digest."""
    return bi_service.compile_executive_digest(current_user["tenant_id"])
