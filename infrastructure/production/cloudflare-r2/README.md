# Cloudflare R2 production infrastructure reference

R2 uses the existing S3-compatible `S3ObjectStorageAdapter` adapter, a private bucket, and server-generated `private/` object keys. Required endpoint, region, CORS, retention, and operational recovery values are in `docs/production/operations.md`.
