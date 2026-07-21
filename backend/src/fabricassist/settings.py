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
        return self
