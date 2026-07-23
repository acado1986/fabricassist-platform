# Deployment

1. Build API/worker/web artifacts from one reviewed commit. Scan them, generate
   SBOMs, sign/push immutable digests, and record the digests.
2. Review `tofu plan` from `infrastructure/terraform/staging` in a protected
   environment. Secrets Manager provides all sensitive `FABRICASSIST_*` values.
3. Verify a current RDS snapshot and object-storage lifecycle policy.
4. Run Alembic `upgrade head` as a one-off task; never migrate in API startup.
5. Roll API and worker ECS services with circuit-breaker rollback. Mixed
   pre-cutover clients are unsupported.
6. Publish the web artifact behind TLS/CDN, then run synthetic health,
   authentication, upload/mock analysis, review, chat, and deletion checks.
7. Observe latency, 5xx, queue age, validator/review rate, model usage, product
   lookup outcomes, and deletion failures before promotion.

Production differs from local development: explicit HTTPS CORS origins, nonlocal
database/S3 credentials, fail-closed rate limits, an internal metrics token,
private networking, encryption, and a reviewed provider are mandatory.
