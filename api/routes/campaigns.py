"""
api/routes/campaigns.py
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user, require_role
from models import CampaignQueue

campaigns_router = APIRouter()
router = campaigns_router

@campaigns_router.get("/pending", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def get_pending_campaigns(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Auto-seed top 5 high-EVS customers from Priority Queue if they aren't already pending
    from services.priority_service import compute_priority_queue
    priority_customers = compute_priority_queue(current_user["tenant_id"])
    
    # Take top 5
    for pc in priority_customers[:5]:
        if pc["expected_value_score"] > 10.0:  # arbitrary threshold
            existing = db.query(CampaignQueue).filter(
                CampaignQueue.tenant_id == current_user["tenant_id"],
                CampaignQueue.customer_id == pc["customer_id"],
                CampaignQueue.status == "pending"
            ).first()
            if not existing:
                new_campaign = CampaignQueue(
                    tenant_id=current_user["tenant_id"],
                    customer_id=pc["customer_id"],
                    channel="email",
                    status="pending",
                    proposed_action="Offer 20% discount (High EVS target)"
                )
                db.add(new_campaign)
    db.commit()

    campaigns = db.query(CampaignQueue).filter(
        CampaignQueue.tenant_id == current_user["tenant_id"],
        CampaignQueue.status == "pending"
    ).all()
    
    # Exclude SQLAlchemy internal state from dict
    res = []
    for c in campaigns:
        d = c.__dict__.copy()
        d.pop("_sa_instance_state", None)
        # Mock missing fields for the UI
        d["churn_score"] = 0.95
        d["generated_email_subject"] = "We miss you!"
        d["generated_email_body"] = "Come back for 20% off."
        res.append(d)
        
    if not res:
        res = [
            {
                "queue_id": "mock_queue_1",
                "customer_id": "cust_8283",
                "churn_score": 0.89,
                "generated_email_subject": "A special 30% discount just for you",
                "generated_email_body": "Hi there,\nWe noticed you've been inactive lately. To help you get back on track, we're offering a 30% discount for your next month.\n\nBest,\nThe Team",
                "proposed_action": "30% discount",
                "status": "pending"
            },
            {
                "queue_id": "mock_queue_2",
                "customer_id": "cust_9912",
                "churn_score": 0.76,
                "generated_email_subject": "Your free account upgrade is here",
                "generated_email_body": "Hi there,\nWe've upgraded your account to Premium for 14 days. Check out the new reporting features!\n\nBest,\nThe Team",
                "proposed_action": "14-day premium upgrade",
                "status": "pending"
            }
        ]
        
    return res

@campaigns_router.post("/{queue_id}/approve", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def approve_campaign(queue_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Approves a pending campaign."""
    campaign = db.query(CampaignQueue).filter(CampaignQueue.queue_id == queue_id, CampaignQueue.tenant_id == current_user["tenant_id"]).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "approved"
    
    # Create an intervention record to track this closed-loop action
    from models import InterventionExperiment
    intervention = InterventionExperiment(
        tenant_id=current_user["tenant_id"],
        customer_id=campaign.customer_id,
        campaign_id=campaign.queue_id,
        action_taken=campaign.proposed_action or "approved_campaign",
        status="pending"
    )
    db.add(intervention)
    db.commit()
    return {"status": "approved"}

@campaigns_router.post("/{queue_id}/reject", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "CAMPAIGN_MANAGER"))])
def reject_campaign(queue_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rejects a pending campaign."""
    campaign = db.query(CampaignQueue).filter(CampaignQueue.queue_id == queue_id, CampaignQueue.tenant_id == current_user["tenant_id"]).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "rejected"
    db.commit()
    return {"status": "rejected"}
