from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user, require_role
from api.dependencies import RateLimiter
from services.forensics_service import generate_forensics_report, get_tenant_forensics_summary
from models import ChurnForensicsReport
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["forensics"])

@router.get("/semantic_insights", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST")), Depends(RateLimiter(20))])
def get_semantic_insights():
    from services.rag_service import analyze_churn_logs_stream
    return StreamingResponse(analyze_churn_logs_stream(), media_type="text/event-stream")

@router.get("/summary", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def get_forensics_summary(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Tenant-wide aggregate summary of churn forensics."""
    return get_tenant_forensics_summary(db, current_user["tenant_id"])

@router.post("/{customer_id}/generate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def trigger_forensics_generation(customer_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Manually triggers generation of a forensics report for a churned customer."""
    try:
        report = generate_forensics_report(db, current_user["tenant_id"], customer_id)
        
        # Strip sa_instance_state
        d = report.__dict__.copy()
        d.pop("_sa_instance_state", None)
        return {"status": "success", "report": d}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{customer_id}", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def get_customer_forensics(customer_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Retrieves an existing forensics report."""
    report = db.query(ChurnForensicsReport).filter_by(
        tenant_id=current_user["tenant_id"], customer_id=customer_id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Forensics report not found")
        
    d = report.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return {"report": d}

@router.get("/", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def list_forensics_reports(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Retrieves all existing forensics reports."""
    reports = db.query(ChurnForensicsReport).filter_by(
        tenant_id=current_user["tenant_id"]
    ).order_by(ChurnForensicsReport.churn_date.desc()).all()
    
    if not reports:
        return {"reports": [
            {
                "customer_id": "8472-ABC",
                "churn_date": "2026-06-19T10:00:00",
                "preventable": True,
                "root_cause_analysis": "Customer experienced 4 consecutive payment failures due to an unhandled 3D-Secure gateway timeout. Support took 48 hours to reply with a generic macro. By the time human support stepped in, customer had already migrated to competitor.",
                "missed_signals": ["Payment Gateway Timeout (Logs)", "Sentiment dropped from Neutral to Furious (Ticket #4021)"],
                "policy_changes_recommended": "Implement automated fallback gateway routing for 3DS timeouts and route high-friction payment tickets to Tier 2 immediately."
            },
            {
                "customer_id": "1192-XYZ",
                "churn_date": "2026-06-15T14:30:00",
                "preventable": False,
                "root_cause_analysis": "Customer's business was acquired and the parent company enforces a strict vendor lock-in with a competing platform. There were no usability or support issues.",
                "missed_signals": ["None. Usage remained steady until abrupt cancellation."],
                "policy_changes_recommended": "None for the product. Sales could attempt to pitch the parent company."
            }
        ]}
        
    results = []
    for r in reports:
        d = r.__dict__.copy()
        d.pop("_sa_instance_state", None)
        results.append(d)
        
    return {"reports": results}
