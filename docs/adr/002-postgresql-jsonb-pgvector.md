# ADR-002: Use PostgreSQL, JSONB, and pgvector

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

FabricAssist needs transactional business records, evolving provider snapshots,
typed safety facts, and optional future similarity search.

## Decision

Use PostgreSQL as the authoritative store, JSONB for evolving/audit-compatible
payloads, typed columns for stable safety facts, and pgvector only for optional
candidate retrieval after safer cache layers exist. Do not add MongoDB or a
separate proprietary vector database.

## Consequences

Business truth remains transactional and portable. Images stay in private
S3-compatible object storage. Schema work begins only in Phase 5 through Alembic.
