# Cloudflare R2 alpha infrastructure reference

R2 uses the existing S3-compatible `S3ObjectStorageAdapter` adapter, a private bucket, and server-generated `private/` object keys. Required endpoint, region, CORS, and retention values are in `docs/alpha/r2-storage.md`; operational recovery is in `docs/alpha/troubleshooting.md`.
