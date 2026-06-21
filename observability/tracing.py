"""
observability/tracing.py — OpenTelemetry Distributed Tracing
=============================================================
Implements Section 7.3.
Exports spans to Jaeger via OTLP (HTTP/gRPC).
Wire into app.py lifespan:
    from observability.tracing import configure_tracing
    configure_tracing()
"""

import logging
import os

logger = logging.getLogger("retention_core.tracing")

JAEGER_ENDPOINT = os.getenv("JAEGER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
SERVICE_NAME    = os.getenv("OTEL_SERVICE_NAME", "retention-core-api")
ENVIRONMENT     = os.getenv("ENVIRONMENT", "development")


def configure_tracing(app=None) -> None:
    """
    Configures OpenTelemetry SDK with Jaeger OTLP exporter.
    If FastAPI app is passed, also instruments all HTTP endpoints.
    Gracefully degrades if opentelemetry packages not installed.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning(
            "[tracing] opentelemetry packages not installed. Tracing disabled. "
            "Run: pip install opentelemetry-sdk opentelemetry-exporter-otlp "
            "opentelemetry-instrumentation-fastapi"
        )
        return

    resource = Resource.create({
        "service.name":        SERVICE_NAME,
        "service.version":     "3.0.0",
        "deployment.environment": ENVIRONMENT,
    })
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=JAEGER_ENDPOINT)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[tracing] FastAPI instrumented. Exporting to: %s", JAEGER_ENDPOINT)
    else:
        logger.info("[tracing] Tracer configured (no app provided). Exporting to: %s", JAEGER_ENDPOINT)


def get_tracer(name: str):
    """Returns an OpenTelemetry tracer for the given module name."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None
