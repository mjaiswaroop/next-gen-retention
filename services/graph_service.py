from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models import CustomerEdge, TenantConfig, Customer, EventLog
from database import SessionLocal
import json
import uuid

def ingest_edges(tenant_id: int, edges: List[Dict[str, Any]]):
    db = SessionLocal()
    try:
        new_edges = []
        for e in edges:
            edge = CustomerEdge(
                tenant_id=tenant_id,
                source_customer_id=e["source_customer_id"],
                target_customer_id=e["target_customer_id"],
                edge_type=e.get("edge_type", "explicit"),
                weight=e.get("weight", 1.0),
                confidence_score=1.0
            )
            new_edges.append(edge)
        
        # Merge or add all (simplistic insert for now, ignoring unique constraint violations)
        for e in new_edges:
            existing = db.query(CustomerEdge).filter_by(
                tenant_id=e.tenant_id,
                source_customer_id=e.source_customer_id,
                target_customer_id=e.target_customer_id
            ).first()
            if not existing:
                db.add(e)
        db.commit()
    finally:
        db.close()

def infer_relationships(tenant_id: int):
    """
    Infers new edges based on shared signals like payment friction or recency similarity.
    (This simulates finding shared payment methods, IP addresses etc. in a real system)
    """
    db = SessionLocal()
    try:
        config = db.query(TenantConfig).filter_by(tenant_id=tenant_id).first()
        if not config or not config.enable_inferred_edges:
            return 0
        
        # Very basic inference: customers with exactly the same payment_friction_index
        # Assuming in a real system, we'd check actual payment tokens from EventLog
        customers = db.query(Customer).filter_by(merchant_id=tenant_id).all()
        
        inferred_count = 0
        # Check all pairs
        for i in range(len(customers)):
            for j in range(i + 1, len(customers)):
                c1 = customers[i]
                c2 = customers[j]
                
                # Rule: if they have identical non-zero payment friction, infer they share a payment method
                if c1.payment_friction_index > 0 and abs(c1.payment_friction_index - c2.payment_friction_index) < 0.001:
                    existing = db.query(CustomerEdge).filter_by(
                        tenant_id=tenant_id,
                        source_customer_id=c1.user_id,
                        target_customer_id=c2.user_id
                    ).first()
                    
                    if not existing:
                        inferred_count += 1
                        edge1 = CustomerEdge(
                            tenant_id=tenant_id,
                            source_customer_id=c1.user_id,
                            target_customer_id=c2.user_id,
                            edge_type="inferred",
                            weight=0.5,
                            confidence_score=0.8,
                            inference_basis={"signal": "shared_payment_profile"}
                        )
                        # Bi-directional
                        edge2 = CustomerEdge(
                            tenant_id=tenant_id,
                            source_customer_id=c2.user_id,
                            target_customer_id=c1.user_id,
                            edge_type="inferred",
                            weight=0.5,
                            confidence_score=0.8,
                            inference_basis={"signal": "shared_payment_profile"}
                        )
                        db.add(edge1)
                        db.add(edge2)
        
        db.commit()
        return inferred_count
    finally:
        db.close()


def propagate_contagion(*args, **kwargs): return {}
def compute_centrality(*args, **kwargs): return {}

def get_contagion_risk_nodes(tenant_id: int) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        config = db.query(TenantConfig).filter_by(tenant_id=tenant_id).first()
        enable_inferred = config.enable_inferred_edges if config else False

        query = db.query(CustomerEdge).filter_by(tenant_id=tenant_id)
        if not enable_inferred:
            query = query.filter(CustomerEdge.edge_type == "explicit")
        
        edges = query.all()
        
        # Simple representation for the UI
        # We compute 'cascade_risk' by summing weights of outgoing edges for each node
        node_scores = {}
        links = []
        for e in edges:
            node_scores[e.source_customer_id] = node_scores.get(e.source_customer_id, 0) + e.weight
            links.append({
                "source": e.source_customer_id,
                "target": e.target_customer_id,
                "type": e.edge_type,
                "confidence": e.confidence_score
            })
            
        # Get customer details for nodes
        nodes = []
        for user_id, score in sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[:50]:
            cust = db.query(Customer).filter_by(merchant_id=tenant_id, user_id=user_id).first()
            if cust:
                nodes.append({
                    "user_id": user_id,
                    "cascade_risk": score,
                    "churn_probability": cust.churn_probability,
                    "monetary_value": cust.monetary_value
                })
        
        return {"nodes": nodes, "links": links}
    finally:
        db.close()
