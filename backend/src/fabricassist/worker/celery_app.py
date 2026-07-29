"""Celery composition root; broker selection is independent of Valkey capabilities."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from celery import Celery

from fabricassist.api.logging import configure_logging
from fabricassist.infrastructure.telemetry import configure_worker_telemetry
from fabricassist.settings import Settings


def _celery_broker_url(url: str) -> str:
    return url.replace("valkey://", "redis://", 1)


settings = Settings()
settings.otel_service_name = "fabricassist-worker"
configure_logging(settings.log_level)
configure_worker_telemetry(settings)
celery_app = Celery("fabricassist-worker", broker=_celery_broker_url(settings.celery_broker_url))
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    broker_connection_retry_on_startup=True,
)
celery_app.autodiscover_tasks(["fabricassist.worker"])
