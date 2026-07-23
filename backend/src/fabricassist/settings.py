"""Typed application settings for the backend foundation."""

from __future__ import annotations

import json
from typing import Literal, cast

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded only from FabricAssist-prefixed variables."""

    model_config = SettingsConfigDict(
        env_prefix="FABRICASSIST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    access_token_secret: str = Field(
        default="change-me-local-access-secret-please-replace", min_length=32
    )
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    default_tenant_slug: str = Field(default="fabricassist-development", min_length=3)
    cors_origins: str = "http://localhost:8081,http://localhost:19006"
    s3_endpoint_url: str = "http://fabricassist-minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "fabricassist-local"
    s3_secret_key: str = "change-me-local-minio"
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
    valkey_url: str = Field(default="valkey://fabricassist-valkey:6379/0", min_length=1)
    cache_hot_mirror_enabled: bool = False
    cache_hot_ttl_seconds: int = Field(default=86_400, ge=60, le=604_800)

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self) -> Settings:
        """Prevent the known local database default from being used in production."""
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
