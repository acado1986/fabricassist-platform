#!/usr/bin/env python3
"""Exercise the hosted alpha API without printing credentials or upload URLs."""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required {name}")
    return value


def request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[dict[str, object], dict[str, str]]:
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    try:
        with urlopen(
            Request(base_url + path, data=body, method=method, headers=request_headers),
            timeout=30,
        ) as response:
            status = response.status
            response_body = response.read()
            response_headers = dict(response.headers.items())
    except HTTPError as error:
        status = error.code
        response_body = error.read()
        response_headers = dict(error.headers.items())
    except URLError as error:
        raise RuntimeError(f"request failed for {path}: {error.reason}") from error
    if status not in expected:
        error_code = "unknown"
        correlation_id = response_headers.get("X-Correlation-ID", "unknown")
        try:
            decoded = json.loads(response_body)
            if isinstance(decoded, dict):
                error = decoded.get("error")
                if isinstance(error, dict):
                    error_code = str(error.get("code", error_code))
                    correlation_id = str(error.get("correlation_id", correlation_id))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        raise RuntimeError(
            f"unexpected HTTP {status} for {method} {path} "
            f"(code={error_code}, correlation_id={correlation_id})"
        )
    return (json.loads(response_body) if response_body else {}, response_headers)


def upload(upload_url: str, upload_headers: dict[str, str], image_path: Path) -> None:
    headers = dict(upload_headers)
    headers.setdefault("Content-Type", "image/png")
    try:
        with urlopen(
            Request(
                upload_url, data=image_path.read_bytes(), method="PUT", headers=headers
            ),
            timeout=30,
        ) as response:
            if response.status not in {200, 201, 204}:
                raise RuntimeError(f"unexpected upload HTTP {response.status}")
    except HTTPError as error:
        raise RuntimeError(f"unexpected upload HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"upload request failed: {error.reason}") from error


def fixture_png() -> bytes:
    """Create a high-variance 256px PNG so image-quality validation can proceed."""
    width = height = 256
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            value = 32 if (x // 16 + y // 16) % 2 else 224
            row.extend((value, 255 - value, value // 2))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    base_url = required("FABRICASSIST_ALPHA_API_URL").rstrip("/")
    email = required("FABRICASSIST_ALPHA_SMOKE_EMAIL")
    password = required("FABRICASSIST_ALPHA_SMOKE_PASSWORD")
    timeout = int(os.environ.get("FABRICASSIST_ALPHA_SMOKE_TIMEOUT_SECONDS", "180"))

    request(base_url, "/api/v1/health/live")
    request(base_url, "/api/v1/health/ready")
    session, _ = request(
        base_url,
        "/api/v1/auth/login",
        method="POST",
        payload={"email": email, "password": password},
    )
    token = str(session["access_token"])
    auth = {"Authorization": f"Bearer {token}"}
    scan, _ = request(
        base_url,
        "/api/v1/scans",
        method="POST",
        payload={"requested_language": "en"},
        headers=auth,
        expected=(201,),
    )
    scan_id = str(scan["scan_id"])
    image_request = {
        "role": "care_label",
        "content_type": "image/png",
        "display_order": 0,
    }
    idempotency_key = str(uuid4())
    upload_instruction, _ = request(
        base_url,
        f"/api/v1/scans/{scan_id}/images",
        method="POST",
        payload=image_request,
        headers={**auth, "Idempotency-Key": idempotency_key},
        expected=(201,),
    )
    repeated_instruction, _ = request(
        base_url,
        f"/api/v1/scans/{scan_id}/images",
        method="POST",
        payload=image_request,
        headers={**auth, "Idempotency-Key": idempotency_key},
        expected=(201,),
    )
    if repeated_instruction.get("image_id") != upload_instruction.get("image_id"):
        raise RuntimeError("image idempotency did not return the original image")

    descriptor, temporary_path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    image_path = Path(temporary_path)
    try:
        image_path.write_bytes(fixture_png())
        upload(
            str(upload_instruction["url"]),
            dict(upload_instruction["headers"]),
            image_path,
        )
        request(
            base_url,
            f"/api/v1/scans/{scan_id}/uploads/complete",
            method="POST",
            payload={
                "image_id": upload_instruction["image_id"],
                "content_type": "image/png",
            },
            headers=auth,
        )
        analysis_key = str(uuid4())
        analysis, _ = request(
            base_url,
            f"/api/v1/scans/{scan_id}/analyse",
            method="POST",
            payload={},
            headers={**auth, "Idempotency-Key": analysis_key},
            expected=(202,),
        )
        repeated_analysis, _ = request(
            base_url,
            f"/api/v1/scans/{scan_id}/analyse",
            method="POST",
            payload={},
            headers={**auth, "Idempotency-Key": analysis_key},
            expected=(202,),
        )
        if repeated_analysis.get("operation_key") != analysis.get("operation_key"):
            raise RuntimeError(
                "analysis idempotency did not return the original operation"
            )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            detail, _ = request(base_url, f"/api/v1/scans/{scan_id}", headers=auth)
            if detail.get("status") in {
                "completed",
                "needs_review",
                "needs_better_image",
            }:
                break
            if detail.get("status") in {"failed", "deleted"}:
                raise RuntimeError(f"analysis ended with {detail.get('status')}")
            time.sleep(3)
        else:
            raise RuntimeError("analysis did not complete before the smoke timeout")
        request(base_url, f"/api/v1/scans/{scan_id}/result", headers=auth)
        request(
            base_url,
            f"/api/v1/scans/{scan_id}",
            method="DELETE",
            headers=auth,
            expected=(202,),
        )
    finally:
        image_path.unlink(missing_ok=True)
    print("FabricAssist alpha live smoke passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"FabricAssist alpha live smoke failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
