"""Minimal structured logging for the backend foundation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)
log_fields_context: ContextVar[dict[str, str] | None] = ContextVar("log_fields", default=None)
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|password|refresh[_-]?token|presigned[_-]?url)"
    r"([\"'=:\s]+)([^,\s}\"]+)"
)


class JsonFormatter(logging.Formatter):
    """Render safe common log fields as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _SECRET_PATTERN.sub(r"\1\2[REDACTED]", record.getMessage()),
        }
        correlation_id = correlation_id_context.get()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        payload.update(log_fields_context.get() or {})
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


@contextmanager
def log_context(**fields: str | None) -> Generator[None, None, None]:
    """Attach safe identifiers to every log emitted inside the context."""
    current = log_fields_context.get() or {}
    token = log_fields_context.set(
        {**current, **{key: value for key, value in fields.items() if value is not None}}
    )
    try:
        yield
    finally:
        log_fields_context.reset(token)
