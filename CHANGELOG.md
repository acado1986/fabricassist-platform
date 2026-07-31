# Changelog

All notable changes to FabricAssist are documented here.

## [1.3.2] - 2026-07-31

### Fixed

- Derive the FastAPI OpenAPI version from installed FabricAssist package metadata, keeping generated OpenAPI artifacts deterministic in release CI.

## [1.3.1] - 2026-07-31

### Fixed

- Allow Alembic to traverse the orphan-garment repair migration during rollback without attempting an unsafe data reversal.

## [1.3.0] - 2026-07-31

### Added

- Mixed GraphQL, REST, and Server-Sent Events API support for AI runs and conversation updates.
- Durable AI-run, image, and event persistence with the `20260731_0020` migration.
- Frontend GraphQL operations and SSE client coverage for live run updates.
- Garment revision orphan cleanup and confirmed history deletion behavior.
- Explicit `make migrate-repair REVISION=...` recovery workflow for locally mis-stamped databases.

### Changed

- Synchronized generated OpenAPI and TypeScript API client artifacts with the current backend contract.
- Expanded release, deployment, environment, migration, and SSE runbook documentation.
- Updated dependency and security metadata used by the release workflows.

### Deployment

This production release is deployed by pushing the immutable tag `v1.3.1`. The
tag-triggered workflow runs quality gates, applies migrations, deploys the API
and web application, and executes hosted smoke tests. Production stable release
remains a separate exact `vMAJOR.MINOR.PATCH` workflow.

[1.3.2]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.2
[1.3.1]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.1
[1.3.0]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.0
