"""QStash publisher; inbound execution is intentionally implemented in Phase 3."""

from __future__ import annotations

from hashlib import sha256

import httpx

from fabricassist.application.jobs import AnalysisJobMessage
from fabricassist.settings import Settings


class JobDispatchError(RuntimeError):
    """Base class that never includes credentials or raw message content."""


class RetryableJobDispatchError(JobDispatchError):
    """A transient transport or upstream availability failure."""


class PermanentJobDispatchError(JobDispatchError):
    """An authentication, configuration, or permanently rejected publication."""


class QStashJobDispatcher:
    """Publish strict identifier-only jobs through QStash with bounded I/O."""

    _PUBLISH_BASE_URL = "https://qstash.upstash.io/v2/publish/"

    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._token = settings.qstash_token
        self._destination_url = settings.qstash_destination_url
        self._timeout = float(min(settings.job_stage_budget_seconds, 30))
        self._transport = transport

    @staticmethod
    def deduplication_id(message: AnalysisJobMessage) -> str:
        value = f"fabricassist:v1:{message.operation_key}:{message.stage}"
        return sha256(value.encode()).hexdigest()

    async def dispatch_analysis(self, message: AnalysisJobMessage, *, correlation_id: str) -> None:
        payload = message.model_dump(mode="json")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Upstash-Method": "POST",
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
