# FabricAssist prerelease secrets and protected values

Create values manually in provider dashboards and GitHub's protected `alpha` environment. Never paste their values into a shell history, issue, commit, or workflow log.

## GitHub environment

Required GitHub **secrets**:

```text
RENDER_DEPLOY_HOOK_URL
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

The migration secret is used only by the protected `migrate` job. The smoke credentials must be a dedicated prerelease account with no personal data.

## Render runtime variable names

Create these exact names in the Render service dashboard. The deployment
workflow never writes their values; it only triggers the selected Git SHA with
the protected deploy-hook secret:

```text
FABRICASSIST_ACCESS_TOKEN_SECRET
FABRICASSIST_APP_BASE_URL
FABRICASSIST_API_PUBLIC_URL
FABRICASSIST_CORS_ALLOWED_ORIGINS
FABRICASSIST_DATABASE_URL
FABRICASSIST_DATABASE_MIGRATION_URL
FABRICASSIST_S3_ENDPOINT_URL
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL
FABRICASSIST_S3_REGION
FABRICASSIST_S3_BUCKET
FABRICASSIST_S3_ACCESS_KEY
FABRICASSIST_S3_SECRET_KEY
FABRICASSIST_S3_FORCE_PATH_STYLE
FABRICASSIST_QSTASH_TOKEN
FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY
FABRICASSIST_QSTASH_NEXT_SIGNING_KEY
FABRICASSIST_QSTASH_DESTINATION_URL
```

For the R2-backed prerelease, set `FABRICASSIST_S3_REGION=auto` and
`FABRICASSIST_S3_FORCE_PATH_STYLE=false`. The API now rejects a prerelease
configuration that omits either R2 credential instead of starting successfully
and failing later while preparing an upload.

Use a randomly generated access-token secret of at least 32 characters. Set the database runtime secret to the **pooled** TLS URL, and the migration secret to the **direct** TLS URL. Set the QStash destination only after the final Render API origin is known:

```text
https://<final-api-origin>/internal/jobs/qstash
```

## Rotation and recovery

Rotate a leaked value at its owning provider first, update the matching GitHub or Render value, then redeploy the same approved ref and run live smoke. For QStash signing-key rotation, configure old/current and new/next together, verify signed delivery with both overlap keys accepted, then promote the new key and retain a new next key. Do not rotate only one side of the internal destination verification.

If a credential appears in a log or commit, treat it as compromised: revoke it, audit provider access, redeploy, and document the incident without reproducing the secret.
