import pytest
from sqlalchemy.orm import Session
from models import AgentActionRegistry, AgentActionLog, Merchant, AgentSession
from database import SessionLocal
from services.agent_service import execute_agent_action, resolve_agent_action

def test_agent_governance():
    db = SessionLocal()
    tenant_id = 998
    session_id = "test_session_123"
    
    try:
        # Setup: Create merchant
        merchant = Merchant(id=tenant_id, name="Test Merchant 2", api_key="test_key_998")
        db.add(merchant)
        db.commit()
        
        session = AgentSession(session_id=session_id, tenant_id=tenant_id)
        db.add(session)
        db.commit()
        
        # Setup: Create whitelist registry
        reg_auto = AgentActionRegistry(tenant_id=tenant_id, action_type="read_data", classification="AUTONOMOUS")
        reg_approve = AgentActionRegistry(tenant_id=tenant_id, action_type="send_email", classification="REQUIRES_APPROVAL")
        db.add_all([reg_auto, reg_approve])
        db.commit()
        
        # Test 1: Action NOT in whitelist
        log1 = execute_agent_action(db, tenant_id, session_id, "delete_db", {"table": "users"}, "I want to delete everything")
        assert log1.status == "REJECTED"
        assert log1.classification == "UNKNOWN"
        
        # Test 2: AUTONOMOUS action
        log2 = execute_agent_action(db, tenant_id, session_id, "read_data", {"query": "SELECT *"}, "Just looking")
        assert log2.status == "EXECUTED"
        assert log2.classification == "AUTONOMOUS"
        
        # Test 3: REQUIRES_APPROVAL action
        log3 = execute_agent_action(db, tenant_id, session_id, "send_email", {"to": "user@test.com"}, "User needs intervention")
        assert log3.status == "PENDING_APPROVAL"
        assert log3.classification == "REQUIRES_APPROVAL"
        assert log3.rationale == "User needs intervention"
        
        # Test 4: Approve pending action
        log4 = resolve_agent_action(db, tenant_id, log3.id, approved=True, user_id="admin_1")
        assert log4.status == "APPROVED"
        assert log4.resolved_by == "admin_1"
        assert log4.resolved_at is not None
        
        # Test 5: Re-trigger rejected/resolved action (should fail)
        with pytest.raises(ValueError, match="Action is not in a pending state"):
            resolve_agent_action(db, tenant_id, log4.id, approved=False, user_id="admin_2")
            
        # Test 6: Tenant isolation
        # Another tenant trying to approve log3
        with pytest.raises(ValueError, match="Action not found"):
            resolve_agent_action(db, 9999, log3.id, approved=True, user_id="admin_1")

    finally:
        db.rollback()
        # Cleanup
        db.query(AgentActionLog).filter_by(tenant_id=tenant_id).delete()
        db.query(AgentActionRegistry).filter_by(tenant_id=tenant_id).delete()
        db.query(AgentSession).filter_by(tenant_id=tenant_id).delete()
        db.query(Merchant).filter_by(id=tenant_id).delete()
        db.commit()
        db.close()
