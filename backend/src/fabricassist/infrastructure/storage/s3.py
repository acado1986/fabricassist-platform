"""S3-compatible storage adapter for Phase 7 direct uploads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, cast

import boto3
from botocore.config import Config
from PIL import Image, UnidentifiedImageError

from fabricassist.settings import Settings

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True)
class ObjectMetadata:
    content_type: str
    byte_size: int
    width: int
    height: int


class S3Storage:
    """Only generates scoped URLs and verifies private objects; it never logs URLs or bytes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        client_factory: Any = cast(Any, boto3).client
        self._client: Any = client_factory(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                s3={"addressing_style": "path" if settings.s3_force_path_style else "virtual"}
            ),
        )
        self._presign_client: Any = client_factory(
            "s3",
            endpoint_url=settings.s3_public_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                s3={"addressing_style": "path" if settings.s3_force_path_style else "virtual"}
            ),
        )

    def presign_put(self, *, key: str, content_type: str) -> tuple[str, dict[str, str], datetime]:
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError("Unsupported image type.")
        expires = datetime.now(UTC) + timedelta(minutes=self._settings.upload_url_minutes)
        url = str(
            self._presign_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._settings.s3_bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=self._settings.upload_url_minutes * 60,
                HttpMethod="PUT",
            )
        )
        return url, {"Content-Type": content_type}, expires

    def verify_image(self, key: str, declared_mime_type: str) -> ObjectMetadata:
        head: dict[str, Any] = self._client.head_object(Bucket=self._settings.s3_bucket, Key=key)
        content_type = str(head.get("ContentType", "")).split(";", 1)[0].lower()
        byte_size = int(head.get("ContentLength", 0))
        if (
            content_type not in ALLOWED_MIME_TYPES
            or content_type != declared_mime_type
            or byte_size > self._settings.upload_max_bytes
            or byte_size <= 0
        ):
            raise ValueError("Uploaded image metadata is invalid.")
        body = cast(
            bytes, self._client.get_object(Bucket=self._settings.s3_bucket, Key=key)["Body"].read()
        )
        try:
            with Image.open(BytesIO(body)) as image:
                image.verify()
            with Image.open(BytesIO(body)) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("Uploaded content is not a valid image.") from error
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise ValueError("Uploaded image dimensions are unsafe.")
        return ObjectMetadata(
            content_type=content_type, byte_size=byte_size, width=width, height=height
        )

    def read_object(self, key: str) -> bytes:
        """Read a private object for worker-only processing; callers must authorize first."""
        return cast(
            bytes, self._client.get_object(Bucket=self._settings.s3_bucket, Key=key)["Body"].read()
        )

    def delete_object(self, key: str) -> None:
        """Delete a private object; callers retain retry/audit responsibility."""
        self._client.delete_object(Bucket=self._settings.s3_bucket, Key=key)
