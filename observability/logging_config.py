"""
observability/logging_config.py — Structured JSON Logging via structlog
=======================================================================
Implements Section 7.1.
Every log entry is JSON with fields:
  timestamp, level, tenant_id, user_id, trace_id, module, event, duration_ms, error

Usage:
    from observability.logging_config import configure_logging, get_logger
    configure_logging()   # call once at app startup
    logger = get_logger(__name__)
    logger.info("customer.scored", tenant_id=1, user_id="abc", churn_score=0.87)
"""

import logging
import logging.config
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configures structlog for JSON output.
    Call once at application startup (e.g. in app.py lifespan).
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> Any:
    """Returns a structlog logger bound to the given module name."""
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """
    Binds context variables to the current async context (e.g. per-request).
    Call this in FastAPI middleware to add tenant_id, user_id, trace_id
    to ALL log entries within that request lifecycle.

    Example:
        bind_context(tenant_id=1, user_id="abc123", trace_id="req-xyz")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clears bound context variables (call in response middleware after request)."""
    structlog.contextvars.clear_contextvars()
