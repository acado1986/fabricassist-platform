from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from fabricassist.settings import (
    ConcurrencyGateBackend,
    DeploymentProfile,
    HotCacheBackend,
    JobDispatcherType,
    ModelCapabilityProvider,
    RateLimiterBackend,
    Settings,
)


def qstash_settings(**overrides: object) -> Settings:
    """Return a provider-neutral test configuration for QStash settings."""
    values: dict[str, object] = {
        "environment": "test",
        "deployment_profile": DeploymentProfile.LOCAL,
        "job_dispatcher": JobDispatcherType.QSTASH,
        "hot_cache_backend": "noop",
        "rate_limiter_backend": "noop",
        "concurrency_gate_backend": "noop",
        "access_token_secret": "test-access-token-secret-that-is-long-enough",
        "app_base_url": "https://app.example.test",
        "api_public_url": "https://api.example.test",
        "cors_allowed_origins": "https://app.example.test",
        "database_url": "postgresql://test:password@db.example.test/fabricassist",
        "database_migration_url": "postgresql://test:password@db-direct.example.test/fabricassist",
        "s3_endpoint_url": "https://account.r2.cloudflarestorage.com",
        "s3_public_endpoint_url": "https://account.r2.cloudflarestorage.com",
        "s3_region": "auto",
        "s3_access_key": "synthetic-r2-access-key",
        "s3_secret_key": "synthetic-r2-secret-key",
        "s3_bucket": "fabricassist-test",
        "s3_force_path_style": False,
        "qstash_token": "synthetic-qstash-token",
        "qstash_current_signing_key": "synthetic-current-signing-key",
        "qstash_next_signing_key": "synthetic-next-signing-key",
        "qstash_destination_url": "https://api.example.test/internal/jobs/qstash",
        "valkey_url": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_unregistered_model_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"evidence_provider": "azure_openai"})


def test_gemini_provider_requires_api_key_and_uses_provider_model() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings(evidence_provider=ModelCapabilityProvider.GEMINI)

    settings = Settings(
        evidence_provider=ModelCapabilityProvider.GEMINI,
        gemini_api_key="synthetic-key",
        gemini_model="gemini-2.5-flash",
    )

    assert settings.gemini_model == "gemini-2.5-flash"


def test_settings_accept_test_configuration() -> None:
    settings = Settings(environment="test", database_url="postgresql://example.test/fabricassist")

    assert settings.environment == "test"
    assert settings.vision_max_input_tokens == 128_000
    assert settings.vision_max_output_tokens == 16_000
    assert settings.celery_broker_url == "redis://fabricassist-valkey:6379/0"


def test_vision_token_limits_cannot_exceed_the_model_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(vision_max_input_tokens=128_001)
    with pytest.raises(ValidationError):
        Settings(vision_max_output_tokens=16_001)


def test_production_rejects_local_database_defaults() -> None:
    with pytest.raises(ValidationError, match="must not use local development defaults"):
        Settings(environment="production")


def test_celery_broker_is_independent_from_valkey_capabilities() -> None:
    settings = Settings(
        environment="test",
        job_dispatcher=JobDispatcherType.CELERY,
        celery_broker_url="amqp://rabbitmq.internal/fabricassist",
        valkey_url="valkey://cache.internal:6379/4",
        hot_cache_backend=HotCacheBackend.NOOP,
        rate_limiter_backend=RateLimiterBackend.NOOP,
        concurrency_gate_backend=ConcurrencyGateBackend.NOOP,
    )

    assert settings.celery_broker_url.startswith("amqp://")
    assert settings.valkey_url.endswith("/4")


def test_any_selected_valkey_capability_requires_a_valkey_url() -> None:
    with pytest.raises(ValidationError, match="VALKEY_URL"):
        Settings(
            environment="test",
            valkey_url="",
            hot_cache_backend=HotCacheBackend.VALKEY,
            rate_limiter_backend=RateLimiterBackend.NOOP,
            concurrency_gate_backend=ConcurrencyGateBackend.NOOP,
        )


def test_qstash_settings_accept_complete_configuration_without_valkey() -> None:
    settings = qstash_settings()

    assert settings.deployment_profile == DeploymentProfile.LOCAL
    assert settings.job_dispatcher == JobDispatcherType.QSTASH
    assert settings.valkey_url == ""
    assert settings.max_images_per_scan == 8
    assert settings.vision_max_concurrency == 1
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 10
    assert settings.database_pool_recycle_seconds == -1
    assert settings.database_connect_attempts == 1
    assert settings.database_connect_retry_seconds == 0
    assert settings.migration_database_url == settings.database_migration_url


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"qstash_token": ""}, "QSTASH_TOKEN"),
        ({"qstash_current_signing_key": ""}, "CURRENT_SIGNING_KEY"),
        ({"qstash_next_signing_key": ""}, "NEXT_SIGNING_KEY"),
        ({"qstash_destination_url": "http://api.example.test/jobs"}, "DESTINATION_URL"),
    ],
)
def test_qstash_settings_reject_incomplete_configuration(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        qstash_settings(**overrides)


def test_retired_alpha_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": "alpha"})
    with pytest.raises(ValidationError):
        Settings.model_validate({"deployment_profile": "alpha"})


def test_secret_settings_are_not_expo_public_configuration() -> None:
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
