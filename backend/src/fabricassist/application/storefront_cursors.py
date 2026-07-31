"""Versioned opaque cursors for ordered storefront GraphQL connections."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID


def _encode(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps({"v": 1, **payload}, separators=(",", ":"), sort_keys=True).encode()
    )
    return encoded.rstrip(b"=").decode("ascii")


def _decode(value: str, keys: set[str]) -> dict[str, object]:
    try:
        padded = value.encode("ascii") + b"=" * (-len(value) % 4)
        raw_payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(raw_payload, dict):
            raise ValueError
        payload = cast(dict[str, object], raw_payload)
        if payload.get("v") != 1 or set(payload) != {"v", *keys}:
            raise ValueError
        return payload
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid storefront cursor") from error


@dataclass(frozen=True)
class ScanCursor:
    created_at: datetime
    scan_id: UUID


def encode_scan_cursor(cursor: ScanCursor) -> str:
    return _encode({"c": cursor.created_at.isoformat(), "s": str(cursor.scan_id)})


def decode_scan_cursor(value: str) -> ScanCursor:
    payload = _decode(value, {"c", "s"})
    created_at = payload["c"]
    if not isinstance(created_at, str):
        raise ValueError("Invalid storefront cursor")
    parsed = datetime.fromisoformat(created_at)
    if parsed.tzinfo is None:
        raise ValueError("Invalid storefront cursor")
    return ScanCursor(parsed, UUID(str(payload["s"])))


@dataclass(frozen=True)
class GarmentCursor:
    created_at: datetime
    garment_id: UUID


def encode_garment_cursor(cursor: GarmentCursor) -> str:
    return _encode({"c": cursor.created_at.isoformat(), "g": str(cursor.garment_id)})


def decode_garment_cursor(value: str) -> GarmentCursor:
    payload = _decode(value, {"c", "g"})
    created_at = payload["c"]
    if not isinstance(created_at, str):
        raise ValueError("Invalid storefront cursor")
    parsed = datetime.fromisoformat(created_at)
    if parsed.tzinfo is None:
        raise ValueError("Invalid storefront cursor")
    return GarmentCursor(parsed, UUID(str(payload["g"])))


@dataclass(frozen=True)
class MessageCursor:
    created_at: datetime
    message_id: UUID


def encode_message_cursor(cursor: MessageCursor) -> str:
    return _encode({"c": cursor.created_at.isoformat(), "m": str(cursor.message_id)})


def decode_message_cursor(value: str) -> MessageCursor:
    payload = _decode(value, {"c", "m"})
    created_at = payload["c"]
    if not isinstance(created_at, str):
        raise ValueError("Invalid storefront cursor")
    parsed = datetime.fromisoformat(created_at)
    if parsed.tzinfo is None:
        raise ValueError("Invalid storefront cursor")
    return MessageCursor(parsed, UUID(str(payload["m"])))
