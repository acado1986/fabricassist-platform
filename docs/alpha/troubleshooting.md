# FabricAssist alpha troubleshooting

Start with the release SHA, timestamp, affected scan ID, and redacted workflow job URL. Never collect image bytes, passwords, access tokens, full presigned URLs, or QStash signing keys in an incident record.

| Symptom | Inspect | Safe recovery |
| --- | --- | --- |
| Alpha config check fails | `.env.alpha.example`, `Settings` validation, profile/dispatcher values | Correct placeholders or required HTTPS/TLS values; rerun `make check-alpha-config` without provider contact |
| API is live but not ready | Koyeb logs, Neon TLS URL, R2/QStash secret names | Correct secret/configuration; redeploy selected approved ref; do not start Celery in API |
| Browser upload CORS failure | Exact Pages origin in API and R2 CORS; no trailing slash | Add only exact HTTPS origin and retry a fresh presigned instruction; never use `*` |
| Upload completion fails | R2 private object metadata, MIME/size/image validation | Re-upload a valid synthetic image; do not mark a missing object complete |
| Analysis does not advance | scan durable stage/checkpoint, QStash delivery result, exact destination | Verify key overlap/raw-signature destination; replay only through the signed path and let durable recovery reconcile |
| Repeated work/result | operation key, idempotency key, checkpoint claim state | Stop manual duplicate sends; investigate database claim/idempotency before retrying |
| Invalid signed delivery loops | QStash response/status and message schema | Fix publisher schema/signature; permanently invalid messages must receive non-retry handling, not a transient retry |
| Migration job fails | direct Neon migration URL/TLS and Alembic head | Fix forward, rerun migration job; never auto-downgrade production-like alpha data |
| Smoke ends `needs_review` | mock provider/evidence outcome | This can be expected; confirm terminal safe status and result reload, then use a separate controlled real-provider test if approved |
| Secret marker in web bundle | `make build-alpha-web` output and frontend environment | Remove non-public value, rebuild, and rotate it if exposed; only the two documented Expo public variables are allowed |

## Escalation and acceptance

After any recovery, run liveness/readiness and the manual diagnostic live smoke workflow. Re-run the affected resilience drill. If safety, tenant isolation, or message compatibility is uncertain, keep the release unaccepted and follow [rollback.md](rollback.md) rather than guessing.
