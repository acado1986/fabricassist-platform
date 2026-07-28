"""Portable private-object contract for MinIO and opt-in R2 smoke runs."""

from __future__ import annotations

import os
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings

pytestmark = pytest.mark.integration


def contract_settings() -> Settings:
    """Build storage-only settings without provider defaults or credentials in source."""
    if os.environ.get("FABRICASSIST_OBJECT_STORAGE_CONTRACT") != "1":
        pytest.skip("Storage contract is enabled by its explicit Make target.")
    endpoint = os.environ["FABRICASSIST_OBJECT_STORAGE_ENDPOINT_URL"]
    return Settings(
        environment="test",
        s3_endpoint_url=endpoint,
        s3_public_endpoint_url=endpoint,
        s3_region=os.environ["FABRICASSIST_OBJECT_STORAGE_REGION"],
        s3_bucket=os.environ["FABRICASSIST_OBJECT_STORAGE_BUCKET"],
        s3_access_key=os.environ["FABRICASSIST_OBJECT_STORAGE_ACCESS_KEY"],
        s3_secret_key=os.environ["FABRICASSIST_OBJECT_STORAGE_SECRET_KEY"],
        s3_force_path_style=os.environ["FABRICASSIST_OBJECT_STORAGE_FORCE_PATH_STYLE"] == "true",
    )


@pytest.fixture
def storage() -> S3Storage:
    return S3Storage(contract_settings())


@pytest.fixture
def object_prefix() -> str:
    configured = os.environ.get("FABRICASSIST_OBJECT_STORAGE_TEST_PREFIX", "contract")
    return f"{configured.strip('/')}/{uuid4()}"


def jpeg_bytes() -> bytes:
    image = BytesIO()
    Image.new("RGB", (32, 24), "white").save(image, "JPEG")
    return image.getvalue()


def test_private_object_lifecycle_contract(storage: S3Storage, object_prefix: str) -> None:
    """Exercise upload verification, private reads, derivatives, previews, and deletion."""
    source_key = f"{object_prefix}/tenant-a/source.jpg"
    derivative_key = f"{object_prefix}/tenant-a/derivatives/normalized.jpg"
    other_tenant_key = f"{object_prefix}/tenant-b/source.jpg"
    raw = jpeg_bytes()

    storage._client.put_object(  # pyright: ignore[reportPrivateUsage]
        Bucket=storage._settings.s3_bucket,  # pyright: ignore[reportPrivateUsage]
        Key=source_key,
        Body=raw,
        ContentType="image/jpeg",
    )
    metadata = storage.verify_image(source_key, "image/jpeg")
    assert (metadata.content_type, metadata.width, metadata.height) == ("image/jpeg", 32, 24)
    assert storage.read_object(source_key) == raw

    storage._client.put_object(  # pyright: ignore[reportPrivateUsage]
        Bucket=storage._settings.s3_bucket,  # pyright: ignore[reportPrivateUsage]
        Key=derivative_key,
        Body=raw,
        ContentType="image/jpeg",
    )
    storage._client.put_object(  # pyright: ignore[reportPrivateUsage]
        Bucket=storage._settings.s3_bucket,  # pyright: ignore[reportPrivateUsage]
        Key=other_tenant_key,
        Body=raw,
        ContentType="image/jpeg",
    )
    preview, _expires_at = storage.presign_get(key=source_key)
    upload, headers, _upload_expires_at = storage.presign_put(
        key=f"{object_prefix}/tenant-a/future.jpg", content_type="image/jpeg"
    )
    assert source_key in preview
    assert {"X-Amz-Expires", "Expires"} & set(parse_qs(urlparse(preview).query))
    assert headers == {"Content-Type": "image/jpeg"}
    assert {"X-Amz-Expires", "Expires"} & set(parse_qs(urlparse(upload).query))

    visible_keys = {
        item["Key"]
        for item in storage._client.list_objects_v2(  # pyright: ignore[reportPrivateUsage]
            Bucket=storage._settings.s3_bucket,  # pyright: ignore[reportPrivateUsage]
            Prefix=f"{object_prefix}/tenant-a/",
        ).get("Contents", [])
    }
    assert source_key in visible_keys
    assert other_tenant_key not in visible_keys

    storage.delete_object(source_key)
    storage.delete_object(derivative_key)
    storage.delete_object(other_tenant_key)
    with pytest.raises(ClientError):
        storage.verify_image(source_key, "image/jpeg")


def test_invalid_key_is_not_treated_as_an_uploaded_image(
    storage: S3Storage, object_prefix: str
) -> None:
    with pytest.raises(ClientError):
        storage.verify_image(f"{object_prefix}/missing.jpg", "image/jpeg")
