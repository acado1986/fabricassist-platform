"""Verify that first-party release metadata agrees with VERSION."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
    raise SystemExit(f"VERSION must contain MAJOR.MINOR.PATCH, got {VERSION!r}")

json_files = [
    ROOT / "frontend/package.json",
    ROOT / "frontend/apps/client/package.json",
    *sorted((ROOT / "frontend/packages").glob("*/package.json")),
]
for path in json_files:
    version = json.loads(path.read_text(encoding="utf-8"))["version"]
    if version != VERSION:
        raise SystemExit(f"{path.relative_to(ROOT)} has version {version!r}, expected {VERSION!r}")

pyproject = (ROOT / "backend/pyproject.toml").read_text(encoding="utf-8")
if not re.search(rf'^version = "{re.escape(VERSION)}"$', pyproject, re.MULTILINE):
    raise SystemExit("backend/pyproject.toml does not match VERSION")

api_main = (ROOT / "backend/src/fabricassist/api/main.py").read_text(encoding="utf-8")
if f'version="{VERSION}"' not in api_main:
    raise SystemExit("FastAPI metadata does not match VERSION")

expo_config = (ROOT / "frontend/apps/client/app.config.ts").read_text(encoding="utf-8")
if f"version: '{VERSION}'" not in expo_config:
    raise SystemExit("Expo app metadata does not match VERSION")

print(f"version metadata is consistent: {VERSION}")
