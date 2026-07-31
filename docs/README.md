# FabricAssist documentation

## Active references

- [`requirements.md`](requirements.md) — product, safety, security, and acceptance requirements.
- [`architecture.md`](architecture.md) — runtime boundaries and technology decisions.
- [`environment.md`](environment.md) — environment variables and capability profiles.
- [`production/deployment.md`](production/deployment.md) — stable production release procedure.
- [`production/operations.md`](production/operations.md) — active hosted operations, safety, and recovery.
- [`feature-tasks/`](feature-tasks/) — approved, bounded implementation handoffs.
- [`runbooks/`](runbooks/) — local operations, incidents, recovery, and release procedures.
- [`adr/`](adr/) — immutable architecture decisions.
- [`api/openapi.json`](api/openapi.json) — generated API contract.

## Historical references

[`archive/`](archive/) contains original implementation plans and retired
operational material. They are retained for history only and are not operational
sources of truth. The retired prerelease runbooks are archived under
[`archive/prerelease-runbooks/`](archive/prerelease-runbooks/).

Update the relevant active guide in the same change as code, configuration,
workflow, API, migration, security, or operational behavior. Never put secrets,
private URLs, customer data, or complete presigned URLs in documentation.
