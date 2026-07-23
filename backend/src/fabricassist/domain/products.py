"""Deterministic product identifier normalization and checksum validation."""

from __future__ import annotations

from enum import StrEnum


class ProductMatchStatus(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    NOT_FOUND = "not_found"


class ProductLookupError(Exception):
    """A categorized, non-sensitive failure from a product-information adapter."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_barcode(value: str) -> str:
    normalized = "".join(character for character in value if character.isdigit())
    if len(normalized) not in {8, 12, 13, 14}:
        raise ValueError("BARCODE_UNSUPPORTED_LENGTH")
    if not _valid_mod10(normalized):
        raise ValueError("BARCODE_INVALID_CHECKSUM")
    return normalized


def _valid_mod10(value: str) -> bool:
    body, check = value[:-1], int(value[-1])
    total = sum(
        int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body))
    )
    return (10 - total % 10) % 10 == check
