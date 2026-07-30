"""Celery implementation of the analysis dispatch port."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fabricassist.application.jobs import (
    AnalysisJobMessage,
    ConversationJobMessage,
    PermanentJobDispatchError,
    RetryableJobDispatchError,
)
from fabricassist.infrastructure.jobs.config import CeleryJobDispatcherConfig


class CeleryJobDispatcherAdapter:
    """Preserve the existing local Celery task name and correlation header."""

    def __init__(
        self,
        config: CeleryJobDispatcherConfig,
        *,
        sender: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config
        self._sender = sender

    async def dispatch_analysis(self, message: AnalysisJobMessage, *, correlation_id: str) -> None:
        sender = self._sender
        if sender is None:
            from fabricassist.worker.celery_app import celery_app

            sender = cast(Callable[..., Any], celery_app.send_task)

        try:
            sender(
                self._config.task_name,
                args=[message.model_dump_json()],
                headers={"correlation_id": correlation_id},
            )
        except (TypeError, ValueError) as error:
            raise PermanentJobDispatchError("Celery publication was rejected") from error
        except Exception as error:
            raise RetryableJobDispatchError("Celery publication failed") from error

    async def dispatch_conversation(
        self,
        message: ConversationJobMessage,
        *,
        correlation_id: str,
    ) -> None:
        sender = self._sender
        if sender is None:
            from fabricassist.worker.celery_app import celery_app

            sender = cast(Callable[..., Any], celery_app.send_task)
        try:
            sender(
                "fabricassist.answer_message",
                args=[str(message.conversation_message_id)],
                headers={"correlation_id": correlation_id},
            )
        except (TypeError, ValueError) as error:
            raise PermanentJobDispatchError("Celery publication was rejected") from error
        except Exception as error:
            raise RetryableJobDispatchError("Celery publication failed") from error
