#!/usr/bin/env python3
"""Validate Phase 8 workflow structure without invoking GitHub or providers."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


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
    quality = load("alpha-quality.yml")
    for marker in (
        "pull_request:",
        "feat/free-alpha-deployment",
        "make check-alpha-config",
        "make test-qstash",
        "make test-migrations",
        "make test-object-storage",
        "make check-openapi-drift",
        "make build-alpha-web",
    ):
        require(quality, marker, "alpha-quality.yml")
    for forbidden in (
        "KOYEB_API_TOKEN",
        "CLOUDFLARE_API_TOKEN",
        "FABRICASSIST_DATABASE_MIGRATION_URL",
        "QSTASH_TOKEN",
    ):
        if forbidden in quality:
            raise SystemExit(
                f"alpha-quality.yml must not use external alpha credentials: {forbidden}"
            )

    deploy = load("deploy-alpha.yml")
    for marker in (
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
        "uv run --project backend alembic -c backend/alembic.ini upgrade head",
    ):
        require(deploy, marker, "deploy-alpha.yml")
    for forbidden in ("KOYEB_API_TOKEN", "koyeb-community/", "koyeb/action-"):
        if forbidden in deploy:
            raise SystemExit(f"deploy-alpha.yml must not use Koyeb: {forbidden}")

    smoke = load("alpha-live-smoke.yml")
    for marker in ("workflow_dispatch:", "base_url:", "make alpha-live-smoke"):
        require(smoke, marker, "alpha-live-smoke.yml")
    print("Alpha CI, deployment, and live-smoke workflow checks passed.")


if __name__ == "__main__":
    main()
