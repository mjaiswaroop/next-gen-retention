"""
models.py — SQLAlchemy ORM Models (Auth/Merchant Domain → SQLite)
=================================================================
All tables here live in the SQLite database (retention.db).
Analytics-heavy tables (drift_log, shap_values, etc.) live in DuckDB Parquet.

Sections covered:
  - Original: Merchant, Customer, EventLog, AuditLog
  - Section 1: ModelRegistry, DriftLog, ShapValue, ExperimentAssignment, ExperimentResult
  - Section 3: ErasureCertificate, TenantConfig
  - Section 4: CampaignQueue, CustomerPreferences, CampaignEvent
  - Section 5: User, ApiKey
  - Section 6: TenantIntegration, WebhookDeliveryLog
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, UniqueConstraint, Index, Boolean, Text, JSON
)
from sqlalchemy.orm import relationship
from database import Base


def utc_now():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# CORE: Merchant & Customer
# ─────────────────────────────────────────────────────────────────────────────

class Merchant(Base):
    __tablename__ = "merchants"

    id         = Column(Integer, primary_key=True)
    name       = Column(String(255), nullable=False, unique=True)
    api_key    = Column(String(64),  nullable=False, unique=True)
    is_active  = Column(Boolean, default=True, nullable=False)
    timezone   = Column(String(64), default="UTC", nullable=False)
    data_residency_region = Column(String(8), default="US", nullable=False)  # EU / US / IN
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    customers       = relationship("Customer",    back_populates="merchant", cascade="all, delete-orphan")
    event_logs      = relationship("EventLog",    back_populates="merchant", cascade="all, delete-orphan")
    users           = relationship("User",        back_populates="merchant", cascade="all, delete-orphan")
    api_keys        = relationship("ApiKey",      back_populates="merchant", cascade="all, delete-orphan")
    integrations    = relationship("TenantIntegration", back_populates="merchant", cascade="all, delete-orphan")
    tenant_config   = relationship("TenantConfig", back_populates="merchant", uselist=False, cascade="all, delete-orphan")


class Customer(Base):
    __tablename__ = "customers"

    id                     = Column(Integer, primary_key=True)
    merchant_id            = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    user_id                = Column(String(64), nullable=False)
    recency_days           = Column(Float, nullable=False)
    frequency              = Column(Integer, nullable=False)
    monetary_value         = Column(Float, nullable=False)
    session_failures       = Column(Integer, default=0, nullable=False)
    payment_friction_index = Column(Float, default=0.0, nullable=False)
    active_support_tickets = Column(Integer, default=0, nullable=False)
    churn_probability      = Column(Float, nullable=True)
    segment                = Column(String(50), nullable=True)
    is_deleted             = Column(Boolean, default=False, nullable=False)
    deleted_at             = Column(DateTime(timezone=True), nullable=True)
    created_at             = Column(DateTime(timezone=True), default=utc_now)
    updated_at             = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    merchant     = relationship("Merchant", back_populates="customers")
    events       = relationship("EventLog", back_populates="customer", cascade="all, delete-orphan")
    preferences  = relationship("CustomerPreferences", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    experiments  = relationship("ExperimentAssignment", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", name="uq_customer_merchant_user"),
        Index("ix_customer_merchant_segment", "merchant_id", "segment"),
        Index("ix_customer_merchant_churn",   "merchant_id", "churn_probability"),
        Index("ix_customer_deleted",          "merchant_id", "is_deleted"),
    )


class EventLog(Base):
    __tablename__ = "event_logs"

    id          = Column(Integer, primary_key=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    timestamp   = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    event_type  = Column(String(100), nullable=False)
    payload     = Column(Text, nullable=True)

    merchant = relationship("Merchant", back_populates="event_logs")
    customer = relationship("Customer", back_populates="events")

    __table_args__ = (
        Index("ix_event_merchant_ts",   "merchant_id", "timestamp"),
        Index("ix_event_merchant_type", "merchant_id", "event_type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Compliance — Immutable Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable append-only log. Application layer must never allow UPDATE/DELETE.
    Covers: login, model_promoted, customer_erased, campaign_sent,
            threshold_changed, api_key_rotated, tenant_created, pii_viewed.
    """
    __tablename__ = "audit_logs"

    log_id        = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id     = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    actor_user_id = Column(String(36), nullable=True)   # NULL for system actions
    action_type   = Column(String(64), nullable=False)  # e.g. "customer_erased"
    resource_type = Column(String(64), nullable=True)
    resource_id   = Column(String(64), nullable=True)
    ip_address    = Column(String(45), nullable=True)
    user_agent    = Column(Text, nullable=True)
    payload_hash  = Column(String(64), nullable=True)   # SHA-256 of request body
    occurred_at   = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action_type"),
        Index("ix_audit_tenant_date",   "tenant_id", "occurred_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: ML Model Registry
# ─────────────────────────────────────────────────────────────────────────────

class ModelRegistry(Base):
    """
    Tracks every trained XGBoost artifact per tenant.
    Only one row per tenant can have is_active=True at a time.
    """
    __tablename__ = "model_registry"

    model_id    = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id   = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    version     = Column(Integer, nullable=False)
    artifact_path = Column(String(512), nullable=False)   # models/merchant_1_xgb_v3_20240613.joblib
    trained_at  = Column(DateTime(timezone=True), default=utc_now)
    accuracy    = Column(Float, nullable=True)
    f1_score    = Column(Float, nullable=True)
    auc_roc     = Column(Float, nullable=True)
    precision   = Column(Float, nullable=True)
    recall      = Column(Float, nullable=True)
    is_active   = Column(Boolean, default=False, nullable=False)
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    notes       = Column(Text, nullable=True)   # e.g. "Promoted: +2.1% AUC"
    created_at  = Column(DateTime(timezone=True), default=utc_now)
    updated_at  = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_registry_tenant_active", "tenant_id", "is_active"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1.2: Data Drift Log
# ─────────────────────────────────────────────────────────────────────────────

class DriftLog(Base):
    """
    PSI and Jensen-Shannon divergence per feature per tenant.
    drift_level: 'stable' | 'moderate' | 'severe'
    """
    __tablename__ = "drift_logs"

    log_id        = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id     = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    feature_name  = Column(String(64), nullable=False)
    psi_score     = Column(Float, nullable=True)
    js_divergence = Column(Float, nullable=True)
    drift_level   = Column(String(16), nullable=False, default="stable")
    evaluated_at  = Column(DateTime(timezone=True), default=utc_now)
    action_taken  = Column(String(128), nullable=True)  # e.g. "emergency_retrain_triggered"
    created_at    = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_drift_tenant_feature", "tenant_id", "feature_name"),
        Index("ix_drift_tenant_date",    "tenant_id", "evaluated_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1.3: SHAP Values
# ─────────────────────────────────────────────────────────────────────────────

class ShapValue(Base):
    """
    Stores per-customer SHAP feature attributions for top at-risk users.
    Used by dashboard "Why is this customer at risk?" panel and RAG context.
    """
    __tablename__ = "shap_values"

    shap_id          = Column(String(36), primary_key=True, default=new_uuid)
    customer_id      = Column(String(64), nullable=False)   # user_id string (not FK to keep DuckDB-friendly)
    tenant_id        = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    feature_name     = Column(String(64), nullable=False)
    shap_value       = Column(Float, nullable=False)
    prediction_score = Column(Float, nullable=False)
    computed_at      = Column(DateTime(timezone=True), default=utc_now)
    created_at       = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_shap_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_shap_computed_at",     "tenant_id", "computed_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1.4: A/B Experiment Framework
# ─────────────────────────────────────────────────────────────────────────────

class ExperimentAssignment(Base):
    """
    Records which A/B group each at-risk customer was assigned to.
    outcome fields populated after 30 days by the chi-squared evaluation task.
    """
    __tablename__ = "experiment_assignments"

    experiment_id    = Column(String(36), primary_key=True, default=new_uuid)
    customer_id      = Column(Integer, ForeignKey("customers.id"), nullable=False)
    tenant_id        = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    group            = Column(String(1), nullable=False)   # 'A' or 'B'
    template_version = Column(String(32), nullable=False)  # e.g. 'v1_rag' or 'v2_vip'
    assigned_at      = Column(DateTime(timezone=True), default=utc_now)
    email_opened     = Column(Boolean, default=False)
    email_clicked    = Column(Boolean, default=False)
    churned_after_7d  = Column(Boolean, nullable=True)
    churned_after_30d = Column(Boolean, nullable=True)
    created_at       = Column(DateTime(timezone=True), default=utc_now)
    updated_at       = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    customer = relationship("Customer", back_populates="experiments")

    __table_args__ = (
        Index("ix_exp_tenant_group",   "tenant_id", "group"),
        Index("ix_exp_assigned_at",    "tenant_id", "assigned_at"),
    )


class ExperimentResult(Base):
    """
    Aggregated chi-squared test results per tenant campaign experiment round.
    auto_promoted=True means the winning template was applied to future campaigns.
    """
    __tablename__ = "experiment_results"

    result_id       = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id       = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    evaluated_at    = Column(DateTime(timezone=True), default=utc_now)
    group_a_count   = Column(Integer, nullable=False)
    group_b_count   = Column(Integer, nullable=False)
    group_a_retained = Column(Integer, nullable=False)
    group_b_retained = Column(Integer, nullable=False)
    chi_squared_stat = Column(Float, nullable=True)
    p_value          = Column(Float, nullable=True)
    winning_group    = Column(String(1), nullable=True)    # 'A', 'B', or None (no significance)
    auto_promoted    = Column(Boolean, default=False)
    notes            = Column(Text, nullable=True)
    created_at       = Column(DateTime(timezone=True), default=utc_now)


class InterventionExperiment(Base):
    """
    Tracks causal interventions to validate if they actually reduced churn over 30 days.
    """
    __tablename__ = "intervention_experiments"

    intervention_id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id       = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id     = Column(String(64), nullable=False)
    campaign_id     = Column(String(36), ForeignKey("campaign_queue.queue_id"), nullable=True)
    action_taken    = Column(String(128), nullable=False)
    causal_uplift_predicted = Column(Float, nullable=True)
    status          = Column(String(16), default="pending", nullable=False) # pending, success, failed
    evaluated_at    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=utc_now)
    updated_at      = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_intervention_tenant_status", "tenant_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: RBAC — Users & API Keys
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """
    Platform users with role-based access.
    Roles: SUPER_ADMIN, TENANT_ADMIN, ANALYST, CAMPAIGN_MANAGER, PII_VIEWER
    """
    __tablename__ = "users"

    user_id         = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id       = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    email           = Column(String(255), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role            = Column(String(32), nullable=False, default="ANALYST")
    is_active       = Column(Boolean, default=True, nullable=False)
    last_login      = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=utc_now)
    updated_at      = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    merchant = relationship("Merchant", back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
        Index("ix_user_tenant_role", "tenant_id", "role"),
    )


class ApiKey(Base):
    """
    Scoped API keys managed by TENANT_ADMIN.
    Scopes: read_only | campaign_trigger | data_ingest (stored as JSON array)
    """
    __tablename__ = "api_keys"

    key_id      = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id   = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    key_hash    = Column(String(256), nullable=False, unique=True)
    label       = Column(String(128), nullable=True)
    scopes      = Column(JSON, nullable=False, default=list)  # ["read_only"]
    created_by  = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=utc_now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at  = Column(DateTime(timezone=True), nullable=True)
    is_revoked  = Column(Boolean, default=False, nullable=False)

    merchant = relationship("Merchant", back_populates="api_keys")

    __table_args__ = (
        Index("ix_apikey_tenant_revoked", "tenant_id", "is_revoked"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Compliance — Erasure Certificate & Tenant Config
# ─────────────────────────────────────────────────────────────────────────────

class ErasureCertificate(Base):
    """
    Immutable record of a GDPR/CCPA right-to-erasure action.
    """
    __tablename__ = "erasure_certificates"

    erasure_id        = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id         = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id_hash  = Column(String(64), nullable=False)   # SHA-256 of original customer_id
    tables_cleared    = Column(JSON, nullable=False)          # List of table names
    erased_at         = Column(DateTime(timezone=True), default=utc_now)
    requested_by      = Column(String(36), nullable=True)    # user_id who triggered it
    certificate_pdf_path = Column(String(512), nullable=True)
    created_at        = Column(DateTime(timezone=True), default=utc_now)


class TenantConfig(Base):
    """
    Per-tenant configuration: PII registry, data residency, auto-approve hours, etc.
    """
    __tablename__ = "tenant_configs"

    config_id             = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id             = Column(Integer, ForeignKey("merchants.id"), nullable=False, unique=True)
    pii_fields            = Column(JSON, default=list)          # ["email","full_name","phone"]
    data_residency_region = Column(String(8), default="US")     # EU / US / IN
    campaign_auto_approve_hours = Column(Integer, default=24)
    digest_email_enabled  = Column(Boolean, default=True)
    digest_recipients     = Column(JSON, default=list)          # list of email strings
    churn_threshold       = Column(Float, default=0.75)
    active_template       = Column(String(8), default="A")      # 'A' or 'B' (A/B winner)
    enable_inferred_edges = Column(Boolean, default=False)
    created_at            = Column(DateTime(timezone=True), default=utc_now)
    updated_at            = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    merchant = relationship("Merchant", back_populates="tenant_config")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Contagion Graph
# ─────────────────────────────────────────────────────────────────────────────

class CustomerEdge(Base):
    """
    Stores explicit and inferred relationships between customers.
    """
    __tablename__ = "customer_edges"

    id                 = Column(Integer, primary_key=True)
    tenant_id          = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    source_customer_id = Column(String(64), nullable=False)
    target_customer_id = Column(String(64), nullable=False)
    edge_type          = Column(String(32), default="explicit", nullable=False)
    weight             = Column(Float, default=1.0, nullable=False)
    confidence_score   = Column(Float, default=1.0, nullable=False)
    inference_basis    = Column(JSON, nullable=True)
    created_at         = Column(DateTime(timezone=True), default=utc_now)
    
    __table_args__ = (
        Index("ix_customer_edges_tenant_source", "tenant_id", "source_customer_id"),
        Index("ix_customer_edges_tenant_target", "tenant_id", "target_customer_id"),
        UniqueConstraint("tenant_id", "source_customer_id", "target_customer_id", name="uq_customer_edge"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Campaign Governance
# ─────────────────────────────────────────────────────────────────────────────

class CampaignQueue(Base):
    """
    Human-in-the-loop approval queue for all outgoing win-back campaigns.
    Status flow: pending → approved/rejected/auto_approved
    """
    __tablename__ = "campaign_queue"

    queue_id                 = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id                = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id              = Column(String(64), nullable=False)
    campaign_type            = Column(String(32), default="win_back")
    channel                  = Column(String(16), default="email")  # email/sms/push
    generated_email_subject  = Column(String(512), nullable=True)
    generated_email_body     = Column(Text, nullable=True)
    shap_context             = Column(JSON, nullable=True)   # Top-3 SHAP drivers
    churn_score              = Column(Float, nullable=False)
    status                   = Column(String(16), default="pending", nullable=False)
    created_at               = Column(DateTime(timezone=True), default=utc_now)
    reviewed_by              = Column(String(36), nullable=True)
    reviewed_at              = Column(DateTime(timezone=True), nullable=True)
    auto_approve_after_hours = Column(Integer, default=24)
    rejection_reason         = Column(Text, nullable=True)
    scheduled_send_at        = Column(DateTime(timezone=True), nullable=True)
    sent_at                  = Column(DateTime(timezone=True), nullable=True)
    updated_at               = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_campaign_queue_tenant_status", "tenant_id", "status"),
        Index("ix_campaign_queue_created",       "tenant_id", "created_at"),
    )


class CustomerPreferences(Base):
    """
    Per-customer channel preferences and opt-out flags.
    """
    __tablename__ = "customer_preferences"

    pref_id           = Column(String(36), primary_key=True, default=new_uuid)
    customer_id       = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True)
    tenant_id         = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    preferred_channel = Column(String(16), default="email")
    email_optout      = Column(Boolean, default=False)
    sms_optout        = Column(Boolean, default=False)
    push_optout       = Column(Boolean, default=False)
    updated_at        = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    customer = relationship("Customer", back_populates="preferences")


class CampaignEvent(Base):
    """
    Tracks every campaign lifecycle event: sent, opened, clicked, unsubscribed.
    Used for send-time optimisation (compute best hour/day per customer).
    """
    __tablename__ = "campaign_events"

    event_id    = Column(String(36), primary_key=True, default=new_uuid)
    customer_id = Column(String(64), nullable=False)
    tenant_id   = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    campaign_id = Column(String(36), ForeignKey("campaign_queue.queue_id"), nullable=True)
    event_type  = Column(String(20), nullable=False)  # sent/opened/clicked/unsubscribed
    occurred_at = Column(DateTime(timezone=True), default=utc_now)
    created_at  = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_campaign_event_tenant", "tenant_id", "customer_id"),
        Index("ix_campaign_event_type",   "tenant_id", "event_type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Integration Layer
# ─────────────────────────────────────────────────────────────────────────────

class TenantIntegration(Base):
    """
    Stores which integrations are enabled per tenant and their encrypted config.
    Config values are JSON; secrets come from env vars (never stored here).
    """
    __tablename__ = "tenant_integrations"

    integration_id   = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id        = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    integration_name = Column(String(32), nullable=False)   # salesforce/hubspot/stripe/zendesk/sendgrid/twilio
    is_enabled       = Column(Boolean, default=False)
    config           = Column(JSON, default=dict)            # Non-secret config (subdomain, etc.)
    last_synced_at   = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), default=utc_now)
    updated_at       = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    merchant = relationship("Merchant", back_populates="integrations")

    __table_args__ = (
        UniqueConstraint("tenant_id", "integration_name", name="uq_integration_tenant_name"),
    )


class WebhookDeliveryLog(Base):
    """
    Outbound webhook delivery attempts with retry tracking.
    """
    __tablename__ = "webhook_delivery_logs"

    delivery_id   = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id     = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    event_type    = Column(String(64), nullable=False)
    url           = Column(String(512), nullable=False)
    payload_hash  = Column(String(64), nullable=True)
    http_status   = Column(Integer, nullable=True)
    attempt_count = Column(Integer, default=1)
    delivered_at  = Column(DateTime(timezone=True), nullable=True)
    error         = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), default=utc_now)
    updated_at    = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_webhook_tenant_event", "tenant_id", "event_type"),
    )

