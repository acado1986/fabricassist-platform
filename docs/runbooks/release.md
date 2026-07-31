# Release gates

## Current production release

The current production release is `v1.3.4` (2026-07-31). Its
release notes are maintained in the root [`CHANGELOG.md`](../../CHANGELOG.md).
Create and push the immutable tag only after the working tree contains the
intended release commit:

```bash
git tag -a v1.3.4 -m "release: FabricAssist 1.3.4"
git push origin v1.3.4
```

This release contains the read-only GraphQL storefront implementation and its
REST/SSE integration. The stable tag uses the protected `production` GitHub
environment and the production deployment workflow; exact API and Pages URLs
come from protected production environment variables and are not stored here.

Pushing an stable `vMAJOR.MINOR.PATCH` tag starts the production deployment workflow. It runs
quality checks, migrations, Render API deployment, Cloudflare Pages deployment,
and hosted smoke tests. Do not move or reuse a published tag. This release requires all production approval gates below.

Phase 19 code readiness is necessary but does not itself approve production.
Record date, actor, artifact digest, command output, and exception owner for each
gate:

1. `make check`, `make migration-test`, `make openapi`, and clean Git drift.
2. Playwright customer/operator flow and Android Maestro smoke; iOS release build
   on macOS/Xcode.
3. `make security-check`, dependency/secret/container/IaC scans, and SBOM review.
   No unexpired high/critical finding is allowed.
4. `make iac-check`; protected OpenTofu staging plan/apply using immutable image
   digests and environment-supplied secrets.
5. `make backup-restore-test`, controlled load, Valkey-loss, worker-crash,
   provider-outage, deletion-retry, and rollback drills.
6. Textile-care owner approves validator version/checksum and regression report.
7. Privacy owner approves provider retention/subprocessor records and image
   retention/deletion behavior.
8. Product owner records source licensing/coverage and catalog conflict policy.
9. Migration one-off task completes before API/worker rollout; smoke and
   dashboards remain healthy through the observation window.

Unperformed external gates remain **pending**, never implicitly passed.
The current owner/status record is maintained in
[`docs/release-approvals.md`](../release-approvals.md).
