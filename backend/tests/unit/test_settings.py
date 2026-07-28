from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from fabricassist.settings import DeploymentProfile, JobDispatcherType, Settings


def alpha_settings(**overrides: object) -> Settings:
    """Return complete synthetic alpha settings without using a real credential."""
    values: dict[str, object] = {
        "environment": "alpha",
        "deployment_profile": DeploymentProfile.ALPHA,
        "job_dispatcher": JobDispatcherType.QSTASH,
        "access_token_secret": "alpha-access-token-secret-that-is-long-enough",
        "app_base_url": "https://app.example.test",
        "api_public_url": "https://api.example.test",
        "cors_allowed_origins": "https://app.example.test",
        "database_url": "postgresql://alpha:password@db.example.test/fabricassist?sslmode=require",
        "s3_endpoint_url": "https://account.r2.cloudflarestorage.com",
        "s3_public_endpoint_url": "https://account.r2.cloudflarestorage.com",
        "s3_bucket": "fabricassist-alpha",
        "s3_force_path_style": False,
        "qstash_token": "synthetic-qstash-token",
        "qstash_current_signing_key": "synthetic-current-signing-key",
        "qstash_next_signing_key": "synthetic-next-signing-key",
        "qstash_destination_url": "https://api.example.test/internal/jobs/qstash",
        "valkey_url": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_azure_provider_requires_its_complete_configuration() -> None:
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        Settings(vision_provider="azure_openai")


def test_settings_accept_test_configuration() -> None:
    settings = Settings(environment="test", database_url="postgresql://example.test/fabricassist")

    assert settings.environment == "test"
    assert settings.vision_max_input_tokens == 128_000
    assert settings.vision_max_output_tokens == 16_000


def test_vision_token_limits_cannot_exceed_the_model_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(vision_max_input_tokens=128_001)
    with pytest.raises(ValidationError):
        Settings(vision_max_output_tokens=16_001)


def test_production_rejects_local_database_defaults() -> None:
    with pytest.raises(ValidationError, match="must not use local development defaults"):
        Settings(environment="production")


def test_alpha_settings_accept_complete_qstash_configuration_without_valkey() -> None:
    settings = alpha_settings()

    assert settings.deployment_profile == DeploymentProfile.ALPHA
    assert settings.job_dispatcher == JobDispatcherType.QSTASH
    assert settings.valkey_url == ""
    assert settings.max_images_per_scan == 3
    assert settings.vision_max_concurrency == 1


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"qstash_token": ""}, "QSTASH_TOKEN"),
        ({"qstash_current_signing_key": ""}, "CURRENT_SIGNING_KEY"),
        ({"qstash_next_signing_key": ""}, "NEXT_SIGNING_KEY"),
        ({"qstash_destination_url": "http://api.example.test/jobs"}, "DESTINATION_URL"),
        ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS"),
        (
            {"database_url": "postgresql://fabricassist_dev:change-me@fabricassist-postgres/db"},
            "DATABASE_URL",
        ),
        ({"s3_endpoint_url": "http://fabricassist-minio:9000"}, "MinIO defaults"),
        ({"max_images_per_scan": 4}, "MAX_IMAGES_PER_SCAN"),
    ],
)
def test_alpha_settings_reject_unsafe_or_incomplete_configuration(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        alpha_settings(**overrides)


def test_alpha_settings_require_matching_environment_and_profile() -> None:
    with pytest.raises(ValidationError, match="DEPLOYMENT_PROFILE"):
        Settings(environment="alpha")
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        alpha_settings(environment="production")


def test_alpha_secret_settings_are_not_expo_public_configuration() -> None:
    frontend_config = (
        Path(__file__).resolve().parents[3] / "frontend/apps/client/app.config.ts"
    ).read_text()
    secret_names = (
        "QSTASH_TOKEN",
        "QSTASH_CURRENT_SIGNING_KEY",
        "QSTASH_NEXT_SIGNING_KEY",
        "DATABASE_URL",
        "S3_SECRET_KEY",
    )

    assert all(secret_name not in frontend_config for secret_name in secret_names)
    assert all(not field_name.startswith("expo_public_") for field_name in Settings.model_fields)
