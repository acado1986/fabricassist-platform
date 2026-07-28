# Neon PostgreSQL profile

Phase 5 keeps the existing SQLAlchemy `Database` engine/session factory and
Alembic environment. It does not add a Neon-specific repository, model, or
domain path.

## Required hosted-alpha configuration

Use Neon’s pooled connection for the application runtime and a direct
connection for Alembic and administrative operations. Both must require TLS.

```env
FABRICASSIST_DATABASE_URL=postgresql+psycopg://<user>:<password>@<pooled-host>/<database>?sslmode=require
FABRICASSIST_DATABASE_MIGRATION_URL=postgresql+psycopg://<user>:<password>@<direct-host>/<database>?sslmode=require
```

In the alpha profile, both URLs are required. Alembic always selects
`FABRICASSIST_DATABASE_MIGRATION_URL`; local development leaves it blank and
continues using `FABRICASSIST_DATABASE_URL`.

The alpha runtime uses a bounded pool: size 2, overflow 1, pre-ping enabled,
300-second recycle, and up to three readiness attempts with one-second delay.
These are application defaults for the constrained alpha runtime, not Neon-only
behaviour; tune them only after observing connection usage.

## One-time provider setup

1. Create a dedicated empty Neon alpha database; do not copy production users,
   scans, garments, conversations, or images.
2. Enable the `citext` and `vector` extensions, then apply Alembic migrations
   through the direct URL.
3. Seed only the dedicated FabricAssist alpha tenant/administrator through the
   existing seed command after migrations complete.
4. Store runtime and migration URLs in the API/worker provider secrets. Never
   add either to Expo public configuration or this repository.

## Opt-in smoke

The default suite uses local PostgreSQL and never contacts Neon. A protected
operator can verify a dedicated database with:

```bash
export FABRICASSIST_NEON_SMOKE=1
export FABRICASSIST_NEON_RUNTIME_URL='postgresql+psycopg://...pooler.../fabricassist?sslmode=require'
export FABRICASSIST_NEON_MIGRATION_URL='postgresql+psycopg://...direct.../fabricassist?sslmode=require'
make test-neon
```

The smoke checks TLS-bearing URLs, pooled runtime readiness, direct migration
connectivity, and required extensions. It does not migrate, seed, or modify the
database.
