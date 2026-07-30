"""Infrastructure composition for job dispatchers."""

from __future__ import annotations

from collections.abc import Callable

from fabricassist.application.jobs import JobDispatcher
from fabricassist.infrastructure.jobs.celery import CeleryJobDispatcherAdapter
from fabricassist.infrastructure.jobs.config import (
    CeleryJobDispatcherConfig,
    QStashJobDispatcherConfig,
)
from fabricassist.infrastructure.jobs.qstash import QStashJobDispatcherAdapter
from fabricassist.settings import JobDispatcherType, Settings

JobDispatcherBuilder = Callable[[Settings], JobDispatcher]


def _celery(_settings: Settings) -> JobDispatcher:
    return CeleryJobDispatcherAdapter(CeleryJobDispatcherConfig())


def _qstash(settings: Settings) -> JobDispatcher:
    return QStashJobDispatcherAdapter(
        QStashJobDispatcherConfig(
            token=settings.qstash_token,
            destination_url=settings.qstash_destination_url,
            request_timeout_seconds=float(min(settings.job_stage_budget_seconds, 30)),
            delivery_timeout_seconds=settings.job_stage_budget_seconds,
        )
    )


JOB_DISPATCHER_ADAPTERS: dict[JobDispatcherType, JobDispatcherBuilder] = {
    JobDispatcherType.CELERY: _celery,
    JobDispatcherType.QSTASH: _qstash,
}


def create_job_dispatcher(settings: Settings) -> JobDispatcher:
    """Select one registered job delivery strategy."""
    try:
        builder = JOB_DISPATCHER_ADAPTERS[settings.job_dispatcher]
    except KeyError as error:  # pragma: no cover
        raise ValueError(f"Unsupported job dispatcher: {settings.job_dispatcher}") from error
    return builder(settings)
