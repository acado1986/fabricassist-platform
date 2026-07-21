"""Typed application settings for the backend foundation."""

from __future__ import annotations

from typing import Literal

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

    database_url: str = Field(
        default=(
            "postgresql+psycopg://fabricassist_dev:change-me-local-postgres@"
            "fabricassist-postgres:5432/fabricassist_dev"
        ),
        min_length=1,
    )

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
        return self
