"""
api/routes/agent_ws.py
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Any

from auth import get_current_user, require_role
from services.agent_service import initialize_session, process_message, get_active_sessions

router = APIRouter()
logger = logging.getLogger("retention_core.agent_ws")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_personal_message(self, message: str, session_id: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(message)

manager = ConnectionManager()

# NOTE: WebSocket auth is tricky. For demo purposes, we assume the client 
# negotiates the session ID via a standard REST call first, then connects.
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Process with Agent Service
            result = process_message(session_id, data)
            
            if "error" in result:
                await manager.send_personal_message(json.dumps({"error": result["error"]}), session_id)
                break
                
            response = {
                "reply": result["reply"],
                "status": result["status"]
            }
            await manager.send_personal_message(json.dumps(response), session_id)
            
            if result["status"] in ("success", "escalated", "failed"):
                break
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("[agent] WebSocket disconnected for session %s", session_id)
    except Exception as e:
        logger.error("[agent] WebSocket error: %s", e)
        manager.disconnect(session_id)

@router.post("/start", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def start_negotiation(customer_id: str, current_user: dict = Depends(get_current_user)):
    """Initialize a new agent session and return the session ID for WebSocket connection."""
    session_id = initialize_session(current_user["tenant_id"], customer_id)
    return {"session_id": session_id, "ws_url": f"ws://localhost:8000/api/v1/agent/ws/{session_id}"}

@router.get("/sessions", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def list_active_sessions(current_user: dict = Depends(get_current_user)):
    """Returns active negotiation sessions for the dashboard."""
    sessions = get_active_sessions(current_user["tenant_id"])
    return {"sessions": sessions}

from sqlalchemy.orm import Session
from database import get_db
from services.agent_service import resolve_agent_action
from models import AgentActionLog

@router.get("/actions", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER", "ANALYST"))])
def get_agent_actions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Returns all agent actions."""
    tenant_id = current_user["tenant_id"]
    actions = db.query(AgentActionLog).filter_by(tenant_id=tenant_id).order_by(AgentActionLog.requested_at.desc()).all()
    results = []
    for a in actions:
        d = a.__dict__.copy()
        d.pop("_sa_instance_state", None)
        results.append(d)
    return {"actions": results}

@router.get("/actions/pending", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def get_pending_agent_actions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Returns pending agent actions requiring approval."""
    tenant_id = current_user["tenant_id"]
    actions = db.query(AgentActionLog).filter_by(tenant_id=tenant_id, status="PENDING_APPROVAL").order_by(AgentActionLog.requested_at.desc()).all()
    results = []
    for a in actions:
        d = a.__dict__.copy()
        d.pop("_sa_instance_state", None)
        results.append(d)
    return {"actions": results}

from pydantic import BaseModel

class ResolveActionRequest(BaseModel):
    approved: bool

@router.post("/actions/{action_id}/resolve", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def resolve_action(action_id: int, req: ResolveActionRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Approves or rejects a pending agent action."""
    try:
        log = resolve_agent_action(db, current_user["tenant_id"], action_id, req.approved, current_user["user_id"])
        d = log.__dict__.copy()
        d.pop("_sa_instance_state", None)
        return {"status": "success", "action": d}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/negotiations/{session_id}/replay", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST"))])
def replay_negotiation(session_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Returns the cryptographically hashed transcript of an agent session,
    with claims annotated as grounded vs generic.
    """
    from services.negotiation_ledger import NegotiationLedger
    from repositories.customer_repo import CustomerRepository
    from services.clv_estimator import CLVEstimator
    
    tenant_id = current_user["tenant_id"]
    # Rehydrate the ledger to read the chain
    repo = CustomerRepository(db)
    
    class CausalMock:
        def estimate_uplift(self, m, c, intervention):
            pass
            
    ledger = NegotiationLedger(db, tenant_id, session_id, repo, CausalMock(), CLVEstimator(db))
    
    is_valid = ledger.verify_chain()
    integrity_score = ledger.negotiation_integrity_score()
    
    entries = []
    for e in ledger.entries:
        entries.append({
            "sequence": e.sequence,
            "timestamp": e.timestamp.isoformat(),
            "speaker": e.speaker,
            "message": e.message,
            "claim_type": e.claim_type,
            "justification": e.justification.to_dict() if e.justification else None,
            "entry_hash": e.entry_hash
        })
        
    return {
        "session_id": session_id,
        "is_chain_valid": is_valid,
        "integrity_score": integrity_score,
        "transcript": entries
    }
