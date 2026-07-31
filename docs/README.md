# FabricAssist documentation

## Active references

- [`requirements.md`](requirements.md) — product, safety, security, and acceptance requirements.
- [`architecture.md`](architecture.md) — runtime boundaries and technology decisions.
- [`environment.md`](environment.md) — environment variables and capability profiles.
- [`production/deployment.md`](production/deployment.md) — stable production release procedure.
- [`prerelease/`](prerelease/) — hosted prerelease operations.
- [`runbooks/`](runbooks/) — local operations, incidents, recovery, and release procedures.
- [`adr/`](adr/) — immutable architecture decisions.
- [`api/openapi.json`](api/openapi.json) — generated API contract.
- [`feature-tasks/graphql-garment-history-migration.md`](feature-tasks/graphql-garment-history-migration.md) — locally implemented migration of customer garment-history reads to GraphQL.
- [`feature-tasks/storefront-graphql-read-migration.md`](feature-tasks/storefront-graphql-read-migration.md) — planned unified v1 API migration for read-only GraphQL, REST writes, and SSE progress across web, iOS, and Android.

## Historical references

[`archive/`](archive/) contains the original free-alpha plan and implementation
inventory. They are retained for history only and are not operational sources
of truth.

Update the relevant active guide in the same change as code, configuration,
workflow, API, migration, security, or operational behavior. Never put secrets,
private URLs, customer data, or complete presigned URLs in documentation.
