import pytest
from sqlalchemy.orm import Session
from models import Customer, CustomerEdge, CounterfactualPath, CampaignQueue, ChurnForensicsReport, Merchant
from database import SessionLocal
from services.forensics_service import generate_forensics_report, get_tenant_forensics_summary

def test_churn_forensics():
    from database import active_tenant_id
    db = SessionLocal()
    tenant_id = 1001
    active_tenant_id.set(tenant_id)
    
    try:
        # 1. Setup Merchant and Customers
        merchant = Merchant(id=tenant_id, name=f"Test Merchant {tenant_id}", api_key=f"test_key_{tenant_id}")
        db.add(merchant)
        
        c1 = Customer(merchant_id=tenant_id, user_id="cust_1", churn_probability=0.9, monetary_value=100.0, recency_days=10, frequency=5)
        c2 = Customer(merchant_id=tenant_id, user_id="cust_2", churn_probability=0.95, monetary_value=200.0, recency_days=10, frequency=5)
        c3 = Customer(merchant_id=tenant_id, user_id="cust_3", churn_probability=0.88, monetary_value=50.0, recency_days=10, frequency=5)
        db.add_all([c1, c2, c3])
        db.commit()

        # ---------------------------------------------------------
        # Scenario 1: INTERVENTION_AVAILABLE_NOT_TAKEN (cust_1)
        # Has viable counterfactual, no campaign.
        # ---------------------------------------------------------
        db.add(CustomerEdge(tenant_id=tenant_id, source_customer_id="cust_1", target_customer_id="other", edge_type="explicit", weight=1.0))
        db.add(CounterfactualPath(tenant_id=tenant_id, customer_id="cust_1", intervention_type="discount", estimated_cost=10, predicted_risk_reduction=0.3, roi_score=2.5))
        db.commit()
        
        r1 = generate_forensics_report(db, tenant_id, "cust_1")
        assert r1.verdict == "INTERVENTION_AVAILABLE_NOT_TAKEN"
        assert r1.contagion_context["direct_connections"] == 1
        assert len(r1.counterfactual_history) == 1

        # ---------------------------------------------------------
        # Scenario 2: INTERVENTION_TAKEN_BUT_FAILED (cust_2)
        # Has campaign, still churned.
        # ---------------------------------------------------------
        db.add(CounterfactualPath(tenant_id=tenant_id, customer_id="cust_2", intervention_type="free_upgrade", estimated_cost=50, predicted_risk_reduction=0.5, roi_score=1.5))
        db.add(CampaignQueue(tenant_id=tenant_id, customer_id="cust_2", churn_score=0.95, status="sent"))
        db.commit()
        
        r2 = generate_forensics_report(db, tenant_id, "cust_2")
        assert r2.verdict == "INTERVENTION_TAKEN_BUT_FAILED"
        
        # ---------------------------------------------------------
        # Scenario 3: NO_VIABLE_INTERVENTION_FOUND (cust_3)
        # Has counterfactual, but poor ROI (<1.0)
        # ---------------------------------------------------------
        db.add(CounterfactualPath(tenant_id=tenant_id, customer_id="cust_3", intervention_type="high_cost_gift", estimated_cost=100, predicted_risk_reduction=0.1, roi_score=0.5))
        db.commit()
        
        r3 = generate_forensics_report(db, tenant_id, "cust_3")
        assert r3.verdict == "NO_VIABLE_INTERVENTION_FOUND"

        # ---------------------------------------------------------
        # Test Aggregation
        # ---------------------------------------------------------
        summary = get_tenant_forensics_summary(db, tenant_id)
        assert summary["total"] == 3
        assert summary["breakdown"]["INTERVENTION_AVAILABLE_NOT_TAKEN"] == 1
        assert summary["percentages"]["INTERVENTION_AVAILABLE_NOT_TAKEN"] == 33.33
        
    finally:
        db.rollback()
        db.query(ChurnForensicsReport).filter_by(tenant_id=tenant_id).delete()
        db.query(CampaignQueue).filter_by(tenant_id=tenant_id).delete()
        db.query(CounterfactualPath).filter_by(tenant_id=tenant_id).delete()
        db.query(CustomerEdge).filter_by(tenant_id=tenant_id).delete()
        db.query(Customer).filter_by(merchant_id=tenant_id).delete()
        db.query(Merchant).filter_by(id=tenant_id).delete()
        db.commit()
        db.close()
