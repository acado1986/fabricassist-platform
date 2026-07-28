# FabricAssist alpha secrets and protected values

Create values manually in provider dashboards and GitHub's protected `alpha` environment. Never paste their values into a shell history, issue, commit, or workflow log.

## GitHub environment

Required GitHub **secrets**:

```text
KOYEB_API_TOKEN
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
FABRICASSIST_DATABASE_MIGRATION_URL
FABRICASSIST_ALPHA_SMOKE_EMAIL
FABRICASSIST_ALPHA_SMOKE_PASSWORD
```

Required GitHub **variable** (not secret, but verify it is the final HTTPS API origin with no trailing slash):

```text
FABRICASSIST_API_URL
```

The migration secret is used only by the protected `migrate` job. The smoke credentials must be a dedicated alpha account with no personal data.

## Koyeb secret names

Create these exact names because `deploy-alpha.yml` references them as `@NAME`:

```text
FABRICASSIST_ACCESS_TOKEN_SECRET
FABRICASSIST_APP_BASE_URL
FABRICASSIST_API_PUBLIC_URL
FABRICASSIST_CORS_ALLOWED_ORIGINS
FABRICASSIST_DATABASE_URL
FABRICASSIST_DATABASE_MIGRATION_URL
FABRICASSIST_S3_ENDPOINT_URL
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL
FABRICASSIST_S3_BUCKET
FABRICASSIST_S3_ACCESS_KEY
FABRICASSIST_S3_SECRET_KEY
FABRICASSIST_QSTASH_TOKEN
FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY
FABRICASSIST_QSTASH_NEXT_SIGNING_KEY
FABRICASSIST_QSTASH_DESTINATION_URL
```

Use a randomly generated access-token secret of at least 32 characters. Set the database runtime secret to the **pooled** TLS URL, and the migration secret to the **direct** TLS URL. Set the QStash destination only after the final Koyeb API origin is known:

```text
https://<final-api-origin>/internal/jobs/qstash
```

## Rotation and recovery

Rotate a leaked value at its owning provider first, update the matching GitHub or Koyeb secret, then redeploy the same approved ref and run live smoke. For QStash signing-key rotation, configure old/current and new/next together, verify signed delivery with both overlap keys accepted, then promote the new key and retain a new next key. Do not rotate only one side of the internal destination verification.

If a credential appears in a log or commit, treat it as compromised: revoke it, audit provider access, redeploy, and document the incident without reproducing the secret.
