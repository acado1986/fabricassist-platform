"""QStash publisher; inbound execution is intentionally implemented in Phase 3."""

from __future__ import annotations

from hashlib import sha256

import httpx

from fabricassist.application.jobs import (
    AnalysisJobMessage,
    ConversationJobMessage,
    JobMessage,
    PermanentJobDispatchError,
    RetryableJobDispatchError,
)
from fabricassist.infrastructure.jobs.config import QStashJobDispatcherConfig


class QStashJobDispatcherAdapter:
    """Publish strict identifier-only jobs through QStash with bounded I/O."""

    _PUBLISH_BASE_URL = "https://qstash.upstash.io/v2/publish/"

    def __init__(
        self,
        config: QStashJobDispatcherConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = config.token
        self._destination_url = config.destination_url
        self._timeout = config.request_timeout_seconds
        self._delivery_timeout = config.delivery_timeout_seconds
        self._transport = transport

    @staticmethod
    def deduplication_id(message: JobMessage) -> str:
        if isinstance(message, AnalysisJobMessage):
            value = f"fabricassist:v1:analysis:{message.operation_key}:{message.stage}"
        else:
            value = f"fabricassist:v1:conversation:{message.conversation_message_id}"
        return sha256(value.encode()).hexdigest()

    async def dispatch_analysis(self, message: AnalysisJobMessage, *, correlation_id: str) -> None:
        await self._publish(message, correlation_id=correlation_id)

    async def dispatch_conversation(
        self,
        message: ConversationJobMessage,
        *,
        correlation_id: str,
    ) -> None:
        await self._publish(message, correlation_id=correlation_id)

    async def _publish(self, message: JobMessage, *, correlation_id: str) -> None:
        payload = message.model_dump(mode="json")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Upstash-Method": "POST",
            "Upstash-Timeout": f"{self._delivery_timeout}s",
            "Upstash-Deduplication-Id": self.deduplication_id(message),
            "Upstash-Forward-X-Correlation-ID": correlation_id,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._PUBLISH_BASE_URL}{self._destination_url}",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as error:
            raise RetryableJobDispatchError("QStash publication timed out") from error
        except httpx.HTTPError as error:
            raise RetryableJobDispatchError("QStash publication failed") from error
        if response.status_code in {401, 403} or 400 <= response.status_code < 500:
            raise PermanentJobDispatchError("QStash rejected the publication")
        if response.status_code >= 500:
            raise RetryableJobDispatchError("QStash is temporarily unavailable")
