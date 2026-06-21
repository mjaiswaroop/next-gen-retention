from sqlalchemy.orm import Session
from models import (
    Customer,
    CustomerEdge,
    CounterfactualPath,
    CampaignQueue,
    CampaignEvent,
    ChurnForensicsReport
)
from datetime import datetime, timezone

def generate_forensics_report(db: Session, tenant_id: int, customer_id: str):
    """
    Auto-generates a post-mortem report for a churned customer, compiling
    historical data across emotion, contagion, counterfactuals, and campaigns.
    """
    
    # 1. Check if report already exists
    existing = db.query(ChurnForensicsReport).filter_by(
        tenant_id=tenant_id, customer_id=customer_id
    ).first()
    
    if existing:
        return existing
        
    customer = db.query(Customer).filter_by(merchant_id=tenant_id, user_id=customer_id).first()
    if not customer:
        raise ValueError("Customer not found")

    # Mocking actual retrieval for time-series / complex histories for this implementation
    # In a full production system, we'd query interaction logs, daily snapshots, etc.
    
    # 1. Emotion Trajectory (mocked based on current churn probability)
    base_churn = customer.churn_probability
    emotion_trajectory = [
        {"day": -30, "risk_score": max(0.0, base_churn - 0.4), "sentiment": "neutral"},
        {"day": -15, "risk_score": max(0.0, base_churn - 0.2), "sentiment": "frustrated"},
        {"day": -7, "risk_score": max(0.0, base_churn - 0.1), "sentiment": "angry"},
        {"day": -1, "risk_score": base_churn, "sentiment": "highly_at_risk"}
    ]
    
    # 2. Contagion Context
    # Check edges where this customer is the source
    edges = db.query(CustomerEdge).filter_by(
        tenant_id=tenant_id, source_customer_id=str(customer_id)
    ).all()
    contagion_context = {
        "is_influencer": len(edges) > 3,
        "direct_connections": len(edges),
        "total_weight_at_risk": sum(e.weight for e in edges),
        "edges": [
            {"target": e.target_customer_id, "weight": e.weight, "type": e.edge_type}
            for e in edges
        ]
    }
    
    # 3. Counterfactual Paths
    paths = db.query(CounterfactualPath).filter_by(
        tenant_id=tenant_id, customer_id=str(customer_id)
    ).all()
    cf_history = [
        {
            "intervention": p.intervention_type,
            "cost": p.estimated_cost,
            "predicted_risk_reduction": p.predicted_risk_reduction,
            "roi": p.roi_score
        }
        for p in paths
    ]
    
    # 4. Campaign Actions Taken (Interventions)
    campaigns = db.query(CampaignQueue).filter_by(
        tenant_id=tenant_id, customer_id=str(customer_id)
    ).all()
    actions_taken = [
        {
            "campaign_type": c.campaign_type,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in campaigns
    ]
    
    # 5. Economic Priority
    eco_history = [
        {"day": -30, "ltv": customer.monetary_value, "priority_score": 85.0},
        {"day": -1, "ltv": customer.monetary_value, "priority_score": 90.0}
    ]
    
    # 6. Verdict Logic
    has_viable_cf = any(cf["roi"] > 1.0 for cf in cf_history)
    has_intervention = any(a["status"] in ("approved", "auto_approved", "sent") for a in actions_taken)
    
    if not cf_history:
        verdict = "INSUFFICIENT_DATA"
        reasoning = "No counterfactual paths were ever generated for this customer prior to churn."
    elif has_intervention:
        verdict = "INTERVENTION_TAKEN_BUT_FAILED"
        reasoning = f"We attempted an intervention, but it was insufficient to prevent churn. We had {len(cf_history)} modeled paths."
    elif has_viable_cf and not has_intervention:
        verdict = "INTERVENTION_AVAILABLE_NOT_TAKEN"
        reasoning = f"A positive ROI intervention was available, but no action was taken by the system or human operators."
    else:
        verdict = "NO_VIABLE_INTERVENTION_FOUND"
        reasoning = "Counterfactual models ran, but no intervention met the ROI threshold to justify cost."
        
    report = ChurnForensicsReport(
        tenant_id=tenant_id,
        customer_id=str(customer_id),
        emotion_trajectory=emotion_trajectory,
        contagion_context=contagion_context,
        counterfactual_history=cf_history,
        economic_priority_history=eco_history,
        verdict=verdict,
        reasoning=reasoning
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

def get_tenant_forensics_summary(db: Session, tenant_id: int):
    reports = db.query(ChurnForensicsReport).filter_by(tenant_id=tenant_id).all()
    total = len(reports)
    if total == 0:
        return {"total": 0, "breakdown": {}, "percentages": {}}
        
    breakdown = {}
    for r in reports:
        breakdown[r.verdict] = breakdown.get(r.verdict, 0) + 1
        
    percentages = {k: round(v / total * 100, 2) for k, v in breakdown.items()}
    
    return {
        "total": total,
        "breakdown": breakdown,
        "percentages": percentages
    }
