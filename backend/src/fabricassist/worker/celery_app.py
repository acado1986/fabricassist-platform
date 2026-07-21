"""Celery composition root; Valkey is used through its Redis-compatible protocol."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from celery import Celery

from fabricassist.settings import Settings


def _celery_broker_url(url: str) -> str:
    return url.replace("valkey://", "redis://", 1)


settings = Settings()
celery_app = Celery("fabricassist-worker", broker=_celery_broker_url(settings.valkey_url))
celery_app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1
)
celery_app.autodiscover_tasks(["fabricassist.worker"])
