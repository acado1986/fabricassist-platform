# FabricAssist alpha smoke and acceptance runbook

Run the protected GitHub `Alpha live smoke` workflow after an environment is already deployed, after recovery, and after rollback. Its optional `base_url` is diagnostic only; it does not deploy a candidate.

## Automated hosted smoke

The `deploy-alpha.yml` final job and `make alpha-live-smoke` check:

1. API liveness and readiness.
2. Dedicated smoke-user login.
3. Draft creation, presigned upload instruction, direct private upload, and API upload completion.
4. Image-upload and analysis idempotency replay.
5. QStash-dispatched analysis until a terminal safe status, then result reload.
6. Scan deletion through the existing deletion lifecycle.

The generated fixture is intentionally synthetic. With the mock provider, `completed`, `needs_review`, or `needs_better_image` is an expected safe terminal state; a mock result is not proof of a customer-approved care plan. The smoke script does not print credentials or presigned URLs.

## Manual end-to-end acceptance

From the deployed Pages origin, use the dedicated alpha account to verify:

- registration/sign-in; draft scan; one garment and one care-label image; direct private R2 uploads; and API completion confirmation;
- analysis with an idempotency key; a QStash identifier-only message; durable Neon checkpoint progression; frontend polling; and result after browser refresh;
- repeated analysis idempotency and duplicate QStash delivery do not duplicate work; deletion removes the scan's private objects through the lifecycle;
- logs contain no credentials, image bytes, full presigned URLs, or refresh tokens.

Record each scenario's timestamp, release SHA, and pass/fail outcome. Do not attach customer images or secret-bearing logs.

## Resilience drill matrix

Before accepting a release, perform or schedule these controlled alpha drills:

| Drill | Expected FabricAssist behavior | Recovery evidence |
| --- | --- | --- |
| Blurred image | better-image/review outcome, no invented permission | capture guidance and durable status |
| Provider timeout | bounded retry/failure state, no permanent lock | scan can be retried/reviewed |
| Temporary Neon failure | checkpoint is not falsely completed | readiness recovers and pending work reconciles |
| Next-stage publish failure | committed checkpoint is recovered safely | no duplicate result after replay |
| Render/Neon cold start | readiness eventually passes within operational timeout | smoke rerun succeeds |
| R2 failure | upload/verification fails safely | no completed image reference without object |
| Invalid signature | internal endpoint rejects it | no checkpoint/work created |
| Permanent invalid message | explicit non-retry response | QStash does not redeliver indefinitely |
| Three users / three images | max-three alpha limit and tenant isolation hold | no cross-tenant access or duplicate work |
| Local regression | local Celery/Valkey/MinIO flow passes | `make check` result recorded |

Use synthetic data and a maintenance window for destructive/retry drills. If a drill fails, leave the release unaccepted and use the relevant recovery path in [troubleshooting](troubleshooting.md) or [rollback](rollback.md).
