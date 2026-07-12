"""
app.py — FastAPI Application Entrypoint
=======================================
Implements the core FastAPI server with all 10 enterprise sections routed.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import engine, Base
import models
from observability.logging_config import configure_logging, bind_context, clear_context
from observability.metrics import setup_metrics
from observability.tracing import configure_tracing

# Import Routers (Assume these exist in api/routes/)
from api.routes import auth, compliance, bi, campaigns, causal, twin, emotion, graph, counterfactual, agent_ws, users, predict, priority, forensics, autoheal, wargames, ab_factory, radar

configure_logging()
logger = logging.getLogger("retention_core.api")

import alembic.config
import alembic.command

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Anchor v3.0 API...")
    yield
    # Shutdown actions
    logger.info("Shutting down Anchor API.")

app = FastAPI(
    title="Anchor API",
    version="3.0.0",
    lifespan=lifespan,
)

setup_metrics(app)

from fastapi.responses import JSONResponse
import traceback
from fastapi import HTTPException
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    err_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": err_str})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds request ID to structlog context."""
    async def dispatch(self, request: Request, call_next):
        import uuid
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        bind_context(trace_id=trace_id, path=request.url.path)
        try:
            response = await call_next(request)
            return response
        finally:
            clear_context()

app.add_middleware(RequestContextMiddleware)

# Include Routers
from api.routes.compliance import router as compliance_router
from api.routes.wargames import router as wargames_router
from api.routes.forensics import router as forensics_router
from api.routes.data import router as data_router

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users (RBAC)"])
app.include_router(causal.router, prefix="/api/v1/causal", tags=["Causal Engine"])
app.include_router(predict.router, prefix="/api/v1/predict", tags=["Prediction"])
app.include_router(priority.router, prefix="/api/v1/priority", tags=["Economic Priority"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(ab_factory.router, prefix="/api/v1/ab", tags=["A/B Testing"])
app.include_router(bi.router, prefix="/api/v1/bi", tags=["Business Intelligence"])
app.include_router(radar.router, prefix="/api/v1/radar", tags=["Radar (Contagion & Emotion)"])
app.include_router(twin.router, prefix="/api/v1/twin", tags=["Digital Twin"])
app.include_router(autoheal.router, prefix="/api/v1/autoheal", tags=["Auto-Heal"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Contagion Graph"])
app.include_router(emotion.router, prefix="/api/v1/emotion", tags=["Emotion Detection"])
app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["Compliance"])
app.include_router(wargames_router, prefix="/api/v1/wargames", tags=["Wargames"])
app.include_router(forensics_router, prefix="/api/v1/forensics", tags=["Churn Forensics"])
app.include_router(data_router, prefix="/api/v1/data", tags=["Data Ingestion"])
app.include_router(counterfactual.router, prefix="/api/v1/counterfactual", tags=["Save Path Counterfactuals"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/readiness")
async def readiness_check():
    from database import SessionLocal
    from sqlalchemy import text
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not ready")
