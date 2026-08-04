# pyright: reportPrivateUsage=false
from __future__ import annotations

import pytest

from fabricassist.domain.garment_analysis.parity import ExecutionSnapshot
from fabricassist.settings import ModelCapabilityProvider, Settings
from fabricassist.worker.tasks import _settings_for_execution_snapshot


def _snapshot(*, provider: str, model: str, stain_enabled: bool) -> ExecutionSnapshot:
    return ExecutionSnapshot(
        module_version="garment-analysis-v2",
        workflow_version="garment-analysis-v2",
        provider=provider,
        model=model,
        prompt_versions={},
        schema_versions={},
        preprocessing_version="normalized-jpeg-v2",
        branch_routing_version="routing-v2",
        cache_version="cache-v2",
        product_adapter_version="product-v2",
        identity_policy_version="identity-v2",
        care_policy_version="care-policy-v2",
        rendering_version="care-rendering-v2",
        effective_feature_flags={"stain_analysis": stain_enabled},
    )


@pytest.mark.parametrize(
    ("provider", "model", "model_setting"),
    [
        (ModelCapabilityProvider.GEMINI, "gemini-pinned", "garment_analysis_gemini_model"),
        (
            ModelCapabilityProvider.OPENAI_RESPONSES,
            "openai-pinned",
            "garment_analysis_openai_model",
        ),
    ],
)
def test_execution_snapshot_reconstructs_typed_provider_model_and_feature_flags(
    provider: ModelCapabilityProvider, model: str, model_setting: str
) -> None:
    configured = Settings(
        garment_analysis_provider=ModelCapabilityProvider.MOCK,
        garment_analysis_stain_enabled=False,
    )

    reconstructed = _settings_for_execution_snapshot(
        configured,
        _snapshot(provider=provider.value, model=model, stain_enabled=True),
    )

    assert reconstructed.garment_analysis_provider is provider
    assert getattr(reconstructed, model_setting) == model
    assert reconstructed.garment_analysis_stain_enabled is True
    assert configured.garment_analysis_provider is ModelCapabilityProvider.MOCK


def test_execution_snapshot_rejects_unknown_provider_instead_of_using_runtime_default() -> None:
    with pytest.raises(ValueError):
        _settings_for_execution_snapshot(
            Settings(),
            _snapshot(provider="unknown-provider", model="unknown", stain_enabled=False),
        )
