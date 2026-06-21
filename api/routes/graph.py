"""
api/routes/graph.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from auth import get_current_user, require_role
from services.graph_service import ingest_edges, get_contagion_risk_nodes, infer_relationships
from database import SessionLocal
from models import TenantConfig

router = APIRouter()

class EdgeInput(BaseModel):
    source_customer_id: str
    target_customer_id: str
    edge_type: str
    weight: float

class EdgesRequest(BaseModel):
    edges: List[EdgeInput]

@router.post("/edges", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def add_graph_edges(payload: EdgesRequest, current_user: dict = Depends(get_current_user)):
    """Ingest new customer relationship edges into the graph."""
    edges_dict = [{"source_customer_id": e.source_customer_id, 
                   "target_customer_id": e.target_customer_id, 
                   "edge_type": e.edge_type, 
                   "weight": e.weight} for e in payload.edges]
    ingest_edges(current_user["tenant_id"], edges_dict)
    return {"status": "success", "edges_ingested": len(edges_dict)}

@router.get("/contagion-risk", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def fetch_contagion_risk(current_user: dict = Depends(get_current_user)):
    """Fetch nodes ranked by cascade revenue at risk, along with links."""
    data = get_contagion_risk_nodes(current_user["tenant_id"])
    return {"high_risk_nodes": data["nodes"], "links": data["links"]}

@router.post("/infer", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def trigger_infer_relationships(current_user: dict = Depends(get_current_user)):
    """Triggers inference logic if the tenant has enabled it."""
    count = infer_relationships(current_user["tenant_id"])
    return {"status": "success", "inferred_edges_count": count}

class ConfigPayload(BaseModel):
    enable_inferred_edges: bool

@router.put("/config", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def update_graph_config(payload: ConfigPayload, current_user: dict = Depends(get_current_user)):
    """Toggle inferred edges configuration for tenant."""
    db = SessionLocal()
    try:
        config = db.query(TenantConfig).filter_by(tenant_id=current_user["tenant_id"]).first()
        if not config:
            config = TenantConfig(tenant_id=current_user["tenant_id"])
            db.add(config)
        config.enable_inferred_edges = payload.enable_inferred_edges
        db.commit()
        return {"status": "success", "enable_inferred_edges": config.enable_inferred_edges}
    finally:
        db.close()

@router.get("/config", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST"))])
def get_graph_config(current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        config = db.query(TenantConfig).filter_by(tenant_id=current_user["tenant_id"]).first()
        return {"enable_inferred_edges": config.enable_inferred_edges if config else False}
    finally:
        db.close()
