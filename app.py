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
    logger.info("Starting Retention Core v3.0 API...")
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic.command.upgrade(alembic_cfg, "head")
    configure_tracing(app)
    
    # Auto-seed database for seamless deployment
    from database import SessionLocal
    from models import Merchant, User
    from auth import hash_password
    import secrets
    
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.email == "admin@retentioncore.com").first()
        if not admin_exists:
            logger.info("Auto-seeding default admin account...")
            m = db.query(Merchant).filter(Merchant.name == 'Retention Core Corp').first()
            if not m:
                m = Merchant(name='Retention Core Corp', api_key=secrets.token_urlsafe(32), is_active=True)
                db.add(m)
                db.commit()
            
            u = User(tenant_id=m.id, email='admin@retentioncore.com', hashed_password=hash_password('admin123'), role='SUPER_ADMIN', is_active=True)
            db.add(u)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to auto-seed database: {e}")
    finally:
        db.close()
        
    yield
    # Shutdown
    logger.info("Shutting down Retention Core API.")

app = FastAPI(
    title="Retention Core API",
    version="3.0.0",
    lifespan=lifespan,
)

setup_metrics(app)

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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth & RBAC"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["GDPR/CCPA"])
app.include_router(bi.router, prefix="/api/v1/bi", tags=["Business Intelligence"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Automations"])
app.include_router(causal.router, prefix="/api/v1/causal", tags=["Causal Engine"])
app.include_router(twin.router, prefix="/api/v1/twin", tags=["Digital Twin"])
app.include_router(emotion.router, prefix="/api/v1/emotion", tags=["Emotion Risk Scoring"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Contagion Graph"])
app.include_router(counterfactual.router, prefix="/api/v1/counterfactual", tags=["Counterfactual Paths"])
app.include_router(agent_ws.router, prefix="/api/v1/agent", tags=["Autonomous Agent"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(forensics.router, prefix="/api/v1/forensics", tags=["Forensics"])
app.include_router(predict.router, prefix="/api/v1/predict", tags=["Predict"])
app.include_router(priority.router, prefix="/api/v1/priority", tags=["Priority Queue"])
app.include_router(autoheal.router, prefix="/api/v1/autoheal", tags=["Auto Heal"])
app.include_router(wargames.router, prefix="/api/v1/wargames", tags=["War Games"])
app.include_router(ab_factory.router, prefix="/api/v1/ab_factory", tags=["AB Factory"])
app.include_router(radar.router, prefix="/api/v1/radar", tags=["Radar"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/readiness")
async def readiness_check():
    # To do: check DB connections here
    return {"status": "ready"}
