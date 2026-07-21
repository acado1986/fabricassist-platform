# FabricAssist backend

The backend uses the `backend/src/fabricassist/` Python namespace. Phase 5 adds
Alembic and storage-only SQLAlchemy metadata under
`fabricassist.infrastructure.persistence`.

Run `make migrate` after `make up` to apply the PostgreSQL baseline. Run
`make seed` only for the idempotent development tenant and a non-loginable admin
record; Phase 6 will add authentication and tenant authorization.

The baseline stores object metadata only. Image bytes remain outside PostgreSQL in
private S3-compatible storage, which is implemented in a later phase.
