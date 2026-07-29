"""Object-storage composition root."""

from __future__ import annotations

from fabricassist.application.object_storage import ObjectStorage
from fabricassist.infrastructure.storage.s3 import (
    S3ObjectStorageAdapter,
    S3ObjectStorageConfig,
)
from fabricassist.settings import ObjectStorageBackend, Settings


def create_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_backend is not ObjectStorageBackend.S3:
        raise ValueError(f"Unsupported object storage backend: {settings.object_storage_backend}")
    return S3ObjectStorageAdapter(
        S3ObjectStorageConfig(
            endpoint_url=settings.s3_endpoint_url,
            public_endpoint_url=settings.s3_public_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            force_path_style=settings.s3_force_path_style,
            upload_max_bytes=settings.upload_max_bytes,
            upload_url_minutes=settings.upload_url_minutes,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    )
