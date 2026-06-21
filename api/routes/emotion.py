"""
api/routes/emotion.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_role
from services.emotion_service import analyze_ticket_emotion

router = APIRouter()

class EmotionRequest(BaseModel):
    customer_id: str
    ticket_id: str
    ticket_text: str

@router.post("/analyze", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def analyze_emotion(payload: EmotionRequest, current_user: dict = Depends(get_current_user)):
    """
    Analyzes support ticket text using the HuggingFace emotion classifier,
    updates the customer's rolling emotion signal, and returns risk scores.
    """
    result = analyze_ticket_emotion(
        current_user["tenant_id"], 
        payload.customer_id, 
        payload.ticket_id, 
        payload.ticket_text
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result
