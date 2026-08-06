"""S3-compatible implementation of the private object-storage capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, cast

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from PIL import Image, UnidentifiedImageError

from fabricassist.application.object_storage import (
    ObjectMetadata,
    ObjectNotFoundError,
    ObjectStorageError,
    PermanentObjectStorageError,
    PresignedDownload,
    PresignedUpload,
    RetryableObjectStorageError,
)
from fabricassist.infrastructure.garment_analysis.images import assess_image_quality

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True)
class S3ObjectStorageConfig:
    endpoint_url: str
    public_endpoint_url: str
    region: str
    bucket: str
    force_path_style: bool
    upload_max_bytes: int
    upload_url_minutes: int
    access_key: str = field(default="", repr=False)
    secret_key: str = field(default="", repr=False)


class S3ObjectStorageAdapter:
    """Keep boto3, credentials, buckets, and provider exceptions inside infrastructure."""

    def __init__(self, config: S3ObjectStorageConfig) -> None:
        self._config = config
        client_factory: Any = cast(Any, boto3).client
        credentials = (
            {
                "aws_access_key_id": config.access_key,
                "aws_secret_access_key": config.secret_key,
            }
            if config.access_key and config.secret_key
            else {}
        )
        boto_config = Config(
            s3={"addressing_style": "path" if config.force_path_style else "virtual"}
        )
        self._client: Any = client_factory(
            "s3",
            endpoint_url=config.endpoint_url or None,
            region_name=config.region,
            **credentials,
            config=boto_config,
        )
        self._presign_client: Any = client_factory(
            "s3",
            endpoint_url=config.public_endpoint_url or None,
            region_name=config.region,
            **credentials,
            config=boto_config,
        )

    @staticmethod
    def _translate(error: Exception) -> ObjectStorageError:
        if isinstance(error, ClientError):
            response = cast(
                dict[str, Any],
                cast(object, error.response),  # pyright: ignore[reportUnknownMemberType]
            )
            code = str(cast(dict[str, Any], response.get("Error", {})).get("Code", ""))
            status = int(
                cast(dict[str, Any], response.get("ResponseMetadata", {})).get("HTTPStatusCode", 0)
            )
            if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
                return ObjectNotFoundError("Object does not exist")
            if status == 429 or status >= 500:
                return RetryableObjectStorageError("Object storage is temporarily unavailable")
            return PermanentObjectStorageError("Object storage rejected the operation")
        if isinstance(
            error,
            ConnectionClosedError
            | ConnectTimeoutError
            | EndpointConnectionError
            | ReadTimeoutError
            | BotoCoreError,
        ):
            return RetryableObjectStorageError("Object storage is temporarily unavailable")
        return PermanentObjectStorageError("Object storage operation failed")

    def presign_put(self, *, key: str, content_type: str) -> PresignedUpload:
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError("Unsupported image type.")
        expires = datetime.now(UTC) + timedelta(minutes=self._config.upload_url_minutes)
        try:
            url = str(
                self._presign_client.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self._config.bucket,
                        "Key": key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=self._config.upload_url_minutes * 60,
                    HttpMethod="PUT",
                )
            )
        except Exception as error:
            raise self._translate(error) from error
        return PresignedUpload(url=url, headers={"Content-Type": content_type}, expires_at=expires)

    def presign_get(self, *, key: str, download_filename: str | None = None) -> PresignedDownload:
        expires = datetime.now(UTC) + timedelta(minutes=self._config.upload_url_minutes)
        try:
            params: dict[str, str] = {"Bucket": self._config.bucket, "Key": key}
            if download_filename:
                params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
            url = str(
                self._presign_client.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=self._config.upload_url_minutes * 60,
                    HttpMethod="GET",
                )
            )
        except Exception as error:
            raise self._translate(error) from error
        return PresignedDownload(url=url, expires_at=expires)

    def verify_image(self, key: str, declared_mime_type: str) -> ObjectMetadata:
        try:
            head: dict[str, Any] = self._client.head_object(Bucket=self._config.bucket, Key=key)
            content_type = str(head.get("ContentType", "")).split(";", 1)[0].lower()
            byte_size = int(head.get("ContentLength", 0))
            if (
                content_type not in ALLOWED_MIME_TYPES
                or content_type != declared_mime_type
                or byte_size > self._config.upload_max_bytes
                or byte_size <= 0
            ):
                raise ValueError("Uploaded image metadata is invalid.")
            body = cast(
                bytes,
                self._client.get_object(Bucket=self._config.bucket, Key=key)["Body"].read(),
            )
        except ValueError:
            raise
        except Exception as error:
            raise self._translate(error) from error
        try:
            with Image.open(BytesIO(body)) as image:
                image.verify()
            with Image.open(BytesIO(body)) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("Uploaded content is not a valid image.") from error
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise ValueError("Uploaded image dimensions are unsafe.")
        quality = assess_image_quality(body)
        return ObjectMetadata(
            content_type=content_type,
            byte_size=byte_size,
            width=width,
            height=height,
            quality_state=quality.state,
            blur_score=quality.blur_score,
            brightness_score=quality.brightness_score,
            contrast_score=quality.contrast_score,
            glare_score=quality.glare_score,
            crop_readability_score=quality.crop_readability_score,
            orientation_degrees=quality.orientation_degrees,
        )

    def read_object(self, key: str) -> bytes:
        try:
            return cast(
                bytes,
                self._client.get_object(Bucket=self._config.bucket, Key=key)["Body"].read(),
            )
        except Exception as error:
            raise self._translate(error) from error

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._config.bucket, Key=key)
        except Exception as error:
            raise self._translate(error) from error
