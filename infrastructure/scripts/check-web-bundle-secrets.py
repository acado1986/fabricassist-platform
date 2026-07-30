#!/usr/bin/env python3
"""Fail if an Expo static bundle contains a known private setting or secret prefix."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PRIVATE_SETTING_NAMES = (
    "FABRICASSIST_ACCESS_TOKEN_SECRET",
    "FABRICASSIST_DATABASE_URL",
    "FABRICASSIST_DATABASE_MIGRATION_URL",
    "FABRICASSIST_S3_ACCESS_KEY",
    "FABRICASSIST_S3_SECRET_KEY",
    "FABRICASSIST_QSTASH_TOKEN",
    "FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY",
    "FABRICASSIST_QSTASH_NEXT_SIGNING_KEY",
    "FABRICASSIST_OPENAI_RESPONSES_API_KEY",
    "FABRICASSIST_GEMINI_API_KEY",
    "FABRICASSIST_PRODUCT_HTTP_JSON_API_KEY",
    "FABRICASSIST_REFRESH_TOKEN_HASH_KEY",
)
SECRET_PREFIXES = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:sk|cfat|cfut|sig)_[A-Za-z0-9_-]{16,}"),
)


def find_secret_markers(bundle_dir: Path) -> list[str]:
    """Return safe file-and-marker descriptions without printing secret values."""
    findings: list[str] = []
    for path in sorted(path for path in bundle_dir.rglob("*") if path.is_file()):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for name in PRIVATE_SETTING_NAMES:
            if name in content:
                findings.append(f"{path}: private setting name {name}")
        for prefix in SECRET_PREFIXES:
            if prefix.search(content):
                findings.append(f"{path}: known secret prefix {prefix.pattern}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir", type=Path)
    args = parser.parse_args()

    if not args.bundle_dir.is_dir():
        print(f"Generated web bundle directory does not exist: {args.bundle_dir}", file=sys.stderr)
        return 2

    findings = find_secret_markers(args.bundle_dir)
    if findings:
        print("Private configuration marker found in generated web bundle:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1

    print(f"No known secret markers found in {args.bundle_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
