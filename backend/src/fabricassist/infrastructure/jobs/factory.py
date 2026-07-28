"""Infrastructure composition for job dispatchers."""

from __future__ import annotations

from fabricassist.application.jobs import JobDispatcher
from fabricassist.infrastructure.jobs.celery import CeleryJobDispatcher
from fabricassist.infrastructure.jobs.qstash import QStashJobDispatcher
from fabricassist.settings import JobDispatcherType, Settings


def create_job_dispatcher(settings: Settings) -> JobDispatcher:
    if settings.job_dispatcher == JobDispatcherType.CELERY:
        return CeleryJobDispatcher()
    if settings.job_dispatcher == JobDispatcherType.QSTASH:
        return QStashJobDispatcher(settings)
    raise ValueError(f"Unsupported job dispatcher: {settings.job_dispatcher}")
