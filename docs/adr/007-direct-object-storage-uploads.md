# ADR-007: Upload directly to private object storage

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Images are private, potentially large, and must not become database blobs or be
proxied unnecessarily through the API.

## Decision

Use server-generated object keys and short-lived single-object presigned uploads
through an S3-compatible storage port. Use MinIO locally. Verify type, size,
decodability, and ownership before analysis.

## Consequences

Storage remains replaceable and private. Upload behavior is forbidden until
authentication and tenant isolation exist; it is not implemented in Phase 1.
