"""
api/routes/compliance.py
"""
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user, require_role
from services import compliance_service

compliance_router = APIRouter()
router = compliance_router

@compliance_router.delete("/erasure/{customer_id}", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def execute_erasure(customer_id: str, current_user: dict = Depends(get_current_user)):
    """GDPR/CCPA Right to Erasure cascade delete."""
    try:
        result = compliance_service.erase_customer(
            tenant_id=current_user["tenant_id"],
            customer_id=customer_id,
            requested_by=current_user["user_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
