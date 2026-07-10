"""
api/routes/twin.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from auth import get_current_user, require_role
from tasks.twin_tasks import simulate_twin_task
from tasks.celery_app import celery_app

router = APIRouter()

class TwinRequest(BaseModel):
    customer_id: str
    scenarios: List[str]

@router.post("/simulate", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER"))])
def simulate_twin(payload: TwinRequest, current_user: dict = Depends(get_current_user)):
    """
    Dispatches Monte Carlo simulations asynchronously to the Celery ml_worker queue.
    """
    task = simulate_twin_task.delay(current_user["tenant_id"], payload.customer_id, payload.scenarios)
    return {"task_id": task.id, "status": "PENDING"}

@router.get("/simulate/status/{task_id}")
def get_simulate_status(task_id: str):
    """
    Check the status of a Monte Carlo simulation task.
    """
    res = celery_app.AsyncResult(task_id)
    if res.state == "SUCCESS":
        return {"status": "SUCCESS", "result": res.result}
    elif res.state in ["FAILURE", "REVOKED"]:
        return {"status": res.state, "error": str(res.info)}
    return {"status": "PENDING"}
