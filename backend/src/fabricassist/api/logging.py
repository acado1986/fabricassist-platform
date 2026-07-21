"""Minimal structured logging for the backend foundation."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    """Render safe common log fields as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = correlation_id_context.get()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        for source, target in (
            ("http_method", "http_method"),
            ("http_path", "http_path"),
            ("http_status", "http_status"),
        ):
            value = getattr(record, source, None)
            if value is not None:
                payload[target] = value
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    """Configure an idempotent JSON handler for application logs."""
    logger = logging.getLogger("fabricassist")
    logger.setLevel(level.upper())
    logger.propagate = False
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
