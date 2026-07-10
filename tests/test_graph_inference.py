import pytest
from models import Customer, CustomerEdge, TenantConfig, Merchant
from database import SessionLocal
from services.graph_service import infer_relationships, ingest_edges

def test_graph_inference():
    from database import active_tenant_id
    db = SessionLocal()
    tenant_id = 999
    active_tenant_id.set(tenant_id)
    
    try:
        # Setup: Create merchant
        merchant = Merchant(id=tenant_id, name=f"Test Merchant {tenant_id}", api_key=f"test_key_{tenant_id}")
        db.add(merchant)
        db.commit()
        
        # Setup: Create tenant config with inference disabled initially
        config = TenantConfig(tenant_id=tenant_id, enable_inferred_edges=False)
        db.add(config)
        
        # Setup: Create two customers with identical payment friction > 0
        c1 = Customer(
            merchant_id=tenant_id,
            user_id="cust_A",
            recency_days=10,
            frequency=5,
            monetary_value=100.0,
            payment_friction_index=0.85
        )
        c2 = Customer(
            merchant_id=tenant_id,
            user_id="cust_B",
            recency_days=15,
            frequency=3,
            monetary_value=150.0,
            payment_friction_index=0.85
        )
        c3 = Customer(
            merchant_id=tenant_id,
            user_id="cust_C",
            recency_days=5,
            frequency=10,
            monetary_value=500.0,
            payment_friction_index=0.10 # different
        )
        db.add_all([c1, c2, c3])
        db.commit()

        # Run inference with it disabled
        count = infer_relationships(tenant_id)
        assert count == 0

        # Enable inference
        config.enable_inferred_edges = True
        db.commit()

        # Run inference again
        count = infer_relationships(tenant_id)
        assert count == 1 # 1 pair inferred (A and B)

        # Check DB
        edges = db.query(CustomerEdge).filter_by(tenant_id=tenant_id, edge_type="inferred").all()
        assert len(edges) == 2 # bi-directional

        assert edges[0].source_customer_id in ("cust_A", "cust_B")
        assert edges[0].target_customer_id in ("cust_A", "cust_B")
        
    finally:
        # Cleanup
        db.query(CustomerEdge).filter_by(tenant_id=tenant_id).delete()
        db.query(Customer).filter_by(merchant_id=tenant_id).delete()
        db.query(TenantConfig).filter_by(tenant_id=tenant_id).delete()
        db.query(Merchant).filter_by(id=tenant_id).delete()
        db.commit()
        db.close()
