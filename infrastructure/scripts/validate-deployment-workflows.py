#!/usr/bin/env python3
"""Validate release workflow structure without invoking GitHub or providers."""

from __future__ import annotations

import runpy
import struct
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / "infrastructure" / "scripts"


def load(name: str) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        raise SystemExit(f"missing workflow: {path}")
    yaml.safe_load(path.read_text())
    return path.read_text()


def require(content: str, marker: str, workflow: str) -> None:
    if marker not in content:
        raise SystemExit(f"{workflow} is missing: {marker}")


def main() -> None:
    quality = load("release-quality.yml")
    for marker in (
        "name: Release quality",
        "pull_request:",
        "make check-alpha-config",
        "make check-production-config",
        "make test-qstash",
        "make test-migrations",
        "make test-object-storage",
        "make check-openapi-drift",
        "make build-release-web",
        "make check-deployment-workflows",
    ):
        require(quality, marker, "release-quality.yml")
    for forbidden in (
        "KOYEB_API_TOKEN",
        "CLOUDFLARE_API_TOKEN",
        "FABRICASSIST_DATABASE_MIGRATION_URL",
        "QSTASH_TOKEN",
    ):
        if forbidden in quality:
            raise SystemExit(
                f"release-quality.yml must not use external deployment credentials: {forbidden}"
            )

    alpha_deploy = load("deploy-prerelease.yml")
    for marker in (
        "name: Deploy prerelease",
        '"v*-alpha*"',
        "workflow_dispatch:",
        "description: Commit, branch, or tag to deploy",
        "ref: ${{ inputs.ref || github.ref }}",
        "git rev-parse HEAD",
        "needs: quality",
        "needs: [quality, migrate]",
        "needs: [deploy-api, deploy-web]",
        "RENDER_DEPLOY_HOOK_URL",
        '--data-urlencode "ref=${SELECTED_SHA}"',
        "Wait for API liveness and readiness",
        "uses: cloudflare/wrangler-action@v3",
        "apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}",
        "accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "gitHubToken: ${{ secrets.GITHUB_TOKEN }}",
        "steps.deploy-pages.outputs.deployment-url",
        "run-release-migrations.sh",
    ):
        require(alpha_deploy, marker, "deploy-prerelease.yml")
    for forbidden in ("KOYEB_API_TOKEN", "koyeb-community/", "koyeb/action-"):
        if forbidden in alpha_deploy:
            raise SystemExit(f"deploy-prerelease.yml must not use Koyeb: {forbidden}")

    production_deploy = load("deploy-production.yml")
    for marker in (
        "name: Deploy production",
        '"v[0-9]*.[0-9]*.[0-9]*"',
        '"!v*-*"',
        "Stable tag or exact commit to deploy",
        "make check-production-config",
        "make security-check",
        "environment: production",
        "FABRICASSIST_PAGES_PROJECT",
        "EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT: production",
        "FABRICASSIST_RELEASE_SMOKE_EMAIL",
        "run-release-migrations.sh",
        "needs: [deploy-api, deploy-web]",
    ):
        require(production_deploy, marker, "deploy-production.yml")
    for forbidden in (
        "environment: alpha",
        "FABRICASSIST_ALPHA_",
        "fabricassist-alpha",
        "v*-alpha*",
    ):
        if forbidden in production_deploy:
            raise SystemExit(
                f"deploy-production.yml contains alpha-only marker: {forbidden}"
            )

    migration_runner = SCRIPTS / "run-release-migrations.sh"
    if not migration_runner.is_file():
        raise SystemExit(f"missing migration runner: {migration_runner}")
    runner = migration_runner.read_text()
    for marker in (
        "max_attempts=4",
        "FABRICASSIST_MIGRATION_RETRY_DELAY_SECONDS",
        "AdminShutdown",
        "alembic -c backend/alembic.ini upgrade head",
        "Migration failed with a non-transient error; not retrying.",
    ):
        require(runner, marker, "run-release-migrations.sh")

    for workflow in ("prerelease-live-smoke.yml", "production-live-smoke.yml"):
        smoke = load(workflow)
        for marker in (
            "workflow_dispatch:",
            "base_url:",
            "FABRICASSIST_RELEASE_API_URL",
            "make release-live-smoke",
        ):
            require(smoke, marker, workflow)
    fixture_png = runpy.run_path(str(SCRIPTS / "release-live-smoke.py"))["fixture_png"]()
    width, height = struct.unpack(">II", fixture_png[16:24])
    if width < 320 or height < 320:
        raise SystemExit("release smoke fixture must satisfy backend image dimensions")
    print("Prerelease and production deployment workflow checks passed.")


if __name__ == "__main__":
    main()
