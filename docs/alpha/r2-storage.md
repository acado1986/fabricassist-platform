# Cloudflare R2 storage profile

Phase 4 uses the existing `S3Storage` boto3-compatible adapter. Cloudflare R2
is selected entirely through FabricAssist S3 settings; there is no R2-specific
domain port or storage adapter. MinIO remains path-style for local Compose and
AWS S3 remains supported through the same configuration.

## Application configuration

Configure these secret values in the API/worker provider environment, never in
the Expo build or repository:

```env
FABRICASSIST_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
FABRICASSIST_S3_REGION=auto
FABRICASSIST_S3_BUCKET=fabricassist-alpha
FABRICASSIST_S3_FORCE_PATH_STYLE=false
FABRICASSIST_S3_ACCESS_KEY=<r2-access-key-id>
FABRICASSIST_S3_SECRET_KEY=<r2-secret-access-key>
```

Create the bucket as **private**. Give its access key only the object read/write
permissions needed by the application. Object keys remain server generated and
tenant-scoped; do not add a public bucket, public custom domain, or object-list
permission to browser clients. Presigned PUT and GET URLs use the R2 S3 endpoint
and retain FabricAssist's short configured expiry.

## R2 CORS

In the R2 bucket CORS configuration, add this rule after replacing the Pages
origin with the exact deployed origin (no trailing slash). Do not use `*`.

```json
[
  {
    "AllowedOrigins": ["https://<pages-project>.pages.dev"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["content-type"],
    "ExposeHeaders": ["etag"],
    "MaxAgeSeconds": 600
  }
]
```

If a production custom Pages domain is enabled, add that exact HTTPS origin as
another value in `AllowedOrigins`. Keep API and worker credentials out of CORS;
the browser receives only scoped presigned URLs.

## Lifecycle / retention

Configure a lifecycle deletion rule for the private FabricAssist bucket:

- prefix: `private/` (the deployed server-generated object-key root);
- action: delete objects after the configured tenant retention window;
- alpha default: **7 days**;
- do not transition objects to a public class or enable public access.

This is a safety net for the existing PostgreSQL-authoritative deletion workflow,
not a replacement for it. Keep R2 lifecycle retention at least as long as the
application's configured retention window so an uploaded object is not removed
before its durable deletion record is processed.

## Contract and opt-in live smoke

The default contract runs only against local MinIO:

```bash
make test-object-storage
```

The opt-in R2 smoke uses a dedicated disposable prefix and never runs in normal
CI. Export credentials only in a protected shell or secret-backed manual job:

```bash
export FABRICASSIST_R2_SMOKE=1
export FABRICASSIST_R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
export FABRICASSIST_R2_BUCKET=<private-test-bucket>
export FABRICASSIST_R2_ACCESS_KEY=<access-key-id>
export FABRICASSIST_R2_SECRET_KEY=<secret-access-key>
export FABRICASSIST_R2_TEST_PREFIX=smoke/fabricassist
make test-object-storage-r2
```

The smoke verifies presign generation, metadata validation, private read,
derivative write, tenant-prefix isolation, deletion, and invalid-key handling.
It intentionally does not list the whole bucket or test with real customer data.
