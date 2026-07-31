"""Portable OpenTelemetry tracing and Prometheus-compatible metrics."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter
from typing import Final

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from fabricassist.settings import Settings

logger = logging.getLogger("fabricassist.telemetry")

HTTP_REQUESTS: Final = Counter(
    "fabricassist_http_requests_total",
    "HTTP requests handled by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION: Final = Histogram(
    "fabricassist_http_request_duration_seconds",
    "HTTP request latency.",
    ("method", "route"),
)
RATE_LIMITED: Final = Counter(
    "fabricassist_rate_limited_total",
    "Requests rejected by a configured rate limit.",
    ("policy",),
)
JOBS: Final = Counter(
    "fabricassist_jobs_total",
    "Worker job outcomes.",
    ("operation", "outcome"),
)
JOB_DURATION: Final = Histogram(
    "fabricassist_job_duration_seconds",
    "Worker job duration.",
    ("operation",),
)
WORKER_CONCURRENCY: Final = Gauge(
    "fabricassist_worker_concurrency_slots",
    "Active provider-facing worker slots.",
    ("scope", "operation"),
)
IDENTITY_OUTCOMES: Final = Counter(
    "fabricassist_identity_outcomes_total",
    "Garment identity classifications.",
    ("classification",),
)
PRODUCT_LOOKUPS: Final = Counter(
    "fabricassist_product_lookups_total",
    "Product lookup outcomes.",
    ("provider", "status"),
)
VALIDATION_OUTCOMES: Final = Counter(
    "fabricassist_validation_outcomes_total",
    "Care validator outcomes and retry state.",
    ("outcome", "retried"),
)
CONVERSATIONS: Final = Counter(
    "fabricassist_conversations_total",
    "Conversation message outcomes.",
    ("outcome",),
)
CONVERSATION_CONTEXT_IMAGES: Final = Histogram(
    "fabricassist_conversation_context_images",
    "Images selected into a conversation context.",
    buckets=(0, 1, 2, 4, 8),
)
REVIEWS: Final = Counter(
    "fabricassist_reviews_total",
    "Review workflow transitions.",
    ("action",),
)
DELETIONS: Final = Counter(
    "fabricassist_object_deletions_total",
    "Private-object deletion outcomes.",
    ("outcome",),
)
SSE_CONNECTIONS: Final = Gauge(
    "fabricassist_sse_connections",
    "Active authenticated AI-run SSE connections.",
)
SSE_DISCONNECTS: Final = Counter(
    "fabricassist_sse_disconnects_total",
    "AI-run SSE disconnects before a terminal event.",
)

_configured_services: set[str] = set()


def _configure_provider(settings: Settings) -> None:
    service_name = settings.otel_service_name
    if settings.otel_exporter_otlp_endpoint and service_name not in _configured_services:
        provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
                )
            )
        )
        trace.set_tracer_provider(provider)
        _configured_services.add(service_name)


def configure_telemetry(app: FastAPI, settings: Settings) -> None:
    """Instrument FastAPI and configure OTLP export only when explicitly requested."""
    _configure_provider(settings)
    FastAPIInstrumentor.instrument_app(  # pyright: ignore[reportUnknownMemberType]
        app,
        tracer_provider=trace.get_tracer_provider(),
        excluded_urls="/api/v1/health/live,/api/v1/metrics",
    )


def configure_worker_telemetry(settings: Settings) -> None:
    """Instrument Celery delivery and propagate W3C trace context through task headers."""
    _configure_provider(settings)
    CeleryInstrumentor().instrument(tracer_provider=trace.get_tracer_provider())


def metrics_payload() -> tuple[bytes, str]:
    """Return the current process metrics in Prometheus exposition format."""
    return generate_latest(), CONTENT_TYPE_LATEST


@contextmanager
def measure_job(operation: str) -> Generator[None, None, None]:
    """Record one worker operation without leaking job arguments."""
    started = perf_counter()
    try:
        yield
    except Exception:
        JOBS.labels(operation=operation, outcome="failed").inc()
        raise
    else:
        JOBS.labels(operation=operation, outcome="completed").inc()
    finally:
        JOB_DURATION.labels(operation=operation).observe(perf_counter() - started)
