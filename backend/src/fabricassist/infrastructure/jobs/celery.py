"""Celery implementation of the analysis dispatch port."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from fabricassist.application.jobs import AnalysisJobMessage


class CeleryJobDispatcher:
    """Preserve the existing local Celery task name and correlation header."""

    async def dispatch_analysis(self, message: AnalysisJobMessage, *, correlation_id: str) -> None:
        from fabricassist.worker.celery_app import celery_app

        celery_app.send_task(
            "fabricassist.analyse_scan",
            args=[str(message.scan_id)],
            headers={"correlation_id": correlation_id},
        )
