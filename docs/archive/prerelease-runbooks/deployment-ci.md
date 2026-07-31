# Prerelease CI and deployment workflow

`release-quality.yml` is credential-free routine CI for pull requests and pushes
to `main`. It runs only local deterministic
checks: `make check`, prerelease configuration, synthetic QStash tests, and static
Expo export/secret scanning. It also runs the local PostgreSQL migration and
MinIO storage contracts plus OpenAPI/client drift checks. It does not receive
provider credentials or call Neon, R2, QStash, Render, Cloudflare, or an AI
provider.

`deploy-prerelease.yml` runs for immutable `v*-alpha*` prerelease tags or a manual
`ref` input. It checks out that ref, records its immutable SHA, migrates first,
deploys the API and frontend in parallel from that SHA, and then runs the prerelease
smoke. The `alpha` GitHub environment supplies deployment and smoke secrets
only to the relevant protected jobs.

`prerelease-live-smoke.yml` is manual diagnostic tooling for an environment that is
already deployed. Its optional `base_url` does not deploy a candidate and is
therefore not evidence that a new ref was released.

Stable tags deploy only through the separate production workflow documented in
the [production deployment runbook](../../production/deployment.md).

To roll back, manually dispatch `deploy-prerelease.yml` with a known-good commit or
tag. Do not move or re-push a published tag, and do not automatically downgrade
PostgreSQL. Verify liveness, readiness, and prerelease smoke after the redeploy.
