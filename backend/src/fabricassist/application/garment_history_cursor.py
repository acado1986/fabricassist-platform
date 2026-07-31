"""Pure cursor value object and codec for garment-history pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID


@dataclass(frozen=True)
class GarmentHistoryCursor:
    last_analysis_at: datetime | None
    garment_id: UUID


def encode_history_cursor(cursor: GarmentHistoryCursor) -> str:
    payload = {
        "a": cursor.last_analysis_at.isoformat() if cursor.last_analysis_at else None,
        "g": str(cursor.garment_id),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    return encoded.rstrip(b"=").decode("ascii")


def decode_history_cursor(value: str) -> GarmentHistoryCursor:
    try:
        padded = value.encode("ascii") + b"=" * (-len(value) % 4)
        raw_payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(raw_payload, dict):
            raise ValueError
        payload = cast(dict[str, object], raw_payload)
        if set(payload) != {"a", "g"}:
            raise ValueError
        analysis_at = payload["a"]
        if analysis_at is not None:
            if not isinstance(analysis_at, str):
                raise ValueError
            analysis_at = datetime.fromisoformat(analysis_at)
            if analysis_at.tzinfo is None:
                raise ValueError
        garment_id = UUID(str(payload["g"]))
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid garment history cursor") from error
    return GarmentHistoryCursor(analysis_at, garment_id)