class AgentSession(Base):
    """
    Stores logs and transcripts for autonomous agent sessions (websockets).
    """
    __tablename__ = "agent_sessions"

    session_id  = Column(String(36), primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    started_at  = Column(DateTime(timezone=True), default=utc_now)
    ended_at    = Column(DateTime(timezone=True))
    transcript  = Column(JSON, default=list)

    __table_args__ = (
        Index("ix_agent_sessions_tenant", "tenant_id"),
    )

class AgentActionRegistry(Base):
    """
    Whitelist of permitted actions for the autonomous agent.
    """
    __tablename__ = "agent_action_registry"

    id             = Column(Integer, primary_key=True)
    tenant_id      = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    action_type    = Column(String(64), nullable=False)
    classification = Column(String(32), nullable=False) # 'AUTONOMOUS' or 'REQUIRES_APPROVAL'
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "action_type", name="uq_agent_action_type"),
    )

class AgentActionLog(Base):
    """
    Audit log of all actions proposed or executed by the autonomous agent.
    """
    __tablename__ = "agent_action_logs"

    id             = Column(Integer, primary_key=True)
    tenant_id      = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    session_id     = Column(String(36), ForeignKey("agent_sessions.session_id"), nullable=True)
    action_type    = Column(String(64), nullable=False)
    action_payload = Column(JSON, nullable=True)
    classification = Column(String(32), nullable=False) # 'AUTONOMOUS' or 'REQUIRES_APPROVAL'
    status         = Column(String(32), nullable=False) # 'EXECUTED', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'
    rationale      = Column(Text, nullable=True)
    requested_at   = Column(DateTime(timezone=True), default=utc_now)
    resolved_at    = Column(DateTime(timezone=True), nullable=True)
    resolved_by    = Column(String(64), nullable=True) # Could be a User ID

    __table_args__ = (
        Index("ix_agent_action_logs_tenant", "tenant_id"),
    )

