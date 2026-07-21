from __future__ import annotations

import pytest
from pydantic import ValidationError

from fabricassist.settings import Settings


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
