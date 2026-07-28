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
    log_level: str = "INFO"
    access_token_secret: str = Field(
        default="change-me-local-access-secret-please-replace", min_length=32
    )
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    default_tenant_slug: str = Field(default="fabricassist-development", min_length=3)
    app_base_url: str = "http://localhost:8081"
    api_public_url: str = "http://localhost:8000"
    cors_allowed_origins: str = "http://localhost:8081,http://localhost:19006"
    security_hsts_seconds: int = Field(default=31_536_000, ge=0, le=63_072_000)
    metrics_enabled: bool = True
    metrics_access_token: str = ""
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "fabricassist-api"
    rate_limit_enabled: bool = True
    rate_limit_fail_open: bool = True
    rate_limit_global_per_minute: int = Field(default=600, ge=1, le=100_000)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10_000)
    rate_limit_analysis_per_minute: int = Field(default=10, ge=1, le=10_000)
    rate_limit_chat_per_minute: int = Field(default=20, ge=1, le=10_000)
    worker_global_concurrency: int = Field(default=8, ge=1, le=1_000)
    worker_tenant_concurrency: int = Field(default=2, ge=1, le=100)
    worker_concurrency_lease_seconds: int = Field(default=300, ge=30, le=3_600)
    vision_max_concurrency: int = Field(default=1, ge=1, le=100)
    job_stage_budget_seconds: int = Field(default=75, ge=1, le=900)
    default_image_retention_days: int = Field(default=7, ge=1, le=365)
    s3_endpoint_url: str = "http://fabricassist-minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "fabricassist-local"
    s3_force_path_style: bool = True
    upload_max_bytes: int = Field(default=12 * 1024 * 1024, ge=1)
    upload_url_minutes: int = Field(default=10, ge=1, le=60)
    max_images_per_scan: int = Field(default=8, ge=1, le=20)
    analysis_lease_minutes: int = Field(default=5, ge=1, le=30)
    vision_provider: Literal["mock", "openai_compatible", "openai_responses", "azure_openai"] = (
        "mock"
    )
    vision_base_url: str = ""
    vision_api_key: str = ""
    vision_model: str = ""
    vision_extra_headers_json: str = "{}"
    vision_timeout_seconds: int = Field(default=120, ge=5, le=120)
    vision_max_input_tokens: int = Field(default=128_000, ge=1_024, le=128_000)
    vision_max_output_tokens: int = Field(default=16_000, ge=256, le=16_000)
    vision_debug_logging: bool = False
    product_provider: Literal["mock", "http_json"] = "mock"
    product_base_url: str = ""
    product_api_key: str = ""
    product_allowed_hosts: str = ""
    product_timeout_seconds: int = Field(default=10, ge=1, le=30)
    product_max_response_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    product_cache_minutes: int = Field(default=1_440, ge=1, le=43_200)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    database_url: str = Field(
        default=(
            "postgresql+psycopg://fabricassist_dev:change-me-local-postgres@"
            "fabricassist-postgres:5432/fabricassist_dev"
        ),
        min_length=1,
    )
    database_migration_url: str = ""
    valkey_url: str = "valkey://fabricassist-valkey:6379/0"
    qstash_token: str = ""
    qstash_current_signing_key: str = ""
    qstash_next_signing_key: str = ""
    qstash_destination_url: str = ""
    cache_hot_mirror_enabled: bool = False
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
            if urlparse(self.valkey_url.replace("valkey://", "redis://", 1)).scheme != "rediss":
                raise ValueError("FABRICASSIST_VALKEY_URL must use TLS (rediss://) in production")
            if "sslmode=" not in self.database_url:
                raise ValueError(
                    "FABRICASSIST_DATABASE_URL must configure PostgreSQL TLS in production"
                )
            if self.vision_debug_logging:
                raise ValueError("FABRICASSIST_VISION_DEBUG_LOGGING must be false in production")
            if not self.rate_limit_enabled or self.rate_limit_fail_open:
                raise ValueError(
                    "Production rate limiting must be enabled and fail closed when Valkey is down"
                )
            if self.metrics_enabled and len(self.metrics_access_token) < 32:
                raise ValueError(
                    "FABRICASSIST_METRICS_ACCESS_TOKEN must be at least 32 characters "
                    "when production metrics are enabled"
                )
        if self.vision_provider in {"openai_compatible", "openai_responses"} and (
            not self.vision_base_url or not self.vision_api_key or not self.vision_model
        ):
            raise ValueError(
                "FABRICASSIST_VISION_BASE_URL, FABRICASSIST_VISION_API_KEY, and "
                "FABRICASSIST_VISION_MODEL are required for the OpenAI-compatible provider"
            )
        try:
            headers = json.loads(self.vision_extra_headers_json)
        except json.JSONDecodeError as error:
            raise ValueError(
                "FABRICASSIST_VISION_EXTRA_HEADERS_JSON must contain valid JSON"
            ) from error
        if not isinstance(headers, dict):
            raise ValueError(
                "FABRICASSIST_VISION_EXTRA_HEADERS_JSON must be a JSON object of string headers"
            )
        typed_headers = cast(dict[object, object], headers)
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in typed_headers.items()
        ):
            raise ValueError(
                "FABRICASSIST_VISION_EXTRA_HEADERS_JSON must be a JSON object of string headers"
            )
        if self.vision_provider == "azure_openai" and (
            not self.azure_openai_endpoint
            or not self.azure_openai_api_key
            or not self.azure_openai_deployment
        ):
            raise ValueError(
                "FABRICASSIST_AZURE_OPENAI_ENDPOINT, FABRICASSIST_AZURE_OPENAI_API_KEY, and "
                "FABRICASSIST_AZURE_OPENAI_DEPLOYMENT are required for the Azure OpenAI provider"
            )
        if self.product_provider == "http_json" and (
            not self.product_base_url or not self.product_allowed_hosts
        ):
            raise ValueError(
                "FABRICASSIST_PRODUCT_BASE_URL and FABRICASSIST_PRODUCT_ALLOWED_HOSTS are required"
            )
        return self
