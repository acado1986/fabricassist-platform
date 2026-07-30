# FabricAssist prerelease quotas and limits

Provider plan limits change independently of this repository. Check the active provider dashboards before onboarding users; do not encode a vendor quota in application code or promise an amount in user-facing copy.

## FabricAssist-enforced prerelease limits

| Limit | Value | Reason / response |
| --- | ---: | --- |
| Images per scan | 3 | bounded prerelease storage and analysis; reject excess images clearly |
| Image retention default | 7 days | private `private/` R2 lifecycle safety net; PostgreSQL lifecycle remains authoritative |
| Vision concurrency | 1 | prevent model/worker burst exhaustion |
| Job stage budget | 75 seconds | force durable checkpointed continuation rather than long request execution |
| Neon prerelease pool | 2 + 1 overflow | limit connection pressure; readiness retries three times |
| Presigned URL/CORS | scoped, exact origin | preserve private object access |

## Provider budget controls

- Configure dashboard spend/usage alerts for Neon, R2, QStash, Render, and Cloudflare Pages at a low prerelease threshold chosen by the operator.
- Monitor Render cold starts/health, Neon active connections, R2 object/storage growth and failed requests, QStash deliveries/retries, and Pages deployment failures.
- Keep routine CI credential-free. Run live smoke only after deployment, recovery, or planned diagnostics; use mock vision by default and real model smoke separately and sparingly.

## Exhaustion response

When a quota or capacity alarm fires, stop inviting users and pause new analysis dispatch if required. Preserve existing PostgreSQL state; do not delete objects to create room outside the normal lifecycle. Identify the provider limit, reduce traffic or increase the approved budget manually, then run readiness and live smoke before reopening the prerelease environment. Record the incident and observed usage without storing account identifiers or credentials.
