"""Typed application settings for the backend foundation."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal, cast
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentProfile(str, Enum):
    """Deployment topology selected at the infrastructure composition boundary."""

    LOCAL = "local"
    ALPHA = "alpha"
    PRODUCTION = "production"


class JobDispatcherType(str, Enum):
    """Configured asynchronous dispatch transport; adapters are added separately."""

    CELERY = "celery"
    QSTASH = "qstash"


class HotCacheBackend(str, Enum):
    """Configured best-effort hot-cache implementation."""

    VALKEY = "valkey"
    NOOP = "noop"


class RateLimiterBackend(str, Enum):
    """Configured shared request-rate limiter implementation."""

    VALKEY = "valkey"
    NOOP = "noop"


class ConcurrencyGateBackend(str, Enum):
    """Configured worker concurrency-gate implementation."""

    VALKEY = "valkey"
    NOOP = "noop"


class ObjectStorageBackend(str, Enum):
    """Configured private object-storage implementation."""

    S3 = "s3"


class ModelCapabilityProvider(str, Enum):
    """Constructible model adapters selectable per independent capability."""

    MOCK = "mock"
    GEMINI = "gemini"
    OPENAI_RESPONSES = "openai_responses"


class ProductInformationProviderType(str, Enum):
    MOCK = "mock"
    HTTP_JSON = "http_json"


class Settings(BaseSettings):
    """Runtime configuration loaded only from FabricAssist-prefixed variables."""

    model_config = SettingsConfigDict(
        env_prefix="FABRICASSIST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "alpha", "production"] = "development"
    deployment_profile: DeploymentProfile = DeploymentProfile.LOCAL
    job_dispatcher: JobDispatcherType = JobDispatcherType.CELERY
    hot_cache_backend: HotCacheBackend = HotCacheBackend.VALKEY
    rate_limiter_backend: RateLimiterBackend = RateLimiterBackend.VALKEY
    concurrency_gate_backend: ConcurrencyGateBackend = ConcurrencyGateBackend.VALKEY
    object_storage_backend: ObjectStorageBackend = ObjectStorageBackend.S3
    log_level: str = "INFO"
    access_token_secret: str = Field(
        default="change-me-local-access-secret-please-replace", min_length=32, repr=False
    )
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    default_tenant_slug: str = Field(default="fabricassist-development", min_length=3)
    app_base_url: str = "http://localhost:8081"
    api_public_url: str = "http://localhost:8000"
    cors_allowed_origins: str = "http://localhost:8081,http://localhost:19006"
    security_hsts_seconds: int = Field(default=31_536_000, ge=0, le=63_072_000)
    metrics_enabled: bool = True
    metrics_access_token: str = Field(default="", repr=False)
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "fabricassist-api"
    rate_limit_enabled: bool = True
    rate_limit_fail_open: bool = True
    rate_limit_global_per_minute: int = Field(default=600, ge=1, le=100_000)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10_000)
    rate_limit_analysis_per_minute: int = Field(default=10, ge=1, le=10_000)
    rate_limit_chat_per_minute: int = Field(default=20, ge=1, le=10_000)
    conversation_recent_message_limit: int = Field(default=12, ge=1, le=100)
    conversation_relevant_image_limit: int = Field(default=8, ge=1, le=20)
    worker_global_concurrency: int = Field(default=8, ge=1, le=1_000)
    worker_tenant_concurrency: int = Field(default=2, ge=1, le=100)
    worker_concurrency_lease_seconds: int = Field(default=300, ge=30, le=3_600)
    vision_max_concurrency: int = Field(default=1, ge=1, le=100)
    job_stage_budget_seconds: int = Field(default=75, ge=1, le=900)
    publication_recovery_interval_seconds: int = Field(default=30, ge=5, le=3_600)
    publication_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    deletion_max_attempts: int = Field(default=5, ge=1, le=100)
    default_image_retention_days: int = Field(default=7, ge=1, le=365)
    merged_garment_retention_days: int = Field(default=30, ge=1, le=3_650)
    s3_endpoint_url: str = "http://fabricassist-minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = Field(default="", repr=False)
    s3_secret_key: str = Field(default="", repr=False)
    s3_bucket: str = "fabricassist-local"
    s3_force_path_style: bool = True
    upload_max_bytes: int = Field(default=12 * 1024 * 1024, ge=1)
    upload_url_minutes: int = Field(default=10, ge=1, le=60)
    max_images_per_scan: int = Field(default=8, ge=1, le=20)
    analysis_lease_minutes: int = Field(default=5, ge=1, le=30)
    evidence_provider: ModelCapabilityProvider = ModelCapabilityProvider.MOCK
    care_planner_provider: ModelCapabilityProvider = ModelCapabilityProvider.MOCK
    chat_provider: ModelCapabilityProvider = ModelCapabilityProvider.MOCK
    openai_responses_base_url: str = ""
    openai_responses_api_key: str = Field(default="", repr=False)
    openai_responses_model: str = ""
    openai_responses_extra_headers_json: str = Field(default="{}", repr=False)
    vision_timeout_seconds: int = Field(default=120, ge=5, le=120)
    vision_max_input_tokens: int = Field(default=128_000, ge=1_024, le=128_000)
    vision_max_output_tokens: int = Field(default=16_000, ge=256, le=16_000)
    vision_debug_logging: bool = False
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    product_information_provider: ProductInformationProviderType = (
        ProductInformationProviderType.MOCK
    )
    product_http_json_base_url: str = ""
    product_http_json_api_key: str = Field(default="", repr=False)
    product_http_json_allowed_hosts: str = ""
    product_http_json_timeout_seconds: int = Field(default=10, ge=1, le=30)
    product_http_json_max_response_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    product_cache_minutes: int = Field(default=1_440, ge=1, le=43_200)

    database_url: str = Field(
        default=(
            "postgresql+psycopg://fabricassist_dev:change-me-local-postgres@"
            "fabricassist-postgres:5432/fabricassist_dev"
        ),
        min_length=1,
        repr=False,
    )
    database_migration_url: str = Field(default="", repr=False)
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=10, ge=0, le=20)
    database_pool_recycle_seconds: int = Field(default=-1, ge=-1, le=3_600)
    database_connect_attempts: int = Field(default=1, ge=1, le=5)
    database_connect_retry_seconds: float = Field(default=0, ge=0, le=30)
    valkey_url: str = Field(default="valkey://fabricassist-valkey:6379/0", repr=False)
    celery_broker_url: str = Field(
        default="redis://fabricassist-valkey:6379/0",
        repr=False,
    )
    qstash_token: str = Field(default="", repr=False)
    qstash_current_signing_key: str = Field(default="", repr=False)
    qstash_next_signing_key: str = Field(default="", repr=False)
    qstash_destination_url: str = ""
    cache_hot_ttl_seconds: int = Field(default=86_400, ge=60, le=604_800)

    @model_validator(mode="before")
    @classmethod
    def apply_alpha_defaults(cls, data: Any) -> Any:
        """Apply hosted-alpha limits without changing the local default values."""
        if not isinstance(data, dict):
            return data
        values = cast(dict[str, Any], data)
        profile = values.get("deployment_profile")
        environment = values.get("environment")
        if (
            profile in {DeploymentProfile.ALPHA, DeploymentProfile.ALPHA.value}
            or environment == "alpha"
        ):
            values = values.copy()
            values.setdefault("max_images_per_scan", 3)
            values.setdefault("database_pool_size", 2)
            values.setdefault("database_max_overflow", 1)
            values.setdefault("database_pool_recycle_seconds", 300)
            values.setdefault("database_connect_attempts", 3)
            values.setdefault("database_connect_retry_seconds", 1)
            return values
        return values

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self) -> Settings:
        """Reject local credentials and unsafe network policy in production."""
        if self.environment == "alpha" and self.deployment_profile != DeploymentProfile.ALPHA:
            raise ValueError(
                "FABRICASSIST_DEPLOYMENT_PROFILE must be alpha when environment is alpha"
            )
        if self.deployment_profile == DeploymentProfile.ALPHA and self.environment != "alpha":
            raise ValueError(
                "FABRICASSIST_ENVIRONMENT must be alpha for the alpha deployment profile"
            )
        if self.job_dispatcher == JobDispatcherType.QSTASH:
            if not self.qstash_token:
                raise ValueError("FABRICASSIST_QSTASH_TOKEN is required when QStash is selected")
            if not self.qstash_current_signing_key or not self.qstash_next_signing_key:
                raise ValueError(
                    "FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY and "
                    "FABRICASSIST_QSTASH_NEXT_SIGNING_KEY are required when QStash is selected"
                )
            if urlparse(self.qstash_destination_url).scheme != "https":
                raise ValueError(
                    "FABRICASSIST_QSTASH_DESTINATION_URL must use HTTPS when QStash is selected"
                )
        if self.job_dispatcher == JobDispatcherType.CELERY and not self.celery_broker_url.strip():
            raise ValueError("FABRICASSIST_CELERY_BROKER_URL is required when Celery is selected")
        uses_valkey_capability = (
            self.hot_cache_backend == HotCacheBackend.VALKEY
            or self.rate_limiter_backend == RateLimiterBackend.VALKEY
            or self.concurrency_gate_backend == ConcurrencyGateBackend.VALKEY
        )
        if uses_valkey_capability:
            if not self.valkey_url.strip():
                raise ValueError(
                    "FABRICASSIST_VALKEY_URL is required by the selected Valkey capability"
                )
        if self.deployment_profile == DeploymentProfile.ALPHA:
            origins = [
                origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()
            ]
            if (
                not origins
                or "*" in origins
                or any(urlparse(origin).scheme != "https" for origin in origins)
            ):
                raise ValueError(
                    "FABRICASSIST_CORS_ALLOWED_ORIGINS must contain explicit HTTPS origins in alpha"
                )
            if any(
                local_value in self.database_url
                for local_value in ("change-me", "fabricassist_dev", "fabricassist-postgres")
            ):
                raise ValueError(
                    "FABRICASSIST_DATABASE_URL must not use local development defaults in alpha"
                )
            if not self.database_migration_url:
                raise ValueError("FABRICASSIST_DATABASE_MIGRATION_URL is required in alpha")
            if "sslmode=require" not in self.database_url:
                raise ValueError("FABRICASSIST_DATABASE_URL must configure PostgreSQL TLS in alpha")
            if "sslmode=require" not in self.database_migration_url:
                raise ValueError(
                    "FABRICASSIST_DATABASE_MIGRATION_URL must configure PostgreSQL TLS in alpha"
                )
            if (
                self.s3_bucket == "fabricassist-local"
                or "fabricassist-minio" in self.s3_endpoint_url
                or "localhost" in self.s3_endpoint_url
            ):
                raise ValueError("FabricAssist MinIO defaults are forbidden in alpha")
            if urlparse(self.s3_endpoint_url).scheme != "https":
                raise ValueError("FABRICASSIST_S3_ENDPOINT_URL must use HTTPS in alpha")
            if urlparse(self.s3_public_endpoint_url).scheme != "https":
                raise ValueError("FABRICASSIST_S3_PUBLIC_ENDPOINT_URL must use HTTPS in alpha")
            if not self.s3_access_key or not self.s3_secret_key:
                raise ValueError(
                    "FABRICASSIST_S3_ACCESS_KEY and FABRICASSIST_S3_SECRET_KEY "
                    "are required in alpha"
                )
            if self.s3_region != "auto":
                raise ValueError("FABRICASSIST_S3_REGION must be auto in alpha")
            if self.s3_force_path_style:
                raise ValueError("FABRICASSIST_S3_FORCE_PATH_STYLE must be false in alpha")
            if self.max_images_per_scan > 3:
                raise ValueError("FABRICASSIST_MAX_IMAGES_PER_SCAN must not exceed 3 in alpha")
        if self.environment == "production" and (
            "change-me" in self.database_url
            or "fabricassist_dev" in self.database_url
            or "fabricassist-postgres" in self.database_url
        ):
            message = (
                "FABRICASSIST_DATABASE_URL must not use local development defaults in production"
            )
            raise ValueError(message)
        if self.environment == "production" and "change-me" in self.access_token_secret:
            raise ValueError("FABRICASSIST_ACCESS_TOKEN_SECRET must be configured in production")
        if self.environment == "production":
            origins = [
                origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()
            ]
            if (
                not origins
                or "*" in origins
                or any(urlparse(origin).scheme != "https" for origin in origins)
            ):
                raise ValueError(
                    "FABRICASSIST_CORS_ALLOWED_ORIGINS must contain explicit HTTPS origins "
                    "in production"
                )
            if urlparse(self.app_base_url).scheme != "https":
                raise ValueError("FABRICASSIST_APP_BASE_URL must use HTTPS in production")
            if urlparse(self.api_public_url).scheme != "https":
                raise ValueError("FABRICASSIST_API_PUBLIC_URL must use HTTPS in production")
            if bool(self.s3_access_key) != bool(self.s3_secret_key):
                raise ValueError("Configure both S3 static credentials or neither")
            if self.s3_access_key and (
                "change-me" in self.s3_secret_key or self.s3_access_key == "fabricassist-local"
            ):
                raise ValueError("FabricAssist S3 local credentials are forbidden in production")
            if self.s3_bucket == "fabricassist-local":
                raise ValueError("FabricAssist S3 local credentials are forbidden in production")
            if self.s3_endpoint_url and urlparse(self.s3_endpoint_url).scheme != "https":
                raise ValueError("FABRICASSIST_S3_ENDPOINT_URL must use HTTPS in production")
            if urlparse(self.s3_public_endpoint_url).scheme != "https":
                raise ValueError("FABRICASSIST_S3_PUBLIC_ENDPOINT_URL must use HTTPS in production")
            if (
                uses_valkey_capability
                and urlparse(self.valkey_url.replace("valkey://", "redis://", 1)).scheme != "rediss"
            ):
                raise ValueError("FABRICASSIST_VALKEY_URL must use TLS (rediss://) in production")
            broker_scheme = urlparse(
                self.celery_broker_url.replace("valkey://", "redis://", 1)
            ).scheme
            if self.job_dispatcher == JobDispatcherType.CELERY and broker_scheme not in {
                "rediss",
                "amqps",
            }:
                raise ValueError(
                    "FABRICASSIST_CELERY_BROKER_URL must use rediss:// or amqps:// in production"
                )
            if "sslmode=" not in self.database_url:
                raise ValueError(
                    "FABRICASSIST_DATABASE_URL must configure PostgreSQL TLS in production"
                )
            if self.vision_debug_logging:
                raise ValueError("FABRICASSIST_VISION_DEBUG_LOGGING must be false in production")
            if not self.rate_limit_enabled or self.rate_limit_fail_open:
                raise ValueError(
                    "Production rate limiting must be enabled and fail closed "
                    "when its backend is down"
                )
            if self.rate_limiter_backend == RateLimiterBackend.NOOP:
                raise ValueError(
                    "FABRICASSIST_RATE_LIMITER_BACKEND=noop is forbidden in production"
                )
            if self.concurrency_gate_backend == ConcurrencyGateBackend.NOOP:
                raise ValueError(
                    "FABRICASSIST_CONCURRENCY_GATE_BACKEND=noop is forbidden in production"
                )
            if self.metrics_enabled and len(self.metrics_access_token) < 32:
                raise ValueError(
                    "FABRICASSIST_METRICS_ACCESS_TOKEN must be at least 32 characters "
                    "when production metrics are enabled"
                )
        selected_model_capabilities = {
            self.evidence_provider,
            self.care_planner_provider,
            self.chat_provider,
        }
        if ModelCapabilityProvider.OPENAI_RESPONSES in selected_model_capabilities and (
            not self.openai_responses_base_url
            or not self.openai_responses_api_key
            or not self.openai_responses_model
        ):
            raise ValueError(
                "FABRICASSIST_OPENAI_RESPONSES_BASE_URL, "
                "FABRICASSIST_OPENAI_RESPONSES_API_KEY, and "
                "FABRICASSIST_OPENAI_RESPONSES_MODEL are required for "
                "the OpenAI Responses provider"
            )
        if (
            ModelCapabilityProvider.GEMINI in selected_model_capabilities
            and not self.gemini_api_key
        ):
            raise ValueError(
                "FABRICASSIST_GEMINI_API_KEY is required when the Gemini provider is selected"
            )
        try:
            headers = json.loads(self.openai_responses_extra_headers_json)
        except json.JSONDecodeError as error:
            raise ValueError(
                "FABRICASSIST_OPENAI_RESPONSES_EXTRA_HEADERS_JSON must contain valid JSON"
            ) from error
        if not isinstance(headers, dict):
            raise ValueError(
                "FABRICASSIST_OPENAI_RESPONSES_EXTRA_HEADERS_JSON must be "
                "a JSON object of string headers"
            )
        typed_headers = cast(dict[object, object], headers)
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in typed_headers.items()
        ):
            raise ValueError(
                "FABRICASSIST_OPENAI_RESPONSES_EXTRA_HEADERS_JSON must be "
                "a JSON object of string headers"
            )
        if self.product_information_provider is ProductInformationProviderType.HTTP_JSON and (
            not self.product_http_json_base_url or not self.product_http_json_allowed_hosts
        ):
            raise ValueError(
                "FABRICASSIST_PRODUCT_HTTP_JSON_BASE_URL and "
                "FABRICASSIST_PRODUCT_HTTP_JSON_ALLOWED_HOSTS are required"
            )
        return self

    @property
    def migration_database_url(self) -> str:
        """Use a direct administrative URL when configured, otherwise the local runtime URL."""
        return self.database_migration_url or self.database_url