class ChurnForensicsReport(Base):
    """
    Auto-generated post-mortem report for churned customers.
    """
    __tablename__ = "churn_forensics_reports"

    id                        = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id                 = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id               = Column(String(64), nullable=False)
    churn_date                = Column(DateTime(timezone=True), default=utc_now)
    emotion_trajectory        = Column(JSON, nullable=True)
    contagion_context         = Column(JSON, nullable=True)
    counterfactual_history    = Column(JSON, nullable=True)
    economic_priority_history = Column(JSON, nullable=True)
    verdict                   = Column(String(64), nullable=False) 
    # e.g., 'INTERVENTION_AVAILABLE_NOT_TAKEN', 'INTERVENTION_TAKEN_BUT_FAILED', 'NO_VIABLE_INTERVENTION_FOUND', 'INSUFFICIENT_DATA'
    reasoning                 = Column(Text, nullable=True)
    created_at                = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_churn_forensics_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_churn_forensics_verdict", "tenant_id", "verdict"),
    )

class CounterfactualPath(Base):
    __tablename__ = "counterfactual_paths"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(String(64), nullable=False)
    intervention_type = Column(String(64), nullable=False)
    estimated_cost = Column(Float, nullable=False)
    predicted_risk_reduction = Column(Float, nullable=False)
    roi_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class LedgerEntryModel(Base):
    __tablename__ = 'negotiation_ledger'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('merchants.id'), nullable=False)
    session_id = Column(String(128), nullable=False)
    sequence = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    speaker = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    claim_type = Column(String(32), nullable=False)
    justification = Column(JSON, nullable=True)
    telemetry_snapshot = Column(JSON, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    entry_hash = Column(String(64), nullable=False)
    
    __table_args__ = (
        Index('ix_ledger_session', 'tenant_id', 'session_id'),
    )
