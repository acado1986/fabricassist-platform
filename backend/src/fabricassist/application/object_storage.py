"""Application-facing private object-storage capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ObjectStorageError(RuntimeError):
    """Technology-neutral storage failure."""


class RetryableObjectStorageError(ObjectStorageError):
    """A transient storage failure safe to retry."""


class PermanentObjectStorageError(ObjectStorageError):
    """A storage failure that retry cannot repair."""


class ObjectNotFoundError(ObjectStorageError):
    """The requested private object does not exist."""


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    headers: dict[str, str]
    expires_at: datetime

    def __iter__(self):
        yield self.url
        yield self.headers
        yield self.expires_at


@dataclass(frozen=True)
class PresignedDownload:
    url: str
    expires_at: datetime

    def __iter__(self):
        yield self.url
        yield self.expires_at


@dataclass(frozen=True)
class ObjectMetadata:
    content_type: str
    byte_size: int
    width: int
    height: int
    quality_state: str = "unknown"
    blur_score: float | None = None
    brightness_score: float | None = None
    contrast_score: float | None = None
    glare_score: float | None = None
    crop_readability_score: float | None = None
    orientation_degrees: int | None = None


class ObjectStorage(Protocol):
    def presign_put(self, *, key: str, content_type: str) -> PresignedUpload: ...

    def presign_get(
        self, *, key: str, download_filename: str | None = None
    ) -> PresignedDownload: ...

    def verify_image(self, key: str, declared_mime_type: str) -> ObjectMetadata: ...

    def read_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...
