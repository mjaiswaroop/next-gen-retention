"""
observability/metrics.py — Prometheus Custom Metrics
=====================================================
Implements Section 7.2.
All custom metrics defined here. Wire into app.py via:
    from observability.metrics import setup_metrics
    setup_metrics(app)
"""

import os
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

# Use default registry (works with prometheus-fastapi-instrumentator)
REGISTRY = CollectorRegistry(auto_describe=True)

# ── Section 7.2 Custom Metrics ────────────────────────────────────────────────

retention_predictions_total = Counter(
    "retention_predictions_total",
    "Total number of churn predictions made",
    ["tenant_id", "risk_band"],   # risk_band: high / medium / low
)

retention_campaigns_sent_total = Counter(
    "retention_campaigns_sent_total",
    "Total number of win-back campaigns sent",
    ["tenant_id", "channel"],    # channel: email / sms / push
)

retention_model_auc = Gauge(
    "retention_model_auc",
    "Current active model AUC-ROC score",
    ["tenant_id", "model_version"],
)

retention_drift_psi = Gauge(
    "retention_drift_psi",
    "Population Stability Index per feature",
    ["tenant_id", "feature_name"],
)

retention_api_latency_seconds = Histogram(
    "retention_api_latency_seconds",
    "API endpoint response time in seconds",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

retention_memory_usage_bytes = Gauge(
    "retention_memory_usage_bytes",
    "Current process memory usage in bytes",
)

last_successful_backup_timestamp = Gauge(
    "retention_last_backup_timestamp_seconds",
    "Unix timestamp of last successful backup",
)

campaign_queue_pending = Gauge(
    "retention_campaign_queue_pending",
    "Number of campaigns pending approval",
    ["tenant_id"],
)


def setup_metrics(app) -> None:
    """
    Wires Prometheus FastAPI auto-instrumentation and exposes /metrics endpoint.
    Call once during app startup.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            excluded_handlers=["/health", "/readiness", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ImportError:
        import logging
        logging.getLogger("retention_core.metrics").warning(
            "prometheus-fastapi-instrumentator not installed. /metrics endpoint unavailable."
        )


def update_memory_gauge() -> None:
    """Updates the memory gauge with current process RSS. Call periodically."""
    try:
        import psutil, os
        process = psutil.Process(os.getpid())
        retention_memory_usage_bytes.set(process.memory_info().rss)
    except ImportError:
        pass


def record_prediction(tenant_id: int, churn_probability: float) -> None:
    """Increments predictions counter with appropriate risk band label."""
    if churn_probability >= 0.75:
        band = "high"
    elif churn_probability >= 0.40:
        band = "medium"
    else:
        band = "low"
    retention_predictions_total.labels(
        tenant_id=str(tenant_id), risk_band=band
    ).inc()


def record_campaign_sent(tenant_id: int, channel: str) -> None:
    """Increments campaigns sent counter."""
    retention_campaigns_sent_total.labels(
        tenant_id=str(tenant_id), channel=channel
    ).inc()


def update_model_auc(tenant_id: int, model_version: str, auc: float) -> None:
    """Updates model AUC gauge after promotion."""
    retention_model_auc.labels(
        tenant_id=str(tenant_id), model_version=model_version
    ).set(auc)


def update_drift_psi(tenant_id: int, feature_name: str, psi: float) -> None:
    """Updates PSI gauge after drift evaluation."""
    retention_drift_psi.labels(
        tenant_id=str(tenant_id), feature_name=feature_name
    ).set(psi)
