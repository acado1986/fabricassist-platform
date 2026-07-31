"""Pure cursor value object and codec for garment analysis pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID


@dataclass(frozen=True)
class GarmentAnalysisCursor:
    created_at: datetime
    scan_id: UUID


def encode_analysis_cursor(cursor: GarmentAnalysisCursor) -> str:
    payload = {"c": cursor.created_at.isoformat(), "s": str(cursor.scan_id)}
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    return encoded.rstrip(b"=").decode("ascii")


def decode_analysis_cursor(value: str) -> GarmentAnalysisCursor:
    try:
        padded = value.encode("ascii") + b"=" * (-len(value) % 4)
        raw_payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(raw_payload, dict):
            raise ValueError
        payload = cast(dict[str, object], raw_payload)
        if set(payload) != {"c", "s"}:
            raise ValueError
        created_at = payload["c"]
        if not isinstance(created_at, str):
            raise ValueError
        parsed_created_at = datetime.fromisoformat(created_at)
        if parsed_created_at.tzinfo is None:
            raise ValueError
        scan_id = UUID(str(payload["s"]))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid garment analysis cursor") from error
    return GarmentAnalysisCursor(parsed_created_at, scan_id)
