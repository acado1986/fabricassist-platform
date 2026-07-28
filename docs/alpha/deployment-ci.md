# Alpha CI and deployment workflow

`alpha-quality.yml` is credential-free routine CI for pull requests and pushes
to `feat/free-alpha-deployment` and `main`. It runs only local deterministic
checks: `make check`, alpha configuration, synthetic QStash tests, and static
Expo export/secret scanning. It also runs the local PostgreSQL migration and
MinIO storage contracts plus OpenAPI/client drift checks. It does not receive
provider credentials or call Neon, R2, QStash, Koyeb, Cloudflare, or an AI
provider.

`deploy-alpha.yml` runs for `v*-alpha*` tags or a manual `ref` input. It checks
out that ref, records its immutable SHA, migrates first, deploys the API and
frontend in parallel from that SHA, and then runs the hosted mock-provider
smoke. The alpha GitHub environment supplies deployment and smoke secrets only
to the relevant protected jobs.

`alpha-live-smoke.yml` is manual diagnostic tooling for an environment that is
already deployed. Its optional `base_url` does not deploy a candidate and is
therefore not evidence that a new ref was released.

To roll back, manually dispatch `deploy-alpha.yml` with a known-good commit or
tag. Do not move or re-push a published tag, and do not automatically downgrade
PostgreSQL. Verify liveness, readiness, and hosted smoke after the redeploy.
