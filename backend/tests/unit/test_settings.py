from __future__ import annotations

import pytest
from pydantic import ValidationError

from fabricassist.settings import Settings


def test_settings_accept_test_configuration() -> None:
    settings = Settings(environment="test", database_url="postgresql://example.test/fabricassist")

    assert settings.environment == "test"


def test_production_rejects_local_database_defaults() -> None:
    with pytest.raises(ValidationError, match="must not use local development defaults"):
        Settings(environment="production")
