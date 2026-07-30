"""Small immutable runtime policies constructed at composition roots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisExecutionPolicy:
    hot_cache_ttl_seconds: int
    product_cache_minutes: int


@dataclass(frozen=True)
class JobExecutionPolicy:
    stage_budget_seconds: int


@dataclass(frozen=True)
class ConversationPolicy:
    recent_message_limit: int
    relevant_image_limit: int


@dataclass(frozen=True)
class ProductLookupPolicy:
    cache_minutes: int


@dataclass(frozen=True)
class UploadPolicy:
    max_images_per_scan: int
