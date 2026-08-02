# Changelog

All notable changes to FabricAssist are documented here.

## [1.3.7] - 2026-08-02

### Added

- Centralized typed REST-write cache effects for Apollo GraphQL reads, including
  normalized garment deletion cleanup and authenticated cache isolation.
- Canonical Apollo synchronization for REST cancellation and completed, failed,
  and cancelled SSE terminal events, including reconnect recovery.

### Fixed

- Prevented deleted garment detail, history, and normalized entities from
  remaining visible after successful REST deletion.
- Ensured mixed REST cache effects refresh every declared GraphQL projection.
- Preserved the active English or Spanish result locale during synchronization.
- Prevented cancelled analyses from remaining in a stale active state.

### Deployment

This patch release is deployed by pushing the immutable tag `v1.3.7`.

## [1.3.6] - 2026-08-01

### Fixed

- Prevented a stale GraphQL cache refetch from turning a successful image
  upload into a user-visible upload failure.

### Deployment

This patch release is deployed by pushing the immutable tag `v1.3.6`.

## [1.3.5] - 2026-07-31

### Fixed

- Fixed production GraphQL startup by instantiating Strawberry's
  `DisableIntrospection` extension correctly, restoring garment history and
  other authenticated GraphQL reads.

### Deployment

This patch release is deployed by pushing the immutable tag `v1.3.5`.

## [1.3.4] - 2026-07-31

### Added

- Read-only GraphQL storefront queries for result composites, garment detail and
  history, conversation reads, and image metadata, with Apollo `InMemoryCache`
  shared by the Expo web, iOS, and Android clients.
- Canonical GraphQL synchronization before SSE reconnects and after terminal
  run events, while REST remains responsible for all writes and file previews.

### Changed

- Restored multi-select garment-history deletion controls, localized English and
  Spanish bulk-delete copy, and typed Apollo cache synchronization after REST
  writes.
- History thumbnails now use safe GraphQL image identifiers with authenticated
  REST preview URLs; complete presigned URLs remain outside GraphQL.

### Fixed

- Prevented stale Apollo history pages from resurrecting deleted garments and
  added focus refetching for newly created or deleted garments.
- Detached hidden merged-garment tombstones before deleting their target garment
  so the self-referential foreign key cannot reject a confirmed deletion.

### Deployment

This stable release is deployed by pushing the immutable tag `v1.3.4`. The
production workflow applies migrations, deploys the API and web application
through the protected production environment, and runs the production smoke
test.

## [1.3.3] - 2026-07-31

### Security

- Upgrade Strawberry GraphQL to 0.312.4 to remediate the high-severity GraphQL WebSocket vulnerabilities reported by the production container scan.

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

[1.3.7]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.7
[1.3.6]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.6
[1.3.5]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.5
[1.3.3]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.3
[1.3.4]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.4
[1.3.2]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.2
[1.3.1]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.1
[1.3.0]: https://github.com/acado1986/fabricassist-platform/releases/tag/v1.3.0
