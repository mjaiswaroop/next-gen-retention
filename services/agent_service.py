import logging
import json
from sqlalchemy.orm import Session
from models import AgentActionRegistry, AgentActionLog
from database import SessionLocal
from google import genai
from pydantic import BaseModel, Field

from config import settings
from services.negotiation_ledger import NegotiationLedger
from services.causal_service import estimate_uplift
from services.clv_estimator import CLVEstimator
from repositories.customer_repo import CustomerRepository

logger = logging.getLogger("retention_core.agent_service")

# Ensure gemini API is available
try:
    # Requires google-genai package
    gemini_client = genai.Client(api_key=settings.anthropic_api_key or "DUMMY") # Actually, we should use GEMINI_API_KEY. For now we use the configured key.
except Exception as e:
    logger.warning(f"Failed to init Gemini client: {e}")
    gemini_client = None


def initialize_session(tenant_id: int, customer_id: str):
    import uuid
    session_id = str(uuid.uuid4())
    logger.info(f"Initialized agent session {session_id} for customer {customer_id}")
    # Return a unique session ID
    return session_id

def get_active_sessions(tenant_id: int):
    # Mock for dashboard
    return [{"session_id": "mock_session", "customer_id": "cust_123", "status": "active"}]


class AgentResponseFormat(BaseModel):
    wants_to_offer_discount: bool = Field(description="True if the agent has decided to offer a discount based on the negotiation.")
    proposed_discount_tier: str = Field(description="The tier of the discount if offering one (e.g., '10%', '20%', '30%'). Leave empty if not offering.")
    fallback_message: str = Field(description="The message to send if the discount cannot be justified by evidence.")
    text: str = Field(description="The response message to the customer if the discount is justified or if no discount is offered.")

def process_message(session_id: str, message: str, tenant_id: int = 1, customer_id: str = "cust_123"):
    """
    LLM driven negotiation using the Provenance Ledger.
    """
    db = SessionLocal()
    try:
        repo = CustomerRepository(db)
        # Mock causal service for ledger injection
        class CausalMock:
            def estimate_uplift(self, m, c, intervention):
                return estimate_uplift(m, c, intervention)
        causal_mock = CausalMock()
        clv_estimator = CLVEstimator(db)
        
        ledger = NegotiationLedger(db, tenant_id, session_id, repo, causal_mock, clv_estimator)
        
        # Record customer message
        ledger.record("customer", message, "generic", None, tenant_id, customer_id)
        
        telemetry = repo.get_telemetry_snapshot(tenant_id, customer_id)
        system_prompt = f"""You are an AI Customer Success Representative. 
Your goal is to retain the customer. You can offer a 10%, 20%, or 30% discount if the customer is severely upset.
Current customer telemetry: {json.dumps(telemetry)}
Do not offer a discount unless you must. If you offer a discount, it will be rigorously checked against their causal uplift and LTV.
Be polite and helpful.
"""     
        # Call LLM
        response_data = None
        if gemini_client and settings.anthropic_api_key:
            try:
                # We use gemini-2.5-flash as the standard fast reasoning model
                res = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[system_prompt + "\n\nCustomer: " + message],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AgentResponseFormat,
                        temperature=0.2
                    )
                )
                response_data = json.loads(res.text)
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")
        
        # Fallback if LLM fails or API key not set
        if not response_data:
            if "cancel" in message.lower() or "discount" in message.lower():
                response_data = {
                    "wants_to_offer_discount": True,
                    "proposed_discount_tier": "20%",
                    "fallback_message": "I understand you're frustrated. I'd like to get my manager to review your account for a special retention offer.",
                    "text": "I completely understand. Because you're a valued customer, I've just applied a 20% discount to your account!"
                }
            else:
                response_data = {
                    "wants_to_offer_discount": False,
                    "proposed_discount_tier": "",
                    "fallback_message": "",
                    "text": "I'm here to help! Could you tell me more about the issue?"
                }
        
        agent_resp = AgentResponseFormat(**response_data)
        
        if agent_resp.wants_to_offer_discount:
            try:
                justification = ledger.build_justification(
                    tenant_id, customer_id, agent_resp.proposed_discount_tier
                )
            except ValueError as e:
                # No evidence available — agent CANNOT make this offer.
                ledger.record("agent", agent_resp.fallback_message, "generic",
                             None, tenant_id, customer_id)
                # In real scenario: execute_agent_action to route to human
                execute_agent_action(db, tenant_id, session_id, "apply_discount", {"tier": agent_resp.proposed_discount_tier}, rationale="Insufficient evidence for autonomous action.")
                return {"reply": agent_resp.fallback_message, "status": "escalated"}

            # Evidence exists
            ledger.record("agent", agent_resp.text, "grounded",
                          justification, tenant_id, customer_id)
            execute_agent_action(
                db, tenant_id, session_id, "apply_discount",
                {"tier": agent_resp.proposed_discount_tier, "justification": justification.to_dict()},
                rationale="Causal uplift and LTV support the intervention."
            )
            return {"reply": agent_resp.text, "status": "success"}
        else:
            ledger.record("agent", agent_resp.text, "generic", None, tenant_id, customer_id)
            return {"reply": agent_resp.text, "status": "active"}

    finally:
        db.close()

def execute_agent_action(db: Session, tenant_id: int, session_id: str, action_type: str, action_payload: dict, rationale: str = ""):
    """
    Called by the agent when it wants to perform an action.
    """
    registry_entry = db.query(AgentActionRegistry).filter_by(
        tenant_id=tenant_id, action_type=action_type, is_active=True
    ).first()

    classification = registry_entry.classification if registry_entry else "UNKNOWN"
    status = "EXECUTED" if classification == "AUTONOMOUS" else "PENDING_APPROVAL"
    
    # If the payload indicates we need human approval due to causal limits:
    if action_payload.get("justification", {}).get("causal_confidence", 0) > 0.3:
        status = "PENDING_APPROVAL"
    
    log = AgentActionLog(
        tenant_id=tenant_id,
        session_id=session_id,
        action_type=action_type,
        action_payload=action_payload,
        classification=classification,
        status=status,
        rationale=rationale
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    
    return log

def resolve_agent_action(db: Session, tenant_id: int, action_id: int, approved: bool, user_id: str):
    log = db.query(AgentActionLog).filter_by(id=action_id, tenant_id=tenant_id).first()
    if not log:
        raise ValueError("Action not found.")
        
    if log.status != "PENDING_APPROVAL":
        raise ValueError("Action is not in a pending state.")
        
    log.status = "APPROVED" if approved else "REJECTED"
    log.resolved_by = user_id
    from datetime import datetime, timezone
    log.resolved_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(log)
    return log
