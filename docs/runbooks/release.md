# Release gates

## Version and changelog maintenance

`VERSION` is the release-version source for repository metadata. Keep it in
sync with the stable Git tag and update the same version in the backend,
frontend, Expo, and OpenAPI metadata. The root `CHANGELOG.md` records the user-
visible changes under `Unreleased` until the release is prepared.

Before tagging a release:

1. Move the completed entries from `Unreleased` to a dated version heading.
2. Update `VERSION` and run `make check-version`.
3. Run `make openapi` so the checked-in OpenAPI metadata has the same version.
4. Run the release quality gates, commit the metadata and changelog together,
   then create an annotated `vMAJOR.MINOR.PATCH` tag on that commit.

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
