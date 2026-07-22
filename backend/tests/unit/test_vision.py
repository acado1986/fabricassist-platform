from uuid import uuid4

import pytest

from fabricassist.application.vision import MockVisionProvider, NormalizedImage
from fabricassist.domain.evidence import ImageRole


@pytest.mark.asyncio
async def test_mock_evidence_is_source_referenced() -> None:
    result = await MockVisionProvider().extract_evidence(
        (NormalizedImage(uuid4(), b"x", "0" * 64, 320, 320, ImageRole.CARE_LABEL),)
    )
    assert result.delta.observations[0].source.role is ImageRole.CARE_LABEL
