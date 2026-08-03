# Release gates

## Current prerelease

The current cumulative prerelease is `v1.3.3` (2026-07-31). Its
release notes are maintained in the root [`CHANGELOG.md`](../../CHANGELOG.md).
Create and push the immutable tag only after the working tree contains the
intended release commit:

```bash
git tag -a v0.1.0-alpha.30 -m "release: FabricAssist 0.1.0-alpha.30"
git push origin v0.1.0-alpha.30
```

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

## Garment-analysis v2 cutover

1. Record the deployed API/worker/client digests and take a verified database
   backup (`make backup-restore-test` locally, an isolated restore drill in
   staging).
2. Confirm no pending/running legacy scan-analysis runs. Migration
   `20260803_0025` durably cancels any that remain; they must be retried as a
   fresh v2 analysis, never resumed by a legacy executor.
3. Apply the migration, deploy API, worker, generated clients, and Expo web as
   one release, then run `make release-check`, GraphQL/OpenAPI drift checks, and
   the authenticated smoke suite.
4. Set `FABRICASSIST_GARMENT_ANALYSIS_ENABLED=true` and set the privacy approval
   assertion only after the record in `docs/privacy/subprocessors.md` is signed.
   A disabled or unapproved production gate returns readiness failure; it never
   falls back to v1.
5. During the observation window, watch v2 branch calls/errors/latency/tokens,
   review and clearer-image rates, and durable branch retries. Keep the backup
   reference with the release record.

If a rollback is necessary, stop new analysis writes and forward-fix with a
post-migration-compatible release. Restore the verified pre-cutover backup only
under the disaster-recovery authorization; never pair old application code with
the transformed schema.

Unperformed external gates remain **pending**, never implicitly passed.
The current owner/status record is maintained in
[`docs/release-approvals.md`](../release-approvals.md).
