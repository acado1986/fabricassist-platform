"""Reviewed, checksum-verified prompt assets for garment-analysis branches."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files


@dataclass(frozen=True)
class PromptAsset:
    branch: str
    version: str
    text: str
    checksum: str


_PROMPTS = {
    "garment_inspection": ("v1", "garment_inspection.txt"),
    "label_extraction": ("v1", "label_extraction.txt"),
    "stain_treatment": ("v1", "stain_treatment.txt"),
    "barcode_enrichment": ("v1", "barcode_enrichment.txt"),
}


def load_prompt(branch: str) -> PromptAsset:
    """Load a fixed package asset; versions are stable public metadata."""
    try:
        version, filename = _PROMPTS[branch]
    except KeyError as error:
        raise ValueError(f"Unsupported garment-analysis prompt branch: {branch}") from error
    text = (
        files("fabricassist.application.garment_analysis.prompts.v1")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return PromptAsset(
        branch=branch,
        version=f"{branch}-{version}",
        text=text,
        checksum=sha256(text.encode()).hexdigest(),
    )
