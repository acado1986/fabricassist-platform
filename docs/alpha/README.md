# FabricAssist free alpha runbooks

This directory is the operator guide for the FabricAssist free alpha. It describes the repository's exact configuration and release procedures; it does not replace Neon, Cloudflare, Upstash, or Render product documentation.

## Read in this order

1. [Architecture](architecture.md) and [configuration](configuration.md).
2. [Secrets](secrets.md), then create the provider resources in the exact order in [deployment](deployment.md).
3. Execute [smoke tests](smoke-tests.md) after deployment.
4. Use [troubleshooting](troubleshooting.md) for a failed check or outage, and [rollback](rollback.md) for a release reversal.

`implementation-inventory.md` records the pre-alpha baseline. The earlier provider notes (`neon-database.md`, `r2-storage.md`, `render-api.md`, and `deployment-ci.md`) remain useful implementation references; these runbooks are the operational source of truth.

## Scope and guardrails

- Alpha is configuration-selected with `FABRICASSIST_DEPLOYMENT_PROFILE=alpha`,
  `FABRICASSIST_JOB_DISPATCHER=qstash`, and explicit no-op hot-cache,
  rate-limiter, and concurrency adapters; local defaults remain Celery, Valkey,
  PostgreSQL, and MinIO.
- PostgreSQL/Neon is the durable authority. R2 stores private image objects; QStash only dispatches identifier-only messages.
- The release workflow uses the mock vision provider. It may finish in `needs_review` or `needs_better_image`; do not claim an approved care plan from its synthetic label.
- Keep all provider credentials in protected GitHub and Render settings. No runtime URL, key, token, presigned URL, password, or refresh token belongs in this directory, a commit, workflow output, or `EXPO_PUBLIC_*` variable.

## Deterministic preflight

Run before a pull request or release dispatch. These commands do not contact the hosted providers:

```bash
make check
make check-alpha-config
make test-qstash
make build-alpha-web
git diff --check
```

The release workflow also runs migration, storage, and OpenAPI drift contracts. See [deployment](deployment.md) for the full release gate.
